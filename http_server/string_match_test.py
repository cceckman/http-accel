import random
from amaranth.sim import Simulator

from string_match import StringMatch

dut = StringMatch("Hello")


async def run_sequence(ctx, input: str):
    """
    Runs the input sequence into the DUT until accepted, rejected,
    or indeterminate after the input has been passsed.

    Returns true iff the input was accepted;
    fails assertion if the input length was exceeded.
    """
    assert ctx.get(dut.accepted) == 0
    assert ctx.get(dut.rejected) == 0

    input = input + "     "
    count = 0

    while True:
        if ctx.get(dut.accepted) or ctx.get(dut.rejected):
            break
        if count > len(input):
            break
        assert ctx.get(dut.input.ready)
        valid = random.randint(0, 1)
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
    return ctx.get(dut.accepted)


async def bench(ctx):
    matches_hello = await run_sequence(ctx, "Hello")
    assert matches_hello

    ctx.set(dut.reset, 1)
    await ctx.tick()
    ctx.set(dut.reset, 0)
    ctx.set(dut.input.valid, 0)

    matches_goodbye = await run_sequence(ctx, "Goodbye")
    assert not matches_goodbye

sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
