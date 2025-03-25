from amaranth.sim import Simulator

from stream_demux import StreamDemux

# Note: Must be a non power-of-two to be able to create a valid out-of-range
# test case.
TEST_MUX_WIDTH = 5


def run_driver(driver):
    dut = StreamDemux(mux_width=TEST_MUX_WIDTH, stream_width=8)
    sim = Simulator(dut)

    async def inner_driver(ctx):
        await driver(dut, ctx)
    sim.add_testbench(inner_driver)
    sim.run()


def test_simple_select():
    async def driver(dut, ctx):
        ctx.set(dut.select, 2)
        ctx.set(dut.input.payload, 3)
        for i in range(TEST_MUX_WIDTH):
            if (i == 2):
                assert ctx.get(dut.outs[i].payload) == 3
            else:
                assert ctx.get(dut.outs[i].payload) == 0
    run_driver(driver)


def test_out_of_range_select():
    async def driver(dut, ctx):
        ctx.set(dut.input.payload, 3)
        ctx.set(dut.select, TEST_MUX_WIDTH+1)
        for i in range(TEST_MUX_WIDTH):
            assert ctx.get(dut.outs[i].payload) == 0
    run_driver(driver)
