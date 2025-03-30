import sys
from amaranth.sim import Simulator

from .count_body import CountBody
from stream_fixtures import StreamCollector

def test_count_body():
    dut = CountBody()
    expected = "requests: 0003 ok_responses: 0002 error_responses: 0001\r\n"

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    collector = StreamCollector(stream=dut.output)
    sim.add_process(collector.collect())

    async def driver(ctx):
        ctx.set(dut.inc_requests, 1)
        ctx.set(dut.inc_ok, 1)
        ctx.set(dut.inc_error, 1)
        await ctx.tick()
        ctx.set(dut.inc_error, 0)
        await ctx.tick()
        ctx.set(dut.inc_ok, 0)
        await ctx.tick()
        ctx.set(dut.inc_requests, 0)
        await ctx.tick()

        ctx.set(dut.en, 1)
        await ctx.tick()
        ctx.set(dut.en, 0)
        while ctx.get(dut.done) != 0:
            await ctx.tick()

    sim.add_testbench(driver)

    # TODO: When #28 is merged, delete.
    with sim.write_vcd(sys.stdout):
        sim.run_until(0.001)

    collector.assert_eq(expected)
    
# TODO: When #28 is merged, delete.
if __name__ == "__main__":
    test_count_body()
