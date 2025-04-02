import asyncio
import pytest

from amaranth import Module
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib import stream

from host_sim import HostSimulator
from http_server import capitalizer
from not_tcp.host import Packet, Flag
from not_tcp.not_tcp import StreamStop
from ntcp_http import NtcpHttpServer
from sim_server import SimServer


pytest_plugins = ('pytest_asyncio',)


class Capitalize(Component):
    """
    A Not TCP server that capitalizes its input.
    """

    tx: Out(stream.Signature(8))
    rx: In(stream.Signature(8))

    def elaborate(self, platform):
        m = Module()

        stop = m.submodules.stop = StreamStop(1)
        # Serial side:
        m.d.comb += [
            self.tx.valid.eq(stop.bus.downstream.valid),
            self.tx.payload.eq(stop.bus.downstream.payload),
            stop.bus.downstream.ready.eq(self.tx.ready),

            stop.bus.upstream.valid.eq(self.rx.valid),
            stop.bus.upstream.payload.eq(self.rx.payload),
            self.rx.ready.eq(stop.bus.upstream.ready),
        ]

        cap = m.submodules.capitalizer = capitalizer.Capitalizer()

        m.d.comb += [
            # Data:
            cap.input.eq(stop.stop.inbound.data.payload),
            stop.stop.outbound.data.payload.eq(cap.output),
            # Stream control:
            stop.stop.outbound.data.valid.eq(stop.stop.inbound.data.valid),
            stop.stop.inbound.data.ready.eq(stop.stop.outbound.data.ready),
            # Session control:
            stop.stop.outbound.active.eq(stop.stop.inbound.active),
        ]

        return m


def DISABLED_test_capitalize_server():
    dut = Capitalize()

    with SimServer(dut, dut.tx, dut.rx) as srv:
        p1 = Packet(flags=Flag.START, stream_id=1, body=b"hello world")
        srv.send(p1.to_bytes())

        received_bytes = bytes()
        received_body = bytes()
        packets = []
        for i in range(100):
            received_bytes += srv.recv()
            (packet, remainder) = Packet.from_bytes(received_bytes)
            if packet is not None:
                received_bytes = remainder
                packets += [packet]
                received_body += packet.body
                if packet.end or len(received_body) == len("hello world"):
                    break
        assert received_body == b"HELLO WORLD"

        received_body = bytes()
        # TODO: For now, we have to send an explicit "end" packet
        p2 = Packet(stream_id=1, body=b"Goodbye for now")
        p3 = Packet(flags=Flag.END, stream_id=1)
        srv.send(p2.to_bytes())
        srv.send(p3.to_bytes())
        for i in range(100):
            received_bytes += srv.recv()
            (packet, remainder) = Packet.from_bytes(received_bytes)
            if packet is not None:
                received_bytes = remainder
                packets += [packet]
                received_body += packet.body
                if packet.end:
                    break
        assert received_body == b"GOODBYE FOR NOW"

        for i in range(len(packets)):
            packet = packets[i]
            assert packet.to_host
            assert packet.start == (
                i == 0), f"start {packet.start} for packet {i}"
            assert packet.end == (
                i == len(packets)-1), f"end {packet.end} for packet {i}"
            assert packet.to_host


@pytest.mark.asyncio
async def test_tcp_proxy():
    dut = NtcpHttpServer()

    with HostSimulator(dut, dut.tx, dut.rx) as srv:
        server = await asyncio.start_server(
            client_connected_cb=srv.client_connected, host="localhost",
            port=3278)
        async with server:
            reader, writer = await asyncio.open_connection("127.0.0.1", 3278)
            writer.write(
                "\r\n".join([
                    "POST /nothing-here HTTP/1.0",
                    "Cache-Control: private",
                    "",
                    "",
                    "lovely day today"
                ]).encode("utf-8")
            )
            await writer.drain()

            read = await reader.read(-1)
        response = read.decode("utf-8")
        lines = response.split("\r\n")
        assert lines[0] == "HTTP/1.0 404 Not Found"
