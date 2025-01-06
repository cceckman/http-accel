import amaranth as am
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream, wiring
from capitalizer import Capitalizer


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
    request: HTTP10Request
        State of the HTTP session.

    input: Stream(8), input
        Input data stream, from the client to the server.
    output: Stream(8), output
        Output data stream, from the server to the client.

    """

    request: Out(HTTP10RequestSignature())
    input: In(stream.Signature(am.unsigned(8)))
    output: Out(stream.Signature(am.unsigned(8)))

    def elaborate(self, platform):
        m = am.Module()
        m.submodules.to_upper = to_upper = Capitalizer(to_upper=True)
        m.d.comb += to_upper.input.eq(self.input.i.payload)
        ready = self.request.ready.o
        request = self.request.request.i

        # Major FSM: request state.
        with m.FSM(name="request"):
            with m.State("reset"):
                m.d.comb += ready.eq(am.Const(1))
                with m.If(request):
                    m.next = "working"
                with m.Else():
                    m.next = "reset"
            with m.State("working"):
                m.d.comb += ready.eq(am.Const(1))
                with m.If(request):
                    # TODO: Inner FSM here, to actually do the work.
                    # May result in "closed" or "working".
                    m.next = "working"
                with m.Else():
                    m.next = "closed"
            with m.State("closed"):
                m.d.comb += ready.eq(am.Const(0))
                with m.If(request):
                    m.next = "closed"
                with m.Else():
                    m.next = "reset"

        return m
