from amaranth.sim import Simulator

from up_counter import UpCounter


def run_driver(driver):
    dut = UpCounter(25)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def inner_driver(ctx):
        await driver(dut, ctx)
    sim.add_testbench(inner_driver)
    sim.run()


def test_disabled_no_overflow():
    async def driver(dut, ctx):
        ctx.set(dut.en, 0)
        for _ in range(30):
            await ctx.tick()
            assert not ctx.get(dut.ovf)
    run_driver(driver)


def test_ovf_time():
    async def driver(dut, ctx):
        ctx.set(dut.en, 1)
        for _ in range(24):
            await ctx.tick()
            assert not ctx.get(dut.ovf)
        await ctx.tick()
        assert ctx.get(dut.ovf)

        # Clear in one cycle:
        await ctx.tick()
        assert not ctx.get(dut.ovf)
    run_driver(driver)
