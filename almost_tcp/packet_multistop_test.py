from amaranth.sim import Simulator
from amaranth.lib.wiring import Component, In, Out, connect
from amaranth import Module
from amaranth.lib import stream
import sys
from message_hdl import ReadPacketStop, PacketSignature
from message_host import Header, Packet, Flags
from packet_fixtures import StreamCollector, MultiPacketSender


class AtcpReadBus(Component):

    inbus: In(stream.Signature(8))
    three: Out(PacketSignature())
    five: Out(PacketSignature())

    def elaborate(self, platform):
        m = Module()

        m.submodules.three = three = ReadPacketStop(id=3)
        m.submodules.five = five = ReadPacketStop(id=5)
        # Export the packet interfaces:
        self.three = three.packet
        self.five = five.packet

        # Chain the bus:
        self.inbus = three.inbus
        connect(m, three.outbus, five.inbus)
        # And allow the last stop to fall on the floor
        m.d.comb += five.outbus.ready.eq(1)

        return m


def test_read_bus():
    dut = AtcpReadBus()

    sim = Simulator(dut)
    three_collector = StreamCollector(
        random_backpressure=False, stream=dut.three.data)
    five_collector = StreamCollector(
        random_backpressure=False, stream=dut.five.data)
    # We don't delay in the input, so we can detect
    # the sender's completion from within the testbench.
    sender = MultiPacketSender(random_delay=False, stream=dut.inbus)
    data = bytes(i % 256 for i in range(0, 50))
    p3 = Packet(
        Header(
            Flags(cwr=True, urg=True, rst=True, fin=True),
            stream=3,
            length=len(data),
            window=770,
            seq=4097,
            ack=12290,
        ),
        body=data
    )
    p5 = Packet(
        Header(
            Flags(fin=True),
            stream=5,
            length=len(data[:40]),
            window=80,
            seq=123,
            ack=456,
        ),
        body=data[:40]
    )

    sim.add_clock(1e-6)

    sim.add_process(three_collector.collect())
    sim.add_process(five_collector.collect())
    sim.add_process(sender.send([p5, p3, p5]))

    async def driver(ctx):
        while not sender.done:
            # Send all bytes
            await ctx.tick()

        # Then wait for receivers to flush
        while ctx.get(dut.three.data.valid) or ctx.get(dut.five.data.valid):
            await ctx.tick()

        # All data should be collected.
    sim.add_testbench(driver)
    sim.run()

    # After the simulation completes -- the sender is done --
    # we still should only have collected only
    # the data from the packet on stream 3...
    three_collector.assert_eq(p3.body)
    # ...and the data from both stream-5 packets on stream 5.
    five_collector.assert_eq(2 * p5.body)
