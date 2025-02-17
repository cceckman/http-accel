from amaranth.sim import Simulator

from bcd_counter import BcdCounter

async def bench(ctx):
    pass

dut = BcdCounter(8, False)
sim = Simulator(dut)
sim.add_testbench(bench)

if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()