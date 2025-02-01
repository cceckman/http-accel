from amaranth import Module, Signal, Array, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream, fifo, memory
from .string_alt_match import StringAltMatch
from .string_match import StringMatch


class HttpMatch(Component):
    """
    Matches an HTTP/1 request line:
    <method> <path> <version>

    Attributes
    ----------
    input:      Stream(8), in
                Data stream to match.
    accepted:   Out(1)
                If the input stream matches an HTTP request line.
    rejected:   Out(1)
                If the input stream does not match an HTTP request line.
    """

    def __init__(self):
        super().__init__()

    input: In(stream.Signature(8))
    accepted: Out(1)
    rejected: Out(1)

    def elaborate(self, platform):
        m = Module()

        m.submodules.method = method = fifo.SyncFIFOBuffered(width=8, depth=10)
        # Fomu in theory has 512x8 memories, but we're only going to use half
        # in case synthesis doesn't know how to make it work
        m.submodules.path = path = fifo.SyncFIFOBuffered(width=8, depth=256)
        m.submodules.version = version = StringAltMatch([
            StringMatch("HTTP/1.0\r\n"),
            StringMatch("HTTP/1.1\r\n"),
        ])
        input = self.input

        with m.FSM():
            with m.State("method"):
                m.next = "method"
                with m.If(input.valid & (input.payload == ord(' '))):
                    m.next = "path"
                    m.d.comb += input.ready.eq(1)
                with m.Elif(~method.w_rdy):
                    m.next = "error"
                with m.Else():
                    m.d.comb += input.ready.eq(method.w_rdy)
                    m.d.comb += method.w_data.eq(input.payload)
                    m.d.comb += method.w_en.eq(input.valid)
            with m.State("path"):
                m.next = "path"
                with m.If(input.valid & (input.payload == ord(' '))):
                    m.next = "version"
                    m.d.comb += input.ready.eq(1)
                with m.Elif(~path.w_rdy):
                    m.next = "error"
                with m.Else():
                    m.d.comb += input.ready.eq(path.w_rdy)
                    m.d.comb += path.w_data.eq(input.payload)
                    m.d.comb += path.w_en.eq(input.valid)
            with m.State("version"):
                m.d.comb += [
                    input.ready.eq(version.input.ready),
                    version.input.valid.eq(input.valid),
                    version.input.payload.eq(input.payload),
                    self.accepted.eq(version.accepted),
                    self.rejected.eq(version.rejected),
                ]
                with m.If(version.accepted):
                    m.next = "done"
                with m.Elif(version.rejected):
                    m.next = "error"
                with m.Else():
                    m.next = "version"
            with m.State("error"):
                m.next = "error"
                m.d.comb += self.rejected.eq(Const(1))
            with m.State("done"):
                m.next = "done"
                m.d.comb += self.accepted.eq(1)

        return m
