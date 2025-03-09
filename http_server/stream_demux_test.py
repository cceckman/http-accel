from amaranth.sim import Simulator

from stream_demux import StreamDemux

# Note: Must be a non power-of-two to be able to create a valid out-of-range test case.
TEST_MUX_WIDTH = 5

async def test_simple_select(ctx):
    ctx.set(dut.select, 2)
    ctx.set(dut.input.payload, 3)
    for i in range(TEST_MUX_WIDTH):
        if (i == 2):
            assert ctx.get(dut.outs[i].payload) == 3
        else:
            assert ctx.get(dut.outs[i].payload) == 0

async def test_out_of_range_select(ctx):
    ctx.set(dut.input.payload, 3)
    ctx.set(dut.select, TEST_MUX_WIDTH+1)
    for i in range(TEST_MUX_WIDTH):
        assert ctx.get(dut.outs[i].payload) == 0

async def bench(ctx):
    await test_simple_select(ctx)
    await test_out_of_range_select(ctx)

dut = StreamDemux(mux_width=TEST_MUX_WIDTH, stream_width=8)
sim = Simulator(dut)
sim.add_testbench(bench)

if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
