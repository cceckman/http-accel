from amaranth import Module
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

from .string_contains_match import StringContainsMatch
import stream_utils


class ParseStart(Component):
    """
    Parser for the start-line of an HTTP request.

    Parameters
    ----------
    paths: list[str]
           Valid paths to match

    Attributes
    ----------
    input:    Stream(8), in
              Data stream to match
    reset:    Signal(1), in
              Reset and await new input
    done:     Signal(1), out
              Indicates that the "\r\n" end-of-line sequence was seen.
    method:   list(Signal(1)), out
              Bitfield of matched methods. The 0th field indicates no match.
              METHOD_* constants can be used for decode.
    path:     list(Signal(1)), out
              Bitfield of matched paths. The 0th field indicates no match.
              Other matches are in the order from the paths parameter.
    protocol: list(Siganl(1)), out
              Bitfield of matched protocol. The 0th field indicates no match.
              PROTOCOL_* constants can be used for decode.
    """

    METHOD_NO_MATCH = 0
    METHOD_GET = 1
    METHOD_POST = 2

    PROTOCOL_NO_MATCH = 0
    PROTOCOL_HTTP1_0 = 1

    def __init__(self, paths):
        super().__init__({
            "input": In(stream.Signature(8)),
            "reset": In(1),
            "done": Out(1),
            "method": Out(3),
            "path": Out(len(paths)+1),
            "protocol": Out(2),
        })
        self._paths = paths

    def elaborate(self, _platform):
        m = Module()

        resets = []

        # TODO: #4 - Evaluate using StringMatch instead of StringContainsMatch. Here and below.
        #            Check https://en.wikipedia.org/wiki/HTTP_request_smuggling cases.
        method_stream = stream.Signature(8).create()
        get_matcher = m.submodules.get_matcher = StringContainsMatch("GET")
        resets.append(get_matcher.reset)
        m.d.comb += self.method[self.METHOD_GET].eq(get_matcher.accepted)

        post_matcher = m.submodules.post_matcher = StringContainsMatch("POST")
        resets.append(post_matcher.reset)
        m.d.comb += self.method[self.METHOD_POST].eq(post_matcher.accepted)

        any_method_match = stream_utils.tree_or(
            m, [get_matcher.accepted, post_matcher.accepted])
        m.d.comb += self.method[0].eq(~any_method_match)

        stream_utils.fanout_stream(
            m, method_stream, [get_matcher.input, post_matcher.input])

        path_stream = stream.Signature(8).create()
        path_streams = []
        path_match = []
        for i, path in enumerate(self._paths):
            matcher = m.submodules[f"path_matchers_{i}"] = StringContainsMatch(
                path)
            path_streams.append(matcher.input)
            resets.append(matcher.reset)
            m.d.comb += self.path[i+1].eq(matcher.accepted)
            path_match.append(matcher.accepted)
        stream_utils.fanout_stream(m, path_stream, path_streams)
        any_path_match = stream_utils.tree_or(m, path_match)
        m.d.comb += self.path[0].eq(~any_path_match)

        # TODO: #4 - If we want to get out of the stone age, should match more than HTTP/1.0
        #            That being said, silicon is kind of like a stone, right?
        protocol_match = m.submodules.protocol_match = StringContainsMatch(
            "HTTP/1.0")
        m.d.comb += self.protocol[self.PROTOCOL_NO_MATCH].eq(
            ~protocol_match.accepted)
        m.d.comb += self.protocol[self.PROTOCOL_HTTP1_0].eq(
            protocol_match.accepted)

        with m.FSM():
            with m.State("reset"):
                for r in resets:
                    m.d.sync += r.eq(1)
                m.d.sync += self.done.eq(0)
                m.next = "match_method"
            with m.State("match_method"):
                m.next = "match_method"
                for r in resets:
                    m.d.sync += r.eq(0)
                m.d.comb += [
                    method_stream.valid.eq(self.input.valid),
                    method_stream.payload.eq(self.input.payload),
                    self.input.ready.eq(method_stream.ready),
                ]
                with m.If(self.input.valid & (self.input.payload == ord(' '))):
                    m.d.comb += self.input.ready.eq(1)
                    m.next = "match_path"
            with m.State("match_path"):
                m.next = "match_path"
                m.d.comb += [
                    path_stream.valid.eq(self.input.valid),
                    path_stream.payload.eq(self.input.payload),
                    self.input.ready.eq(path_stream.ready),
                ]
                with m.If(self.input.valid & (self.input.payload == ord(' '))):
                    m.d.comb += self.input.ready.eq(1)
                    m.next = "match_protocol"
            with m.State("match_protocol"):
                m.next = "match_protocol"
                # connect results in warning about combinatorial signals
                m.d.comb += [
                    protocol_match.input.valid.eq(self.input.valid),
                    protocol_match.input.payload.eq(self.input.payload),
                    self.input.ready.eq(protocol_match.input.ready),
                ]
                with m.If(self.input.valid & (self.input.payload == ord('\r'))):
                    m.d.comb += self.input.ready.eq(1)
                    m.next = "match_end"
            with m.State("match_end"):
                m.d.comb += self.input.ready.eq(1)
                m.next = "match_end"
                # TODO: #4 - Should error if this isn't \n, and setup to return a
                # HTTP 400 Bad Request error.
                with m.If(self.input.valid & (self.input.payload == ord('\n'))):
                    m.next = "done"
            with m.State("done"):
                m.next = "done"
                m.d.sync += self.done.eq(1)

        return m
