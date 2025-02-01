from amaranth import Const, unsigned, Module, ClockDomain, DomainRenamer, Assert
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream
from amaranth.lib.cdc import PulseSynchronizer
from amaranth.lib.fifo import AsyncFIFO, SyncFIFOBuffered
from .http_match import HttpMatch

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
    request_match: Out(1)

    def elaborate(self, platform):
        m = Module()

        m.submodules.reqmatch = reqmatch = HttpMatch()
        m.submodules.accepted = accepted = Printer("ok\n")
        m.submodules.rejected = rejected = Printer("uh oh\n")
        output = self.output

        m.d.comb += [
            self.input.ready.eq(reqmatch.input.ready),
            reqmatch.input.payload.eq(self.input.payload),
            reqmatch.input.valid.eq(self.input.valid),
        ]

        with m.FSM():
            with m.State("idle"):
                m.next = "idle"
                with m.If(reqmatch.accepted):
                    m.next = "accepted"
                with m.If(reqmatch.rejected):
                    m.next = "rejected"

            with m.State("accepted"):
                m.next = "idle"
                m.d.comb += [
                    output.valid.eq(accepted.output.valid),
                    output.payload.eq(accepted.output.payload),
                    accepted.output.ready.eq(output.ready),
                ]

            with m.State("rejected"):
                m.next = "idle"
                m.d.comb += [
                    output.valid.eq(rejected.output.valid),
                    output.payload.eq(rejected.output.payload),
                    rejected.output.ready.eq(output.ready),
                ]

        return m
