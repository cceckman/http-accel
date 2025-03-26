import random

from amaranth.sim import Simulator

from .number import Number


def test_number():

    dut = Number(16)

    async def bench(ctx):
        await run_test(ctx, 0)
        await run_test(ctx, 3)
        await run_test(ctx, 0xffff)

        # Randomized test:
        for _ in range(20):
            await run_test_backpressure(ctx, 1234)

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

    async def run_test_backpressure(ctx, i):
        assert ctx.get(dut.done)
        assert ctx.get(dut.output.valid) == 0

        # Not yet enabled:
        await ctx.tick()
        assert ctx.get(dut.done)
        assert ctx.get(dut.output.valid) == 0

        buf = ""
        ctx.set(dut.input, i)
        ctx.set(dut.en, 1)
        while True:
            if ctx.get(dut.output.valid) and ctx.get(dut.output.ready):
                # A byte will be transferred this cycle.
                # A byte was transferred.
                got = ctx.get(dut.output.payload)
                buf += chr(got)

            await ctx.tick()
            ctx.set(dut.en, 0)
            ctx.set(dut.output.ready, random.randint(0, 1))

            if ctx.get(dut.done):
                break

        assert not ctx.get(dut.output.valid)
        want = str(i)
        assert buf == want, (buf, want)

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(bench)

    sim.run()
