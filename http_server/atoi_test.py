from amaranth.sim import Simulator

from atoi import AtoI

dut = AtoI(32)

async def test_exhaustive(ctx):
    pass

sim = Simulator(dut)
sim.add_testbench(test_exhaustive)

if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
