from amaranth.sim import Simulator

from .host import Packet, Flag
from .not_tcp import StreamStop
from stream_fixtures import StreamSender, StreamCollector


def test_single_stop():
    dut = StreamStop(2)

    sim = Simulator(dut)
    # Passively collect the data that comes in to this stop:
    collect_stop = StreamCollector(dut.stop.inbound.data)
    sim.add_process(collect_stop.collect())
    # And the data that continues on the bus:
    collect_bus = StreamCollector(dut.bus.downstream)
    sim.add_process(collect_bus.collect())

    # Provide senders for "upstream on the bus" and "from this stop"
    send_stop = StreamSender(dut.stop.outbound.data)
    send_bus = StreamSender(dut.bus.upstream)

    # The packet sequence we'll use:
    # Host-to-device, starting stream 2
    p1 = Packet(flags=Flag.START, stream_id=2,
                body=bytes(i for i in range(0, 10)))
    # Host-to-device, starting and ending stream 3
    p2 = Packet(flags=Flag.START | Flag.END, stream_id=3,
                body=bytes(i for i in range(10, 15)))
    # Host-to-device, middle of stream 2
    p3 = Packet(stream_id=2, body=bytes(i for i in range(15, 18)))
    # # device-to-host, stream 2; start and end markers, it's all the data
    p4_body = bytes(i for i in range(18, 28))
    # host-to-device, stream 2: end marker only
    p5 = Packet(flags=Flag.END, stream_id=2, body=bytes())

    async def driver(ctx):
        # Just the header for p1 should start the stream:
        await send_bus.send_active(p1.header().to_bytes())(ctx)
        await ctx.tick().until(dut.stop.inbound.active)
        # Accept the stream:
        ctx.set(dut.stop.outbound.active, 1)
        # And finish p1's body
        await send_bus.send_active(p1.body)(ctx)

        # Feed in p2:
        await send_bus.send_active(p2.to_bytes())(ctx)
        # # and p3:
        await send_bus.send_active(p3.to_bytes())(ctx)
        # # Send p4 on the return path:
        await send_stop.send_active(p4_body)(ctx)
        # And mark the stream as closed:
        ctx.set(dut.stop.outbound.active, 0)
        #
        # # And then send p5 to hang up the inbound path:
        await send_bus.send_active(p5.to_bytes())(ctx)
        #
        # Wait for everything to be flushed:
        await ctx.tick().until(~dut.connected)

        assert ctx.get(~dut.stop.inbound.active)
        assert ctx.get(~dut.bus.downstream.valid)

    sim.add_testbench(driver)
    sim.add_clock(1e-6)

    sim.run()

    # After simulation is complete...
    # The stop should have received all the packets for this stream:
    collect_stop.assert_eq(
        p1.body + p3.body + p5.body
    )
    # And should have received _bodies equivalent to_ the full p4 stream.
    # TODO: Consider forwarding around the bus, too.
    rcvd = collect_bus.body
    packets = []
    while len(rcvd) > 0:
        # All data should be packetized.
        (p, remainder) = Packet.from_bytes(rcvd)
        assert p is not None, f"remaining data: {rcvd}"
        packets += [p]
        rcvd = remainder
    bodies = bytes()
    for i in range(len(packets)):
        packet = packets[i]
        assert packet.stream_id == 2
        assert packet.to_host
        assert packet.start == (i == 0), f"start {packet.start} for packet {i}"
        assert packet.end == (
            i == len(packets)-1), f"end {packet.end} for packet {i}"
        assert packet.to_host

        bodies += packet.body

    assert bodies == p4_body
