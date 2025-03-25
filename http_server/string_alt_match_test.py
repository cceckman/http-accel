import random

from amaranth.sim import Simulator

from .string_match import StringMatch
from .string_alt_match import StringAltMatch


def run_sequence(input: str):
    """
    Runs the input sequence into the DUT until accepted, rejected,
    or indeterminate after the input has been passsed.

    Returns which match if the input was accepted;
    otherwise returns None.
    """
    dut = StringAltMatch(alternatives=[
        StringMatch("GET", match_case=False),
        StringMatch("POST", match_case=True),
        StringAltMatch(alternatives=[
            StringMatch("CONNECT"),
            StringMatch("DELETE"),
        ]),
    ])

    result = None

    async def inner_driver(ctx):
        nonlocal result
        nonlocal input
        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)
        ctx.set(dut.input.valid, 0)

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
        accepted = ctx.get(dut.accepted)
        which = ctx.get(dut.which)
        await ctx.tick()

        if accepted:
            result = which
        else:
            result = None

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(inner_driver)

    sim.run()
    return result


def test_cap_get():
    m = run_sequence("GET")
    assert (m == 0) and (m is not None)


def test_get():
    m = run_sequence("get")
    assert (m == 0) and (m is not None)


def test_cap_post():
    m = run_sequence("POST")
    assert m == 1


def test_post():
    m = run_sequence("post")
    assert (m is None)


def test_put():
    m = run_sequence("PUT")
    assert (m is None)


def test_delete():
    m = run_sequence("DELETE")
    assert m == 2
