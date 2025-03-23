from amaranth import Module, Const
from amaranth.lib.wiring import In, Out, Component, connect

from printer import Printer
from parse_start import ParseStart
from stream_mux import StreamMux
from stream_demux import StreamDemux
from string_match import StringMatch
from string_contains_match import StringContainsMatch
from simple_led_body import SimpleLedBody

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

        ## Input parsers
        parser_demux = m.submodules.parser_demux = StreamDemux(mux_width=4, stream_width=8)
        connect(m, self.session.inbound.data, parser_demux.input)

        # TODO: #4 - Add packet count and RFC2324 endpoints
        MATCHED_LED_PATH = 1 # start_matcher path match is in the order the paths are returned.
        start_matcher = m.submodules.start_matcher = ParseStart(["/led"])
        HTTP_PARSER_START = 0
        connect(m, start_matcher.input, parser_demux.outs[HTTP_PARSER_START])

        HTTP_PARSER_HEADERS = 1
        skip_headers = m.submodules.end_of_header_matcher = StringContainsMatch("\r\n\r\n")
        connect(m, skip_headers.input, parser_demux.outs[HTTP_PARSER_HEADERS])

        HTTP_PARSER_LED_BODY = 2
        led_body_handler = m.submodules.led_body_handler = SimpleLedBody()
        connect(m, led_body_handler.input, parser_demux.outs[HTTP_PARSER_LED_BODY])
        m.d.comb += [
                self.red.eq(led_body_handler.red),
                self.green.eq(led_body_handler.green),
                self.blue.eq(led_body_handler.blue),
                ]

        # Last parser is just a sink
        HTTP_PARSER_SINK = 3
        m.d.comb += parser_demux.outs[HTTP_PARSER_SINK].ready.eq(1)

        ## Responders
        response_mux = m.submodules.response_mux = StreamMux(mux_width=3, stream_width=8)
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
        RESPONSE_OK = 0
        connect(m, ok_printer.output, response_mux.input[RESPONSE_OK])
        send_ok = [
                response_mux.select.eq(RESPONSE_OK),
                parser_demux.select.eq(HTTP_PARSER_SINK),
                ok_printer.en.eq(1),
        ]

        not_found_response = "\r\n".join(
                ["HTTP/1.0 404 Not Found",
                    "Host: Fomu",
                    "Content-Type: text/plain; charset=utf-8",
                    "",
                    "",
                    '👎']) + "\r\n"
        not_found_response = not_found_response.encode("utf-8")
        not_found_printer = m.submodules.not_found_printer = Printer(not_found_response)
        RESPONSE_404 = 1
        connect(m, not_found_printer.output, response_mux.input[RESPONSE_404])
        send_404 = [
                response_mux.select.eq(RESPONSE_404),
                parser_demux.select.eq(HTTP_PARSER_SINK),
                not_found_printer.en.eq(1),
        ]

        not_allowed_response = "\r\n".join(
                ["HTTP/1.0 405 Method Not Allowed",
                    "Host: Fomu",
                    "Content-Type: text/plain; charset=utf-8",
                    "",
                    "",
                    '🛑']) + "\r\n"
        not_allowed_response = not_allowed_response.encode("utf-8")
        not_allowed_printer = m.submodules.not_allowed_printer = Printer(not_allowed_response)
        RESPONSE_405 = 2
        connect(m, not_allowed_printer.output, response_mux.input[RESPONSE_405])
        send_405 = [
                response_mux.select.eq(RESPONSE_405),
                parser_demux.select.eq(HTTP_PARSER_SINK),
                not_allowed_printer.en.eq(1),
        ]


        with m.FSM():
            with m.State("reset"):
                m.d.comb += [
                        start_matcher.reset.eq(1),
                        skip_headers.reset.eq(1),
                        led_body_handler.reset.eq(1),
                ]
                m.next = "idle"
            with m.State("idle"):
                m.d.comb += start_matcher.reset.eq(0)
                m.d.sync += parser_demux.select.eq(HTTP_PARSER_START)
                m.d.sync += response_mux.select.eq(RESPONSE_OK)
                m.next = "idle"
                with m.If(self.session.inbound.active):
                    m.next = "parsing_start"
                    m.d.sync += self.session.outbound.active.eq(1)
            with m.State("parsing_start"):
                m.next = "parsing_start"
                # start line matched successfully
                with m.If(start_matcher.done):
                    m.next = "parsing_header"
                    m.d.sync += parser_demux.select.eq(HTTP_PARSER_HEADERS)
            with m.State("parsing_header"):
                m.next = "parsing_header"
                with m.If(skip_headers.accepted):
                    with m.If(start_matcher.method[start_matcher.METHOD_POST] & 
                              start_matcher.path[MATCHED_LED_PATH]):
                        m.next = "parsing_led_body"
                        m.d.sync += parser_demux.select.eq(HTTP_PARSER_LED_BODY)
                    with m.Elif(start_matcher.method[start_matcher.METHOD_GET] & 
                              start_matcher.path[MATCHED_LED_PATH]):
                        m.next = "writing"
                        m.d.sync += send_405
                    with m.Else():
                        m.next = "writing"
                        m.d.sync += send_404
                with m.Elif(~self.session.inbound.active):
                    m.next = "writing"
                    # TODO: #4 - Should send a different error code besides 404 if the
                    #            headers fail to parse before end-of-session.
                    m.d.sync += send_404
            with m.State("parsing_led_body"): # TODO: #4 - Make body parsing state more generic.
                m.next = "parsing_led_body"
                with m.If(led_body_handler.accepted):
                    m.next = "writing"
                    m.d.sync += send_ok
                with m.Elif(led_body_handler.rejected):
                    m.next = "writing"
                    # TODO: #4 - Should send a different error code besides 404 if the
                    #            body fails to parse before end-of-session.
                    m.d.sync += send_404
            with m.State("writing"):
                m.next = "writing"
                m.d.sync += [
                        ok_printer.en.eq(0),
                        not_found_printer.en.eq(0),
                        not_allowed_printer.en.eq(0),
                        self.session.outbound.active.eq(1),
                ]
                with m.If(  ((response_mux.select == RESPONSE_OK) & ok_printer.done)
                          | ((response_mux.select == RESPONSE_404) & not_found_printer.done)
                          | ((response_mux.select == RESPONSE_405) & not_allowed_printer.done)):
                    m.d.sync += self.session.outbound.active.eq(0)
                    # Can finish writing before all the input is collected,
                    # since a bad request migh trigger an early 404. Wait
                    # until the input is done before returning to the reset
                    # state.
                    with m.If(~self.session.inbound.active):
                        m.next = "reset"

        return m
