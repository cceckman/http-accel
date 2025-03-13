from amaranth import Module, Const
from amaranth.lib.wiring import In, Out, Component, connect

from printer import Printer
from stream_mux import StreamMux

import session


class SimpleLedHttp(Component):
    """
    SimpleLedHttp accepts an HTTP/1.0 request to change LED colors.

    Returns an HTTP OK status if accpeted.

    Expects a POST to the /led path with a body containing 8 hex
    characters corresponding to red, green, and blue LED values.

    Attributes
    ----------
    session: BidiSessionSignature
        Input and output streams & session indicators

    red:      Signal(8), out
    green:    Signal(8), out
    blue:     Signal(8), out
              r/g/b values to send to LEDs.

    """

    session: In(session.BidiSessionSignature())
    red: Out(8)
    green: Out(8)
    blue: Out(8)

    def elaborate(self, _platform):
        m = Module()

        response_mux = m.submodules.response_mux = StreamMux(mux_width=2, stream_width=8)
        connect(m, response_mux.out, self.session.outbound.data)

        ok_response = "\r\n".join(
            ["HTTP/1.0 200 OK",
             "Host: Fomu",
             "Content-Type: text/plain; charset=utf-8",
             "",
             "",
             '👍']) + "\r\n"
        ok_response = ok_response.encode("utf-8")
        ok_printer = m.submodules.ok_printer = Printer(ok_response)
        connect(m, ok_printer.output, response_mux.input[0])

        not_found_response = "\r\n".join(
            ["HTTP/1.0 404 Not Found",
             "Host: Fomu",
             "Content-Type: text/plain; charset=utf-8",
             "",
             "",
             '👎']) + "\r\n"
        not_found_response = not_found_response.encode("utf-8")
        not_found_printer = m.submodules.not_found_printer = Printer(not_found_response)
        connect(m, not_found_printer.output, response_mux.input[1])

        m.d.comb += response_mux.select.eq(0)

        with m.FSM():
            with m.State("idle"):
                m.next = "idle"
                with m.If(self.session.inbound.active):
                    m.next = "parsing"
                    m.d.sync += self.session.outbound.active.eq(1)
            with m.State("parsing"):
                m.d.sync += self.session.outbound.active.eq(1)
                m.next = "parsing"
                # Consume inbound data (drop it on the floor)
                m.d.comb += self.session.inbound.data.ready.eq(1)
                with m.If(~self.session.inbound.active):
                    # All the input is done.
                    # TODO: #3 -- we should make this state transition
                    # when we have completed reading the request
                    # OR if the inbound session becomes inactive.
                    m.next = "writing"
                    m.d.sync += ok_printer.en.eq(1)  # one-shot
            with m.State("writing"):
                m.d.sync += ok_printer.en.eq(0)
                m.d.sync += self.session.outbound.active.eq(1)
                m.next = "writing"
                with m.If(ok_printer.done):
                    m.next = "idle"
                    m.d.sync += self.session.outbound.active.eq(0)

        # TODO: #3 - Implement for real. Currently has a sync block so simple_led_http_test
        # will elaborate.
        m.d.sync += [
            self.red.eq(self.session.inbound.data.payload)
        ]

        return m
        return m
