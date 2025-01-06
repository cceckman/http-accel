from amaranth.sim import Simulator

from up_counter import UpCounter

dut = UpCounter(25)


async def test_disabled_no_overflow(ctx):
    ctx.set(dut.en, 0)
    for _ in range(30):
        await ctx.tick()
        assert not ctx.get(dut.ovf)


async def test_ovf_time(ctx):
    ctx.set(dut.en, 1)
    for _ in range(24):
        await ctx.tick()
        assert not ctx.get(dut.ovf)
    await ctx.tick()
    assert ctx.get(dut.ovf)

    # Clear in one cycle:
    await ctx.tick()
    assert not ctx.get(dut.ovf)


async def bench(ctx):
    # I don't like that these tests are coupled.
    # Is there a better example of independent tests?
    await test_disabled_no_overflow(ctx)
    await test_ovf_time(ctx)

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
