from amaranth.sim import Simulator

import regex
import random
from http_server import HTTP10Server

dut = HTTP10Server()

r = regex.Regex("^[0-9]+ seconds since startup\r\n")


async def bench_once(ctx):
    buf = ""
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


async def bench_backpressure(ctx):
    buf = ""
    while True:
        if ctx.get(dut.output.valid) and ctx.get(dut.output.ready):
            # A byte will be transferred this cycle.
            # A byte was transferred.
            got = ctx.get(dut.output.payload)
            buf += chr(got)

        await ctx.tick()
        ctx.set(dut.output.ready, random.randint(0, 1))

        if buf.endswith("\r\n"):
            break
    assert r.match(buf), buf

    # This comes after bench_once, so we're guaranteed that the second count is >0.
    number = int(buf.split(' ')[0])
    assert number > 0


async def bench_again(ctx):
    await bench_once(ctx)
    # Randomized backpressure:
    for _ in range(20):
        await bench_backpressure(ctx)

sim = Simulator(dut)
sim.add_clock(1e-6)
# sim.add_clock(5e-7, domain="server")
sim.add_testbench(bench_again)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
