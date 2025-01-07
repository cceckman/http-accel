from amaranth import Const, unsigned, Module, ClockDomain, DomainRenamer
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream
from amaranth.lib.cdc import PulseSynchronizer
from amaranth.lib.fifo import AsyncFIFO

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

        # Propagate that tick into the "slow" (server) clock domain.
        m.domains.server = server = ClockDomain("server", local=True)
        # m.domains.server = m.domains.sync.rename("server")
        in_server = DomainRenamer({"sync": "server"})
        # It looks like a clock domain doesn't get driven
        # unless you tell it to be?
        # You can't just say "make this some frequency that meets timings?"
        # Or maybe you can, but I'm not seeing the API for it.
        # This runs the clock specifically at half the USB clock.
        m.d.sync += server.clk.eq(~server.clk)
        # In any case, I can indeed specify the clock constraint here --
        # or let it free and just take whatever.
        # try:
        #     platform.add_clock_constraint(server.clk, 1e9)
        # except AttributeError:
        #     # Can't set the clock constraint, e.g. on the simulator
        #     pass
        m.submodules.tick = tick = PulseSynchronizer(
            i_domain="sync", o_domain="server")

        m.d.comb += [
            tick.i.eq(tick_counter.ovf),
            self.tick.eq(tick_counter.ovf),
        ]

        # In the server domain, run a counter of elapsed seconds.
        m.submodules.second_counter = second_counter = in_server(
            UpCounter(SECOND_MAX))
        m.d.comb += [second_counter.en.eq(tick.o), ]

        m.submodules.number = number = in_server(Number(SECOND_WIDTH))
        m.submodules.suffix = suffix = in_server(
            Printer(" seconds since startup\r\n"))

        # All output goes through a FIFO for reclocking.
        m.submodules.output_fifo = output_fifo = AsyncFIFO(
            w_domain="server", r_domain="sync", width=8, depth=4)

        m.d.comb += [
            # Ready when the FIFO has space:
            number.output.ready.eq(output_fifo.w_rdy),
            suffix.output.ready.eq(output_fifo.w_rdy),
            output_fifo.w_en.eq(Const(0)),
            output_fifo.w_data.eq(Const(0)),
        ]

        # Print the appropriate section of the message:
        m.d.server += [number.en.eq(Const(0)), suffix.en.eq(Const(0))]
        with m.FSM(domain="server"):
            with m.State("idle"):
                m.next = "idle"
                with m.If(tick_counter.ovf):
                    m.d.server += [
                        number.en.eq(Const(1)),
                    ]
                    m.next = "number"

            with m.State("number"):
                m.next = "number"
                m.d.comb += [
                    output_fifo.w_en.eq(number.output.valid),
                    output_fifo.w_data.eq(number.output.payload),
                ]
                with m.If(~number.en & number.done):
                    m.next = "suffix"
                    m.d.server += [
                        suffix.en.eq(Const(1)),
                    ]
            with m.State("suffix"):
                m.next = "suffix"
                m.d.comb += [
                    output_fifo.w_en.eq(suffix.output.valid),
                    output_fifo.w_data.eq(suffix.output.payload),
                ]

                with m.If(~suffix.en & suffix.done):
                    m.next = "idle"

        # If the output is ready,
        m.d.comb += output_fifo.r_en.eq(self.output.ready)
        # On the next cycle, that data is available:
        m.d.sync += self.output.payload.eq(output_fifo.r_data)
        # And we can mark it availabe:
        m.d.sync += self.output.valid.eq(self.output.ready & output_fifo.r_rdy)

        return m
