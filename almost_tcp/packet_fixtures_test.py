from amaranth.lib.fifo import SyncFIFOBuffered
from amaranth.sim import Simulator
from hypothesis import given, strategies
from packet_fixtures import (
    MultiPacketSender, PacketCollector, arbitrary_packet)
from message_host import Packet
from typing import List
import sys

# This doesn't work via import, apparently
strategies.register_type_strategy(Packet, arbitrary_packet())


@given(packets=...)
def test_stream_send_structured_receive(packets: List[Packet]):
    """
    Test a round-trip between MultiPacketSender (Packet -> stream) and
    PacketCollector (stream->Packet), via a FIFO.
    """

    # All we need is a buffer for this to work.
    # Depth chosen arbitrarily.
    dut = SyncFIFOBuffered(width=8, depth=2)
    sender = MultiPacketSender(random_delay=True, stream=dut.w_stream)
    # Turning on random backpressure here causes the tests to take A Long Time.
    # ...I guess because if there's *random* backpressure, there's a set of
    # random sequences which results in it taking an arbitrarily long time to
    # complete. Though, that's *arbitrary*, not *random*.
    # TODO: Double-check on packpressure
    #
    # Apparently Hypothesis handles the `random` RNG:
    # > By default, Hypothesis will handle the global `random` and
    # > `numpy.random` random number generators for you,
    # https://hypothesis.readthedocs.io/en/latest/details.html#making-random-code-deterministic
    #
    receiver = PacketCollector(
        random_backpressure=False, stream=dut.r_stream)

    async def driver(ctx):
        while len(receiver.packets) < len(packets):
            await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_process(sender.send(packets))
    sim.add_process(receiver.recv())
    sim.add_testbench(driver)

    with sim.write_vcd(sys.stdout):
        sim.run()

    assert len(receiver.packets) == len(packets)
    for i in range(len(packets)):
        want = packets[i]
        got = receiver.packets[i]
        assert got == want


if __name__ == "__main__":
    test_stream_send_structured_receive()
