from amaranth.sim import Simulator

from atoi import AtoI


def run_driver(driver):
    dut = AtoI(32)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def inner_driver(ctx):
        await driver(dut, ctx)
    sim.add_testbench(inner_driver)
    sim.run()


async def run_test_case(dut, ctx, input: str, expected: int):
    ctx.set(dut.reset, 1)
    await ctx.tick()
    ctx.set(dut.reset, 0)

    for c in input:
        ctx.set(dut.input.payload, ord(c))
        ctx.set(dut.input.valid, 1)
        await ctx.tick()
        ctx.set(dut.input.valid, 0)
        assert ctx.get(dut.error) == 0

    assert ctx.get(dut.value) == expected


def test_simple():
    async def driver(dut, ctx):
        await run_test_case(dut, ctx, "1", 1)
        await run_test_case(dut, ctx, "12", 12)
        await run_test_case(dut, ctx, "123", 123)
        await run_test_case(dut, ctx, "1234", 1234)
        await run_test_case(dut, ctx, "12345", 12345)
    run_driver(driver)


def test_simple_error():
    async def driver(dut, ctx):
        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)
        await ctx.tick()
        assert ctx.get(dut.error) == 0

        ctx.set(dut.input.payload, ord("A"))
        ctx.set(dut.input.valid, 1)
        await ctx.tick()
        assert ctx.get(dut.error) == 1

        # Error bit is sticky
        ctx.set(dut.input.payload, ord("0"))
        await ctx.tick()
        assert ctx.get(dut.error) == 1

        # Reset clears it
        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)
        await ctx.tick()
        assert ctx.get(dut.error) == 0
    run_driver(driver)


async def run_ignores_invalid_case(dut, ctx, input: str, expected: int):
    ctx.set(dut.reset, 1)
    await ctx.tick()
    ctx.set(dut.reset, 0)

    for c in input:
        ctx.set(dut.input.payload, ord(c))
        ctx.set(dut.input.valid, 1)
        await ctx.tick()
        ctx.set(dut.input.valid, 0)
        ctx.set(dut.input.payload, ord("x"))
        await ctx.tick()
        assert ctx.get(dut.error) == 0

    assert ctx.get(dut.value) == expected


def test_ignores_invalid():
    async def driver(dut, ctx):
        await run_ignores_invalid_case(dut, ctx, "1", 1)
        await run_ignores_invalid_case(dut, ctx, "12", 12)
        await run_ignores_invalid_case(dut, ctx, "123", 123)
        await run_ignores_invalid_case(dut, ctx, "1234", 1234)
        await run_ignores_invalid_case(dut, ctx, "12345", 12345)
    run_driver(driver)
