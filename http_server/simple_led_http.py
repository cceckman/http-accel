from amaranth import Module
from amaranth.lib.wiring import In, Out, Component, connect

from printer import Printer

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

        response = "\r\n".join(
            ["HTTP/1.0 200 OK",
             "Host: Fomu",
             "Content-Type: text/plain; charset=utf-8",
             "",
             "",
             '👍']) + "\r\n"

        response = response.encode("utf-8")

        printer = m.submodules.printer = Printer(response)

        connect(m, printer.output, self.session.outbound.data)

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
                    m.d.sync += printer.en.eq(1)  # one-shot
            with m.State("writing"):
                m.d.sync += printer.en.eq(0)
                m.d.sync += self.session.outbound.active.eq(1)
                m.next = "writing"
                with m.If(printer.done):
                    m.next = "idle"
                    m.d.sync += self.session.outbound.active.eq(0)

        # TODO: #3 - Implement for real. Currently has a sync block so simple_led_http_test
        # will elaborate.
        m.d.sync += [
            self.red.eq(self.session.inbound.data.payload)
        ]

        return m
        return m
