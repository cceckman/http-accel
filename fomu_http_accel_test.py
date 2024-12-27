from amaranth.sim import Simulator

from fomu_http_accel import HTTPAccel

dut = HTTPAccel()


async def test_bus(ctx):
    for _ in range(100):
        await ctx.tick()


async def bench(ctx):
    # I don't like that these tests are coupled.
    # Is there a better example of independent tests?
    await test_bus(ctx)

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
