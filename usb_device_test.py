from amaranth.sim import Simulator

from usb_device import USBDeviceExample

dut = USBDeviceExample()


async def test_clocks(ctx):
    for i in range(0, 128):
        usb = ctx.get(dut.usb_clk)
        if (i % 4) == 3:
            assert usb
        else:
            assert not usb
        await ctx.tick()

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(test_clocks)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
