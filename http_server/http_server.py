from amaranth import Const, unsigned, Module
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream, wiring
try:
    from up_counter import UpCounter
    from number import Number
    from printer import Printer
except ImportError:
    from .up_counter import UpCounter
    from .number import Number
    from .printer import Printer


class HTTP10RequestSignature(wiring.Signature):
    """
    Handshake around an HTTP request.

    HTTP 1.0 is designed to operate over a TCP connection,
    without streaming: one request per connection.
    This allows for the simplified assumption that
    each data stream constitutes a full request;
    since the data stream is not self-synchronizing, a server
    must be able to terminate a request early.

    The flow is as follows:
    - Server asserts ready
    - Client asserts request (after server asserts ready)
    - Data transfers through input and output streams
    - Server deasserts ready when response is complete.
        (Server may any data received from client.)
    - Client deasserts request (optionally after flushing its own data)
    - Serve asserts ready

    request=0,ready=0 is the "mutual reset" condition.

    Attributes
    ----------
    ready: Signal(1), output
        Server is ready to receive a new request / the current request.
    request: Signal(1), input
        Client has a request to send.
    """

    ready: Out(1)
    request: In(1)


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

        # Stub server: repeats a second count at 1Hz.
        m.submodules.tick_counter = tick_counter = UpCounter(freq)
        m.submodules.second_counter = second_counter = UpCounter(SECOND_MAX)
        m.d.comb += [
            tick_counter.en.eq(Const(1)),
            second_counter.en.eq(tick_counter.ovf)
        ]

        m.submodules.number = number = Number(SECOND_WIDTH)
        m.submodules.suffix = suffix = Printer(" seconds since startup\r\n")

        m.d.comb += [
            # Ready when the output channel is ready:
            number.output.ready.eq(self.output.ready),
            suffix.output.ready.eq(self.output.ready),
        ]

        # Numeric input from the counter:
        m.d.comb += number.input.eq(second_counter.count)

        # And deal with state:
        m.d.sync += [
            number.en.eq(Const(0)), suffix.en.eq(Const(0)),
        ]
        m.d.comb += [
            self.output.valid.eq(Const(0)),
            self.output.payload.eq(Const(0)),
        ]
        with m.FSM():
            with m.State("idle"):
                m.next = "idle"
                with m.If(tick_counter.ovf):
                    m.d.sync += [
                        number.en.eq(Const(1)),
                    ]
                    m.next = "number"

            with m.State("number"):
                m.next = "number"
                m.d.comb += [
                    self.output.valid.eq(number.output.valid),
                    self.output.payload.eq(number.output.payload),
                ]
                with m.If(~number.en & number.done):
                    m.next = "suffix"
                    m.d.sync += [
                        suffix.en.eq(Const(1)),
                    ]
            with m.State("suffix"):
                m.next = "suffix"
                m.d.comb += [
                    self.output.valid.eq(suffix.output.valid),
                    self.output.payload.eq(suffix.output.payload),
                ]

                with m.If(~suffix.en & suffix.done):
                    m.next = "idle"

        return m
