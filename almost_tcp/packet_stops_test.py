from amaranth.sim import Simulator

from message_hdl import ReadPacketStop
from message_host import Header, Packet, Flags
from packet_fixtures import StreamCollector, PacketSender

dut = ReadPacketStop(id=3)


def bench(dut,
          body_collector: StreamCollector,
          packet_collector: StreamCollector,
          refpkt: Packet):
    async def bench(ctx):
        packet = dut.packet
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

        # Wait until all the data are read:
        while ctx.get(packet.header_valid):
            await ctx.tick()
        # Wait until the tail is drained too,
        # which is probably at least one cycle later:
        while len(packet_collector) < len(refpkt.encode()):
            await ctx.tick()

        body_collector.assert_eq(refpkt.body)
        packets_collector.assert_eq(refpkt.encode())
    return bench


# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys

    sim = Simulator(dut)
    body_collector = StreamCollector(random_backpressure=True)
    packets_collector = StreamCollector(random_backpressure=True)
    sender = PacketSender(random_delay=True)
    data = bytes(i % 256 for i in range(0, 260))
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

    sim.add_clock(1e-6)
    sim.add_process(sender.send(p, dut.inbus))
    sim.add_process(body_collector.collect(dut.packet.data))
    sim.add_process(packets_collector.collect(dut.outbus))
    sim.add_testbench(bench(dut, body_collector, packets_collector, p))

    with sim.write_vcd(sys.stdout):
        sim.run()
