from amaranth.sim import Simulator

from atoi import AtoI

dut = AtoI(32)

async def run_test_case(ctx, input: str, expected: int) -> int: 
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


async def test_simple(ctx):
    await run_test_case(ctx, "1", 1)
    await run_test_case(ctx, "12", 12)
    await run_test_case(ctx, "123", 123)
    await run_test_case(ctx, "1234", 1234)
    await run_test_case(ctx, "12345", 12345)

async def test_simple_error(ctx):
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

async def bench(ctx):
    await test_simple(ctx)
    await test_simple_error(ctx)

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
