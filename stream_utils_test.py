from amaranth.sim import Simulator

from stream_utils import LimitForwarder
from stream_fixtures import StreamSender, StreamCollector


def test_limit_forward():
    dut = LimitForwarder(width=8, max_count=80)

    sim = Simulator(dut)
    collector = StreamCollector(dut.outbound)
    sim.add_process(collector.collect())
    sender = StreamSender(dut.inbound)
    # TODO: use Hypothesis, generalize the test
    sim.add_process(sender.send_passive(bytes(i for i in range(0, 100))))

    async def driver(ctx):
        # Tick a few times; should have no data
        for _i in range(0, 10):
            assert not ctx.get(dut.inbound.ready)
            assert not ctx.get(dut.outbound.valid)
            assert ctx.get(dut.done)
            await ctx.tick()

        # Send one block:
        ctx.set(dut.count, 40)
        ctx.set(dut.start, 1)
        # Until the tick, still "done"...
        assert ctx.get(dut.done)
        await ctx.tick()
        ctx.set(dut.start, 0)
        assert not ctx.get(dut.done)
        await ctx.tick().until(dut.done)
        assert len(collector.body) == 40

        # Send another block:
        ctx.set(dut.count, 20)
        ctx.set(dut.start, 1)
        await ctx.tick()
        ctx.set(dut.start, 0)
        await ctx.tick().until(dut.done)

        assert collector.body == bytes(i for i in range(0, 60))

    sim.add_testbench(driver)
    sim.add_clock(1e-6)

    sim.run()
