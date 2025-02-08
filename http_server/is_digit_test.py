from amaranth.sim import Simulator

from is_digit import IsDigit

dut = IsDigit()

async def test_exhaustive(ctx):
    for test in range(128):
        ctx.set(dut.input, test)
        await ctx.delay(1)
        assert ctx.get(dut.is_digit) == chr(test).isdigit()

sim = Simulator(dut)
sim.add_testbench(test_exhaustive)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
