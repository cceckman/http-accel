import amaranth as am
from amaranth.sim import Simulator
from amaranth.lib.wiring import In, Out, Component
from capitalizer import Capitalizer


class CapUncap(Component):
    input: In(8)

    lower: Out(8)
    upper: Out(8)

    def elaborate(self, platform):
        m = am.Module()
        m.submodules.upper = upper = Capitalizer(to_upper=True)
        m.submodules.lower = lower = Capitalizer(to_upper=False)

        m.d.comb += [
            upper.input.eq(self.input),
            lower.input.eq(self.input),
            self.upper.eq(upper.output),
            self.lower.eq(lower.output),
        ]

        return m


def test_capitalizer():

    dut = CapUncap()

    async def bench(ctx):
        for i in range(0, 256):
            ctx.set(dut.input, i)
            await ctx.delay(1)

            want_lower = want_upper = i
            if chr(i).isascii():
                want_lower = ord(chr(i).lower())
                want_upper = ord(chr(i).upper())

            up = ctx.get(dut.upper)
            assert up == want_upper, (i, want_upper, up)
            lo = ctx.get(dut.lower)
            assert lo == want_lower, (i, want_lower, lo)

    sim = Simulator(dut)
    # sim.add_clock(1e-6)
    sim.add_testbench(bench)

    sim.run()
