import sys
from amaranth.sim import Simulator

from printer import Printer
from printer_seq import PrinterSeq
from stream_fixtures import StreamCollector


def test_simple_sequence():
    dut = PrinterSeq([Printer("Hello, "), Printer("world!")])
    expected = "Hello, world!"

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    collector = StreamCollector(stream=dut.output)
    sim.add_process(collector.collect())

    async def driver(ctx):
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
    test_simple_sequence()
