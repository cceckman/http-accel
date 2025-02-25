from amaranth.sim import Simulator
from amaranth.lib.wiring import Component, In, Out, connect
from amaranth import Module
from amaranth.lib import stream

from message_hdl import ReadPacketStop, PacketSignature, SendPacketRoot, SendPacketStop
from message_host import Header, Packet, Flags
from packet_fixtures import StreamCollector, MultiPacketSender


class AtcpSendBus(Component):

    outbus: Out(stream.Signature(8))
    a: In(PacketSignature())
    b: In(PacketSignature())

    def elaborate(self, platform):
        m = Module()

        m.submodules.a = a = SendPacketStop()
        m.submodules.b = b = SendPacketStop()
        m.submodules.root = root = SendPacketRoot()

        # Inputs:
        connect(m, self.a, a.packet)
        connect(m, self.b, b.packet)
        # Output:
        connect(m, self.outbus, root.output)
        # Ring:
        connect(m, a.upstream, root.downstream)
        connect(m, b.upstream, b.downstream)
        connect(m, root.upstream, a.downstream)

        return m


dut = AtcpSendBus()


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
