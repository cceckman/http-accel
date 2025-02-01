import random
from amaranth.sim import Simulator

from http_match import HttpMatch

dut = HttpMatch()


async def run_sequence(ctx, input: str):
    """
    Runs the input sequence into the DUT until accepted, rejected,
    or indeterminate after the input has been passsed.

    Returns true iff the input was accepted;
    fails assertion if the input length was exceeded.
    """
    assert ctx.get(dut.accepted) == 0
    assert ctx.get(dut.rejected) == 0

    in_len = len(input)
    count = 0

    while True:
        if ctx.get(dut.accepted) or ctx.get(dut.rejected):
            break
        if count > (in_len + 10):
            # We've overrun and probably aren't going to exit.
            break
        assert ctx.get(dut.input.ready)
        valid = random.randint(0, 1)
        # valid = 1
        if len(input) == 0:
            valid = 0
            count += 1  # anyway, to run out the timer
        ctx.set(dut.input.valid, valid)
        if valid:
            # Advance the input on this cycle.
            count += 1
            ctx.set(dut.input.payload, ord(input[0]))
            input = input[1:]
        await ctx.tick()

    # After matching-or-not, this is no longer "ready" for input.
    assert not ctx.get(dut.input.ready)
    assert ctx.get(dut.accepted) or ctx.get(dut.rejected)
    accepted = ctx.get(dut.accepted)
    await ctx.tick()

    return accepted


async def bench(ctx):
    # matches_hello = await run_sequence(ctx, "GET /index.html HTTP/1.0\r\n")
    # assert matches_hello

    # ctx.set(dut.reset, 1)
    # await ctx.tick()
    # ctx.set(dut.reset, 0)
    # ctx.set(dut.input.valid, 0)
    #
    matches_goodbye = await run_sequence(ctx, "WHAT is this even")
    assert not matches_goodbye
    #
    # ctx.set(dut.reset, 1)
    # await ctx.tick()
    # ctx.set(dut.reset, 0)
    # ctx.set(dut.input.valid, 0)
    #
    # matches_hello_lower = await run_sequence(ctx, "hello")
    # assert not matches_hello_lower

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
