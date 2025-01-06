from amaranth.sim import Simulator

from number import Number

dut = Number(16)


async def bench(ctx):
    await run_test(ctx, 0)
    await run_test(ctx, 3)
    await run_test(ctx, 0xffff)
    await run_test(ctx, 99)


async def run_test(ctx, i):
    assert ctx.get(dut.done)
    assert ctx.get(dut.output.valid) == 0

    # Not yet enabled:
    await ctx.tick()
    assert ctx.get(dut.done)
    assert ctx.get(dut.output.valid) == 0

    ctx.set(dut.input, i)
    ctx.set(dut.en, 1)
    ctx.set(dut.output.ready, 1)
    await ctx.changed(dut.done)
    ctx.set(dut.en, 0)
    buf = ""
    while not ctx.get(dut.done):
        if ctx.get(dut.output.valid):
            got = ctx.get(dut.output.payload)
            buf += chr(got)
        await ctx.tick()

    assert ctx.get(dut.done)
    assert not ctx.get(dut.output.valid)
    want = str(i)
    assert buf == want, (buf, want)


sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
