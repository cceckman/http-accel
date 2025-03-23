from amaranth.sim import Simulator

from stream_mux import StreamMux

# Note: Must be a non power-of-two to be able to create a valid out-of-range test case.
TEST_MUX_WIDTH = 5


def run_driver(driver):
    dut = StreamMux(mux_width=TEST_MUX_WIDTH, stream_width=8)
    sim = Simulator(dut)

    async def inner_driver(ctx):
        await driver(dut, ctx)
    sim.add_testbench(inner_driver)
    sim.run()


def test_simple_select():
    async def driver(dut, ctx):
        for i in range(TEST_MUX_WIDTH):
            ctx.set(dut.input[i].payload, i)
        ctx.set(dut.select, 2)
        assert ctx.get(dut.out.payload) == 2
    run_driver(driver)


def test_out_of_range_select():
    async def driver(dut, ctx):
        for i in range(TEST_MUX_WIDTH):
            ctx.set(dut.input[i].payload, i+1)
        ctx.set(dut.select, TEST_MUX_WIDTH+1)
        assert ctx.get(dut.out.payload) == 0
    run_driver(driver)


async def bench(ctx):
    await test_simple_select(ctx)
    await test_out_of_range_select(ctx)
