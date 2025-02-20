from amaranth.sim import Simulator

from bcd_counter import BcdDigit

async def test_count(ctx):
    ctx.set(dut.reset, 1)
    await ctx.tick()
    ctx.set(dut.reset, 0)

    ctx.set(dut.en, 1)
    for i in range(5):
        assert ctx.get(dut.digit) == i
        await ctx.tick()
    assert ctx.get(dut.digit) == 5

    # If disabled, ticking should not change value
    ctx.set(dut.en, 0)
    for i in range(5):
        assert ctx.get(dut.digit) == 5
        await ctx.tick()

    ctx.set(dut.en, 1)
    for i in range(10):
        digit = ctx.get(dut.digit)
        assert digit == (5+i)%10
        assert ctx.get(dut.ovf) == (digit == 9)
        await ctx.tick()

async def bench(ctx):
    await test_count(ctx)

dut = BcdDigit()
sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
