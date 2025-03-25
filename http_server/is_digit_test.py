from amaranth.sim import Simulator

from is_digit import IsDigit


def test_exhaustive():
    dut = IsDigit()
    sim = Simulator(dut)

    async def driver(ctx):
        for test in range(128):
            ctx.set(dut.input, test)
            await ctx.delay(1)
            got = ctx.get(dut.is_digit)
            want = chr(test).isdigit()
            assert got == want, f"{test}: {got} {want}"

    sim.add_testbench(driver)
    sim.run()
