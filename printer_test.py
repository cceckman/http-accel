from amaranth.sim import Simulator

from printer import Printer

message = "Hello world!"

dut = Printer(message)


async def bench(ctx):
    await bench_no_backpressure(ctx)


async def bench_no_backpressure(ctx):
    assert ctx.get(dut.done)
    assert ctx.get(dut.output.valid) == 0

    # Not yet enabled:
    await ctx.tick()
    assert ctx.get(dut.done)
    assert ctx.get(dut.output.valid) == 0

    ctx.set(dut.en, 1)
    ctx.set(dut.output.ready, 1)
    await ctx.changed(dut.done)
    ctx.set(dut.en, 0)
    for i in range(len(message)):
        await ctx.tick()
        assert not ctx.get(dut.done)
        assert ctx.get(dut.output.valid)
        got = ctx.get(dut.output.payload)
        want = ord(message[i])
        assert got == want, (got, want, chr(got), chr(want))
    await ctx.tick()
    assert ctx.get(dut.done)
    assert not ctx.get(dut.output.valid)


sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
