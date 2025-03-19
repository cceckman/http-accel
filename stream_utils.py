from amaranth import Module, Signal
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib import stream


class LimitForwarder(Component):
    """
    Forwards a limited number of bytes from one stream to another, then stops.

    TODO: Documentation, parameterization
    """

    inbound: In(stream.Signature(8))
    outbound: Out(stream.Signature(8))

    count: In(9)
    start: In(1)
    done: Out(1)

    def elaborate(self, _platform):
        m = Module()

        countdown = Signal(9)
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
                    # Doesn't want to connect()?
                    m.d.comb += [
                            self.inbound.ready.eq(self.outbound.ready),
                            self.outbound.valid.eq(self.inbound.valid),
                            self.outbound.payload.eq(self.inbound.payload),
                    ]
                    with m.If(self.outbound.ready & self.inbound.valid):
                        # Byte was transferred
                        m.d.sync += countdown.eq(countdown - 1)

        return m
