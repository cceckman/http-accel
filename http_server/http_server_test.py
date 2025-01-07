from amaranth.sim import Simulator

import regex
from http_server import HTTP10Server

dut = HTTP10Server()


async def bench_once(ctx):
    buf = ""
    r = regex.Regex("[0-9]+ seconds since startup\r\n")
    ctx.set(dut.output.ready, 1)

    # Wait start-of-output, rising edge of "valid":
    await ctx.edge(dut.output.valid, 1)
    # We don't necessarily have a contiguous "valid" range.
    while True:
        if ctx.get(dut.output.valid):
            buf += chr(ctx.get(dut.output.payload))
        else:
            if buf.endswith("\r\n"):
                break
        await ctx.tick()

    assert r.match(buf), buf


async def bench_again(ctx):
    # Re-trigger several times:
    # for _ in range(20):
    for _ in range(1):
        await bench_once(ctx)

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_clock(5e-7, domain="server")
sim.add_testbench(bench_again)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
