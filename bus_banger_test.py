from amaranth.sim import Simulator

from bus_banger import BusBanger
from amaranth_soc import wishbone


wbparams = wishbone.Signature(
    addr_width=8,
    data_width=8,
)

dut = BusBanger(12, wbparams)


# TODO: Write some more tests.
# I think the waveforms look right? But worth checking.

async def bench(ctx):
    for _ in range(128):
        await ctx.tick()

        is_write = ctx.get(dut.wb.cyc) == 1
        if is_write:
            assert ctx.get(dut.wb.we)

            # behavioral: this is a responder.
            # Should be a test process instead?
            ctx.set(dut.wb.ack, 1)
        else:
            ctx.set(dut.wb.ack, 0)


sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
