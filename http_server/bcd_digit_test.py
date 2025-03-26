from amaranth.sim import Simulator

from .bcd_counter import BcdDigit


def test_count():
    dut = BcdDigit()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def driver(ctx):
        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)

        ctx.set(dut.inc, 1)
        for i in range(5):
            assert ctx.get(dut.digit) == i
            await ctx.tick()
        assert ctx.get(dut.digit) == 5

        # If disabled, ticking should not change value
        ctx.set(dut.inc, 0)
        for i in range(5):
            assert ctx.get(dut.digit) == 5
            await ctx.tick()

        ctx.set(dut.inc, 1)
        for i in range(10):
            digit = ctx.get(dut.digit)
            assert digit == (5+i) % 10
            assert ctx.get(dut.ovf) == (digit == 9)
            await ctx.tick()

    sim.add_testbench(driver)
    sim.run()
