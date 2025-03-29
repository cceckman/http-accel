
from amaranth import Module
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib import stream

from not_tcp.host import Packet, Flag
from sim_server import SimServer
from not_tcp.not_tcp import StreamStop
from http_server import capitalizer


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


def test_capitalize_server():
    dut = Capitalize()

    with SimServer(dut, dut.tx, dut.rx) as srv:
        p1 = Packet(flags=Flag.START, stream_id=1, body=b"hello world")
        srv.send(p1.to_bytes())

        received_bytes = bytes()
        received_body = bytes()
        packets = []
        import sys
        for i in range(100):
            received_bytes += srv.recv()
            (packet, remainder) = Packet.from_bytes(received_bytes)
            if packet is not None:
                sys.stderr.write(f"{packet}\n")
                received_bytes = remainder
                packets += [packet]
                received_body += packet.body
                if packet.end or len(received_body) == len("hello world"):
                    break
        assert received_body == b"HELLO WORLD"

        received_body = bytes()
        p2 = Packet(flags=Flag.END, stream_id=1, body=b"Goodbye for now")
        srv.send(p2.to_bytes())
        for i in range(100):
            received_bytes += srv.recv()
            (packet, remainder) = Packet.from_bytes(received_bytes)
            if packet is not None:
                sys.stderr.write(f"{packet}\n")
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
