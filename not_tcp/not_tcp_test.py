import sys

from amaranth.sim import Simulator

import host
from not_tcp import StreamStop
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
    p1 = host.Packet(start=True, stream=2,
                     body=bytes(i for i in range(0, 10)))
    # Host-to-device, starting and ending stream 3
    p2 = host.Packet(start=True, end=True, stream=3,
                     body=bytes(i for i in range(10, 15)))
    # Host-to-device, middle of stream 2
    p3 = host.Packet(stream=2, body=bytes(i for i in range(15, 18)))
    # # device-to-host, stream 2; start and end markers, it's all the data
    p4 = host.Packet(start=True, end=True, stream=2,
                     body=bytes(i for i in range(18, 28)))
    # host-to-device, stream 2: end marker only
    p5 = host.Packet(end=True, stream=2, body=bytes())

    async def driver(ctx):
        # Just the header for p1 should start the stream:
        await send_bus.send_active(p1.header().to_bytes())(ctx)
        # TODO: wait until "accepted"
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
        await send_stop.send_active(p4.body)(ctx)
        # # And mark the stream as closed:
        ctx.set(dut.stop.outbound.active, 0)
        #
        # # And then send p5 to hang up the inbound path:
        await send_bus.send_active(p5.to_bytes())(ctx)
        #
        # Wait for everything to be flushed:
        await ctx.tick().until(
            ~dut.stop.inbound.active & ~dut.bus.downstream.valid)

    sim.add_testbench(driver)
    sim.add_clock(1e-6)

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.000100)  # 100us

    # After simulation is complete...
    # The stop should have received all the packets for this stream:
    collect_stop.assert_eq(
        p1.body + p3.body + p5.body
    )
    # TODO: Stream multiplexing, to the next stops on the bus

    # And the bus should have received the packet for stream 3
    # (which continued around the bus),
    # then the packet sent for stream 2 (which was generated)
    # collect_bus.assert_eq(
    # #     # p2.to_bytes() +
    #     p4.to_bytes()
    # )


if __name__ == "__main__":
    test_single_stop()
