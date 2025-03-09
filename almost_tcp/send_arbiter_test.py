from typing import List
import sys

from amaranth.sim import Simulator
from amaranth.lib.wiring import Component, In, Out, connect
from amaranth import Module
from amaranth.lib import stream

from message_hdl import PacketSignature, SendPacketRoot, SendPacketStop
from message_host import Packet, Header, Flags
from packet_fixtures import PacketCollector, MultiPacketSender, StreamCollector
from hypothesis import given, example


class AtcpSendBus(Component):
    """
    A two-stop packet-send arbiter.

    Packets come in on ports `a` and `b`,
    and come out of `outbus`.
    """

    outbus: Out(stream.Signature(8))
    a: In(PacketSignature())
    b: In(PacketSignature())

    def elaborate(self, platform):
        m = Module()

        m.submodules.a = a = SendPacketStop()
        # m.submodules.b = b = SendPacketStop()
        m.submodules.root = root = SendPacketRoot()

        # Inputs:
        self.a = a.packet
        # self.b = b.packet
        # Output:
        self.outbus = root.output
        # Ring:
        connect(m, a.upstream, root.downstream)
        # connect(m, a.downstream, b.upstream)
        # connect(m, b.downstream, root.upstream)
        connect(m, a.downstream, root.upstream)

        return m


def test_root():
    # A very basic test: the root passes data faithfully.
    dut = SendPacketRoot()

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def never_valid(ctx):
        # The root never provides "downstream" data-
        # just the downstream token.
        async for clk_edge, rst_value, valid in (
                ctx.tick().sample(dut.downstream.data.valid)):
            assert not valid
    sim.add_process(never_valid)

    async def driver(ctx):
        # Token should be ready imminently:
        await ctx.tick().until(dut.downstream.token)
        # After which point it should disappear until returend:
        await ctx.tick()
        assert not ctx.get(dut.downstream.token)

        await ctx.tick().repeat(10)

        # When the token is not held, the root propagates data:
        ctx.set(dut.output.ready, 1)
        await ctx.tick().until(dut.upstream.data.ready)

        ctx.set(dut.upstream.data.valid, 1)
        ctx.set(dut.upstream.data.payload, 2)
        # TODO: It's an implementation detail that the root is buffer-free.
        # It would be nice not to assert that here.
        assert ctx.get(dut.output.valid)
        assert ctx.get(dut.output.payload) == 2

        await ctx.tick()
        ctx.set(dut.upstream.data.valid, 0)
        assert ctx.get(dut.output.valid) == 0

        await ctx.tick().repeat(10)
        ctx.set(dut.upstream.token, 1)
        await ctx.tick()
        ctx.set(dut.upstream.token, 0)
        await ctx.tick().until(dut.downstream.token)
        await ctx.tick()
        assert not ctx.get(dut.downstream.token)

    sim.add_testbench(driver)

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.01)


@given(...)
def test_send_stop(packets: List[Packet], extra_data: bytes):
    dut = SendPacketStop()

    sender = MultiPacketSender(random_delay=False,
                               packet=dut.packet)
    collector = StreamCollector(
        random_backpressure=False, stream=dut.downstream.data)

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_process(sender.send(packets))
    sim.add_process(collector.collect())

    async def bench(ctx):
        # Start with some data, without passing the token.
        i = 0
        while i < len(extra_data):
            assert not ctx.get(dut.downstream.token)

            # No extra delays.
            ctx.set(dut.upstream.data.payload, extra_data[i])
            ctx.set(dut.upstream.data.valid, 1)

            if ctx.get(dut.upstream.data.ready):
                # Will transfer this cycle.
                i += 1
            await ctx.tick()

        # Pass in the token, for one cycle:
        ctx.set(dut.upstream.token, 1)
        await ctx.tick()

        # And then drive until the token is released.
        while not ctx.get(dut.downstream.token):
            await ctx.tick()

        # And wait until all output is flushed:
        while ctx.get(dut.downstream.data.valid):
            await ctx.tick()

    sim.add_testbench(bench)

    with sim.write_vcd(sys.stdout):
        sim.run()

    # And afterwards...
    want = extra_data
    for packet in packets:
        want += packet.encode()
    assert collector.body == want


@given(...)
def proptest_packet_transmission(a_packets: List[Packet],
                                 b_packets: List[Packet]):
    test_packet_transmission(a_packets, b_packets)


def test_packet_transmission(a_packets: List[Packet], b_packets: List[Packet]):
    total_packets = len(a_packets) + len(b_packets)

    dut = AtcpSendBus()

    a = MultiPacketSender(random_delay=False,
                          packet=dut.a)
    # b = MultiPacketSender(random_delay=False,
    #                       packet=dut.b)
    out = PacketCollector(random_backpressure=False,
                          stream=dut.outbus)

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_process(a.send(a_packets))
    # sim.add_process(b.send(b_packets))
    sim.add_process(out.recv())

    async def drive(ctx):
        while len(out.packets) < total_packets:
            await ctx.tick()
        sys.stderr.write(f"finished test case of {total_packets} packets\n")
    sim.add_testbench(drive)

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.01)

    # Make sure we didn't time out
    # assert len(
    #     out.packets) == total_packets, (
    #         f"got: {len(out.packets)}, want: {total_packets}")

    # The collected packets must be some interpolation of the two streams.
    for i in range(len(out.packets)):
        packet = out.packets[i]
        if len(a_packets) > 0 and packet == a_packets[0]:
            a_packets = a_packets[1:]
            continue
        if len(b_packets) > 0 and packet == b_packets[0]:
            b_packets = b_packets[1:]
            continue

        assert False, "unknown packet: unmatched in a or b"


if __name__ == "__main__":
    test_root()
    # test_packet_transmission(
    #     a_packets=[
    #         Packet(Header(flags=Flags(cwr=True), length=1, stream=2),
    #                bytes([0x25]))], b_packets=[]
    # )
    # test_send_stop()
