from amaranth.sim import Simulator

from bcd_counter import BcdCounter

WIDTH = 5

async def run_test(ctx, value, backpressure):
    ctx.set(dut.reset, 1)
    await ctx.tick()
    ctx.set(dut.reset, 0)

    assert ctx.get(dut.done)
    assert ctx.get(dut.output.valid) == 0

    ctx.set(dut.en, 1)
    for _ in range(value):
        await ctx.tick()

    ctx.set(dut.en, 0)
    ctx.set(dut.trigger, 1)
    ctx.set(dut.output.ready, 1)
    await ctx.tick()
    ctx.set(dut.trigger, 0)

    buf = ""
    while not ctx.get(dut.done):
        if ctx.get(dut.output.valid):
            got = ctx.get(dut.output.payload)
            buf += chr(got)
        if backpressure:
            ctx.set(dut.output.ready, 0)
            for _ in range(5):
                await ctx.tick()
            ctx.set(dut.output.ready, 1)
        await ctx.tick()

    assert buf == f"{value:0{WIDTH}}"


async def bench(ctx):
    await run_test(ctx, 1, backpressure=False)
    await run_test(ctx, 12, backpressure=False)
    await run_test(ctx, 123, backpressure=False)
    await run_test(ctx, 1234, backpressure=False)
    await run_test(ctx, 12345, backpressure=False)
    await run_test(ctx, 1, backpressure=True)
    await run_test(ctx, 12, backpressure=True)
    await run_test(ctx, 123, backpressure=True)
    await run_test(ctx, 1234, backpressure=True)
    await run_test(ctx, 12345, backpressure=True)


dut = BcdCounter(WIDTH, True)
sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
