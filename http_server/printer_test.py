import random

from amaranth.sim import Simulator

from .printer import Printer

message = "Hello world!"


def test_printer():

    dut = Printer(message)

    async def bench(ctx):
        # Randomized testing:
        for _ in range(20):
            await bench_backpressure(ctx)

    async def bench_backpressure(ctx):
        assert ctx.get(dut.done)
        assert ctx.get(dut.output.valid) == 0

        # Not yet enabled:
        await ctx.tick()
        assert ctx.get(dut.done)
        assert ctx.get(dut.output.valid) == 0

        buf = ""
        ctx.set(dut.en, 1)
        while True:
            if ctx.get(dut.output.valid) and ctx.get(dut.output.ready):
                # A byte will be transferred this cycle.
                got = ctx.get(dut.output.payload)
                buf += chr(got)

            await ctx.tick()
            ctx.set(dut.en, 0)
            ctx.set(dut.output.ready, random.randint(0, 1))

            if ctx.get(dut.done):
                break
        assert buf == message, (buf, message)

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(bench)

    sim.run()
