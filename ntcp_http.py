from amaranth.lib.wiring import connect, Component, In, Out
from amaranth.lib import stream
from amaranth import Module
from not_tcp.not_tcp import StreamStop
from http_server.simple_led_http import SimpleLedHttp


class NtcpHttpServer(Component):
    """
    A serial-to-HTTP server, suitable for synthesis.
    """

    tx: Out(stream.Signature(8))
    rx: In(stream.Signature(8))

    red: Out(8)
    green: Out(8)
    blue: Out(8)

    def elaborate(self, platform):
        m = Module()

        # Packet bus:
        # Just a single stream processor for now.
        # the bus doesn't properly handle multiple stops.
        stop = m.submodules.ntcp_stop = StreamStop(stream_id=1)
        m.d.comb += [
            self.tx.valid.eq(stop.bus.downstream.valid),
            self.tx.payload.eq(stop.bus.downstream.payload),
            stop.bus.downstream.ready.eq(self.tx.ready),

            stop.bus.upstream.valid.eq(self.rx.valid),
            stop.bus.upstream.payload.eq(self.rx.payload),
            self.rx.ready.eq(stop.bus.upstream.ready),
        ]

        # Actual HTTP processing:
        http = m.submodules.http = SimpleLedHttp()

        # There's something funky going on with the session lines;
        # connect() should work, but it doesn't.
        # If we do the connections manually, the simulator hangs on cycle 4.

        # On its own, this doesn't work; the active lines don't get connected.
        # connect(m, stop.stop, http.session)
        # So let's try connecting the session-active lines manually:
        m.d.comb += [
            http.session.inbound.active.eq(stop.stop.inbound.active),
            http.session.inbound.data.payload.eq(
                stop.stop.inbound.data.payload),
            http.session.inbound.data.valid.eq(stop.stop.inbound.data.valid),
            stop.stop.inbound.data.ready.eq(http.session.inbound.data.ready),

            stop.stop.outbound.active.eq(http.session.outbound.active),
            stop.stop.outbound.data.payload.eq(
                http.session.outbound.data.payload),
            stop.stop.outbound.data.valid.eq(http.session.outbound.data.valid),
            http.session.outbound.data.ready.eq(stop.stop.outbound.data.ready),
        ]

        m.d.comb += [
            self.red.eq(http.red),
            self.green.eq(http.green),
            self.blue.eq(http.blue),
        ]

        return m
