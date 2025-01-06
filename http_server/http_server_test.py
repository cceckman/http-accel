from amaranth.sim import Simulator

import regex
from http_server import HTTP10Server

dut = HTTP10Server()


async def bench(ctx):
    buf = ""

    ctx.set(dut.output.ready, 1)
    # Wait start-of-output, rising edge of "valid":
    await ctx.edge(dut.output.valid, 1)
    while ctx.get(dut.output.valid):
        buf += chr(ctx.get(dut.output.payload))
        await ctx.tick()

    r = regex.Regex("[0-9]+ seconds since startup\r\n")
    assert r.match(buf), buf


sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
