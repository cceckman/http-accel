from amaranth import Module, Signal
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib import stream
from amaranth.utils import ceil_log2


def tree_and(m: Module, inputs: list[Signal]) -> Signal:
    if len(inputs) == 1:
        return inputs[0]
    elif len(inputs) == 2:
        result = Signal(1)
        m.d.comb += result.eq(inputs[0] & inputs[1])
        return result
    else:
        l = len(inputs)
        left = tree_and(m, inputs[:l//2])
        right = tree_and(m, inputs[l//2:])
        return tree_and(m, [left, right])


def tree_or(m: Module, inputs: list[Signal]) -> Signal:
    if len(inputs) == 1:
        return inputs[0]
    elif len(inputs) == 2:
        result = Signal(1)
        m.d.comb += result.eq(inputs[0] | inputs[1])
        return result
    else:
        l = len(inputs)
        left = tree_or(m, inputs[:l//2])
        right = tree_or(m, inputs[l//2:])
        return tree_or(m, [left, right])


def fanout_stream(m: Module, input: stream.Signature, outputs: list[stream.Signature]):
    combined_ready = tree_and(m, [o.ready for o in outputs])
    m.d.comb += input.ready.eq(combined_ready)

    for o in outputs:
        m.d.comb += [
            o.valid.eq(input.valid & combined_ready),
            o.payload.eq(input.payload),
        ]


class LimitForwarder(Component):
    """
    Forwards a limited number of bytes from one stream to another, then stops.

    Parameters
    ---------
    width: width of the data stream.
    max_count: maximum value of the counter.

    TODO: Documentation for attributes
    """

    def __init__(self, width: int, max_count: int):
        count = ceil_log2(max_count)

        super().__init__({
            "inbound": In(stream.Signature(width)),
            "outbound": Out(stream.Signature(width)),
            "count": In(count),
            "start": In(1),
            "done": Out(1),
        })
        self._count = count

    def elaborate(self, _platform):
        m = Module()

        countdown = Signal(self._count)
        # No transfer by default:
        m.d.comb += [
            self.inbound.ready.eq(0),
            self.outbound.valid.eq(0),
        ]

        with m.FSM():
            with m.State("idle"):
                m.next = "idle"
                m.d.comb += self.done.eq(1)
                with m.If(self.start):
                    m.next = "run"
                    m.d.sync += countdown.eq(self.count)
            with m.State("run"):
                m.next = "run"
                m.d.comb += self.done.eq(0)
                with m.If(countdown == 0):
                    m.next = "idle"
                with m.Else():
                    # We want to do this:
                    # connect(m, self.inbound, self.outbound)
                    # But if we do so in the testbench, we get
                    #   raise DriverConflict("Combinationally driven signals cannot be overriden by testbenches")
                    # from
                    #   ctx.set(dut.inbound.valid, 1)

                    # Yet this works:
                    m.d.comb += [
                        self.inbound.ready.eq(self.outbound.ready),
                        self.outbound.valid.eq(self.inbound.valid),
                        self.outbound.payload.eq(self.inbound.payload),
                    ]
                    with m.If(self.outbound.ready & self.inbound.valid):
                        # Byte was transferred
                        m.d.sync += countdown.eq(countdown - 1)

        return m
