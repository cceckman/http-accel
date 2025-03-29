from amaranth import Module
from amaranth.lib.wiring import In, Out, Component, connect

from .count_body import CountBody
from .parse_start import ParseStart
from .printer import Printer
from .simple_led_body import SimpleLedBody
from .stream_demux import StreamDemux
from .stream_mux import StreamMux
from .string_contains_match import StringContainsMatch

import session


class SimpleLedHttp(Component):
    """
    SimpleLedHttp accepts an HTTP/1.0 request to change LED colors.

    Returns an HTTP OK status if accpeted.

    Expects a POST to the /led path with a body containing 8 hex
    characters corresponding to red, green, and blue LED values.

    A GET from /count will return the number of requests and
    responses.

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

        MATCHED_LED_PATH = 1 # start_matcher path match is in the order the paths are connected.
        MATCHED_COUNT_PATH = 2
        MATCHED_COFFEE_PATH = 3
        start_matcher = m.submodules.start_matcher = ParseStart(["/led", "/count", "/coffee"])
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
        response_mux = m.submodules.response_mux = StreamMux(mux_width=5, stream_width=8)
        connect(m, response_mux.out, self.session.outbound.data)
        count_body = m.submodules.count_body = CountBody()

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
                count_body.inc_ok.eq(1),
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
                count_body.inc_error.eq(1),
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
                count_body.inc_error.eq(1),
        ]

        teapot_response = "\r\n".join(
                ["HTTP/1.0 418 I'm a teapot",
                    "Host: Fomu",
                    "Content-Type: text/plain; charset=utf-8",
                    "",
                    "",
                    "short and stout"]) + "\r\n"
        teapot_response = teapot_response.encode("utf-8")
        teapot_printer = m.submodules.teapot_printer = Printer(teapot_response)
        RESPONSE_TEAPOT = 3
        connect(m, teapot_printer.output, response_mux.input[RESPONSE_TEAPOT])
        send_teapot = [
                response_mux.select.eq(RESPONSE_TEAPOT),
                parser_demux.select.eq(HTTP_PARSER_SINK),
                teapot_printer.en.eq(1),
                count_body.inc_error.eq(1),
        ]

        RESPONSE_COUNT = 4
        connect(m, count_body.output, response_mux.input[RESPONSE_COUNT])
        send_count = [
                response_mux.select.eq(RESPONSE_COUNT),
                parser_demux.select.eq(HTTP_PARSER_SINK),
                count_body.en.eq(1),
        ]

        with m.FSM():
            with m.State("reset"):
                m.d.comb += [
                    start_matcher.reset.eq(1),
                    skip_headers.reset.eq(1),
                ]
                m.next = "idle"
            with m.State("idle"):
                m.d.comb += [
                    start_matcher.reset.eq(0),
                    skip_headers.reset.eq(0),
                ]
                m.d.sync += [
                    parser_demux.select.eq(HTTP_PARSER_START),
                    response_mux.select.eq(RESPONSE_OK),
                ]
                m.next = "idle"
                with m.If(self.session.inbound.active):
                    m.next = "parsing_start"
                    m.d.sync += [
                        self.session.outbound.active.eq(1),
                        count_body.inc_requests.eq(1),
                    ]
            with m.State("parsing_start"):
                m.next = "parsing_start"
                m.d.sync += count_body.inc_requests.eq(0)
                # start line matched successfully
                with m.If(start_matcher.done):
                    m.next = "parsing_header"
                    m.d.sync += parser_demux.select.eq(HTTP_PARSER_HEADERS)
            with m.State("parsing_header"):
                m.next = "parsing_header"
                with m.If(skip_headers.accepted):
                    with m.If(start_matcher.path[MATCHED_LED_PATH]):
                        with m.If(start_matcher.method[start_matcher.METHOD_POST]):
                            m.next = "parsing_led_body"
                            m.d.sync += parser_demux.select.eq(HTTP_PARSER_LED_BODY)
                        with m.Else():
                            m.next = "writing"
                            m.d.sync += send_405
                    with m.Elif(start_matcher.path[MATCHED_COUNT_PATH]):
                        with m.If(start_matcher.method[start_matcher.METHOD_GET]):
                            m.next = "writing_count_ok"
                            m.d.sync += send_ok
                        with m.Else():
                            m.next = "writing"
                            m.d.sync += send_405
                    with m.Elif(start_matcher.path[MATCHED_COFFEE_PATH]):
                        with m.If(start_matcher.method[start_matcher.METHOD_GET] 
                                  | start_matcher.method[start_matcher.METHOD_BREW]): 
                            m.next = "writing"
                            m.d.sync += send_teapot
                        with m.Else():
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
            with m.State("writing_count_ok"):
                m.next = "writing_count_ok"
                m.d.sync += [
                    ok_printer.en.eq(0),
                    count_body.inc_ok.eq(0)
                ]
                with m.If(ok_printer.done):
                    m.d.sync += send_count
                    m.next = "writing"
            with m.State("writing"):
                m.next = "writing"
                m.d.sync += [
                        ok_printer.en.eq(0),
                        not_found_printer.en.eq(0),
                        not_allowed_printer.en.eq(0),
                        teapot_printer.en.eq(0),
                        count_body.en.eq(0),
                        self.session.outbound.active.eq(1),
                        count_body.inc_ok.eq(0),
                        count_body.inc_error.eq(0),
                ]
                with m.If(  ((response_mux.select == RESPONSE_OK) & ok_printer.done)
                          | ((response_mux.select == RESPONSE_404) & not_found_printer.done)
                          | ((response_mux.select == RESPONSE_405) & not_allowed_printer.done)
                          | ((response_mux.select == RESPONSE_COUNT) & count_body.done)
                          | ((response_mux.select == RESPONSE_TEAPOT) & teapot_printer.done)):
                    m.d.sync += self.session.outbound.active.eq(0)
                    # Can finish writing before all the input is collected,
                    # since a bad request migh trigger an early 404. Wait
                    # until the input is done before returning to the reset
                    # state.
                    with m.If(~self.session.inbound.active):
                        m.next = "reset"

        return m
