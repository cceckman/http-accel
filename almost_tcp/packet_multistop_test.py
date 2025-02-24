from amaranth.sim import Simulator
from amaranth.lib.wiring import Component, In, Out, connect
from amaranth import Module
from amaranth.lib import stream

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


dut = AtcpReadBus()


def bench_stream3(dut, refpkt: Packet):
    async def bench(ctx):
        packet = dut.three
        while ctx.get(packet.stream_valid) != 1:
            await ctx.tick()
        assert ctx.get(packet.stream_valid)
        assert ctx.get(packet.header.stream) == refpkt.header.stream
        assert not ctx.get(packet.header_valid)

        while ctx.get(packet.header_valid) != 1:
            await ctx.tick()
        assert ctx.get(packet.stream_valid)
        assert ctx.get(packet.header_valid)
        hdr = refpkt.header
        assert ctx.get(packet.header.flags.fin) == hdr.flags.fin
        assert ctx.get(packet.header.flags.urg) == hdr.flags.urg
        assert ctx.get(packet.header.flags.rst) == hdr.flags.rst
        assert ctx.get(packet.header.flags.cwr) == hdr.flags.cwr
        assert ctx.get(packet.header.flags.psh) == hdr.flags.psh
        assert ctx.get(packet.header.flags.ack) == hdr.flags.ack
        assert ctx.get(packet.header.flags.syn) == hdr.flags.syn
        assert ctx.get(packet.header.flags.ack) == hdr.flags.ack
        assert ctx.get(packet.header.stream) == hdr.stream
        assert ctx.get(packet.header.length) == hdr.length
        assert ctx.get(packet.header.window) == hdr.window
        assert ctx.get(packet.header.seq) == hdr.seq
        assert ctx.get(packet.header.ack) == hdr.ack

        # Continue driving the simulation until the input is complete.
        while ctx.get(dut.inbus.valid):
            await ctx.tick()
        # ...and until the output is complete.
        while ctx.get(dut.five.data.valid):
            await ctx.tick()

    return bench


def sim_main():
    import sys

    sim = Simulator(dut)
    three_collector = StreamCollector(random_backpressure=False)
    five_collector = StreamCollector(random_backpressure=False)
    # We don't delay in the input, so we can detect
    # the sender's completion from within the testbench.
    sender = MultiPacketSender(random_delay=False)
    data = bytes(i % 256 for i in range(0, 50))
    p = Packet(
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
    p0 = Packet(
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

    sim.add_process(three_collector.collect(dut.three.data))
    sim.add_process(five_collector.collect(dut.five.data))
    sim.add_process(sender.send([p0, p, p0], dut.inbus))
    sim.add_testbench(bench_stream3(dut, p))

    with sim.write_vcd(sys.stdout):
        sim.run()

    # After the simulation completes -- the sender is done --
    # we still should only have collected only
    # the data from the packet on stream 3...
    three_collector.assert_eq(p.body)
    # ...and the data from both stream-5 packets on stream 5.
    five_collector.assert_eq(2 * p0.body)


if __name__ == "__main__":
    sim_main()
