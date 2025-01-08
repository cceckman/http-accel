from amaranth import Const, unsigned, Module, ClockDomain, DomainRenamer, Assert
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream
from amaranth.lib.cdc import PulseSynchronizer
from amaranth.lib.fifo import AsyncFIFO, SyncFIFOBuffered

try:
    from up_counter import UpCounter
    from number import Number
    from printer import Printer
except ImportError:
    from .up_counter import UpCounter
    from .number import Number
    from .printer import Printer


class HTTP10Server(Component):
    """
    An HTTP 1.0 server implemented in hardware.

    Attributes
    ----------
    input: Stream(8), input
        Input data stream, from the client to the server.
    output: Stream(8), output
        Output data stream, from the server to the client.

    """

    input: In(stream.Signature(unsigned(8)))
    output: Out(stream.Signature(unsigned(8)))
    tick: Out(1)

    def elaborate(self, platform):
        m = Module()

        # For now, discard all input from the host:
        m.d.comb += self.input.ready.eq(Const(1))

        SECOND_MAX = 2 ** 20
        import math
        SECOND_WIDTH = math.ceil(math.log2(SECOND_MAX))

        freq = 10
        if platform and platform.default_clk_frequency:
            freq = round(platform.default_clk_frequency)

        # Repeats a second count at 1Hz.
        m.submodules.tick_counter = tick_counter = UpCounter(freq)
        m.d.comb += [tick_counter.en.eq(Const(1))]

        # In the server domain, run a counter of elapsed seconds.
        m.submodules.second_counter = second_counter = UpCounter(SECOND_MAX)
        # TODO: Sync or comb? Doesn't really matter;
        # sync "just" introduces a cycle of delay
        m.d.sync += [second_counter.en.eq(tick_counter.ovf), ]

        m.submodules.number = number = Number(SECOND_WIDTH)
        m.submodules.suffix = suffix = Printer(" seconds since startup\r\n")

        # All output goes through a FIFO for reclocking.
        m.submodules.output_fifo = output_fifo = SyncFIFOBuffered(
            width=8, depth=4)

        # Print the appropriate section of the message:
        m.d.comb += [
            number.output.ready.eq(Const(0)),
            suffix.output.ready.eq(Const(0)),
            output_fifo.w_en.eq(Const(0)),
            output_fifo.w_data.eq(Const(0)),
            number.en.eq(Const(0)), suffix.en.eq(Const(0)),
        ]
        m.d.sync += [
            Assert(~(number.output.ready & suffix.output.ready)),
            Assert(~(number.output.valid & suffix.output.valid)),
            Assert(~(number.output.valid & number.done)),
            Assert(~(suffix.output.valid & suffix.done)),
        ]
        with m.FSM():
            with m.State("idle"):
                m.next = "idle"
                with m.If(tick_counter.ovf):
                    m.d.comb += [number.en.eq(Const(1)), ]
                    m.next = "number"

            with m.State("number"):
                m.next = "number"
                # Mux the output FIFO to the number output:
                m.d.comb += [
                    output_fifo.w_en.eq(number.output.valid),
                    output_fifo.w_data.eq(number.output.payload),
                    number.output.ready.eq(output_fifo.w_rdy),
                ]
                with m.If(number.done):
                    m.next = "suffix"
                    m.d.comb += [suffix.en.eq(Const(1)), ]
            with m.State("suffix"):
                m.next = "suffix"
                m.d.comb += [
                    output_fifo.w_en.eq(suffix.output.valid),
                    output_fifo.w_data.eq(suffix.output.payload),
                    suffix.output.ready.eq(output_fifo.w_rdy),
                ]

                with m.If(suffix.done):
                    m.next = "idle"

        # : Naive version: just wire the output port to the FIFO.
        # ...I thought this wouldn't work but apparently it's fine?
        # At least if everything is in the same clock domain.
        m.d.comb += [
            output_fifo.r_en.eq(self.output.ready),
            self.output.payload.eq(output_fifo.r_data),
            self.output.valid.eq(output_fifo.r_rdy),
        ]

        return m
