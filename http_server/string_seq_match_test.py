import random
import sys
from amaranth.sim import Simulator

from string_match import StringMatch
from string_alt_match import StringAltMatch
from string_seq_match import StringSeqMatch

dut = StringSeqMatch(sequence=[
    StringAltMatch(alternatives=[
        StringMatch("GET", match_case=False),
        StringMatch("POST", match_case=False),
    ]),
    StringMatch(" "),
    StringAltMatch(alternatives=[
        StringMatch("/style.css"),
        StringMatch("/index.html"),
    ]),
    StringMatch(" HTTP/1"),
    StringAltMatch(alternatives=[
        StringMatch(".0\r\n"),
        StringMatch("\r\n"),
    ]),
])


async def run_sequence(ctx, input: str):
    """
    Runs the input sequence into the DUT until accepted, rejected,
    or indeterminate after the input has been passsed.

    Returns which match if the input was accepted;
    otherwise returns None.
    """
    ctx.set(dut.reset, 1)
    await ctx.tick()
    ctx.set(dut.reset, 0)
    ctx.set(dut.input.valid, 0)

    assert ctx.get(dut.accepted) == 0
    assert ctx.get(dut.rejected) == 0

    count = 0
    input_len = len(input)
    while True:
        if ctx.get(dut.accepted) or ctx.get(dut.rejected):
            break
        if count == input_len:
            break
        assert ctx.get(dut.input.ready)
        valid = random.randint(0, 1)
        ctx.set(dut.input.valid, valid)
        if valid:
            # Advance the input on this cycle.
            ctx.set(dut.input.payload, ord(input[0]))
            input = input[1:]
            count += 1
        await ctx.tick()

    # After matching-or-not, this is no longer "ready" for input.
    assert not ctx.get(dut.input.ready)
    assert ctx.get(dut.accepted) or ctx.get(dut.rejected)
    accepted = ctx.get(dut.accepted)
    await ctx.tick()

    return accepted


async def bench(ctx):
    assert await run_sequence(ctx, "GET /index.html HTTP/1\r\n")
    assert not await run_sequence(ctx, "DELETE /index.html HTTP/1.0\r\n")
    await run_sequence(ctx, "POST /style.css HTTP/1.0\r\n")


sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys
    with sim.write_vcd(sys.stdout):
        sim.run()
