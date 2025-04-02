
from amaranth.sim import Simulator

from not_tcp.host import Packet, Flag
from sim_server import SimServer
from ntcp_http import NtcpHttpServer
from stream_fixtures import StreamSender, StreamCollector


def test_sim_without_fixture():
    dut = NtcpHttpServer()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    sender = StreamSender(dut.rx)
    receiver = StreamCollector(dut.tx)

    request = (b"GET /unmapped HTTP/1.0\r\n"
               b"Content-Length: 3\r\n"
               b"\r\n"
               b"\r\n"
               b"123\r\n"
               )
    data = Packet(stream_id=1, flags=Flag.START | Flag.END, body=request)

    sim.add_process(sender.send_passive(data.to_bytes()))
    sim.add_process(receiver.collect())

    async def driver(ctx):
        # while not sender.done:
        #     await ctx.tick()
        # Arbitrary delay to flush output before exiting:
        for i in range(0, 4096):
            await ctx.tick()
    sim.add_testbench(driver)

    sim.run()


def test_sim():
    dut = NtcpHttpServer()

    with SimServer(dut, dut.tx, dut.rx) as srv:
        p1 = Packet(flags=Flag.START | Flag.END, stream_id=1,
                    body=(
                        b"GET /unmapped HTTP/1.0\r\n"
                        b"Content-Length: 3\r\n"
                        b"\r\n"
                        b"\r\n"
                        b"123\r\n"))
        srv.send(p1.to_bytes())

        received_bytes = bytes()
        packets = []
        # We shouldn't have more than 100 packets for this test.
        for i in range(100):
            received_bytes += srv.recv()
            (packet, remainder) = Packet.from_bytes(received_bytes)
            if packet is not None:
                received_bytes = remainder
                packets += [packet]
                if packet.end:
                    break

        packet_bodies = bytes()
        for i in range(len(packets)):
            packet = packets[i]
            assert packet.to_host
            assert packet.start == (
                i == 0), f"start {packet.start} for packet {i}"
            assert packet.end == (
                i == len(packets)-1), f"end {packet.end} for packet {i}"
            assert packet.to_host

            packet_bodies += packet.body
        response = packet_bodies.decode("utf-8")
        assert response.startswith("HTTP/1.0"), response
