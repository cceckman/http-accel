import sys

from amaranth.sim import Simulator
from amaranth.lib.wiring import connect

from string_contains_match import StringContainsMatch
from stream_fixtures import StreamSender

def test_finds_substring():
    dut = StringContainsMatch("test")
    sender = StreamSender(stream=dut.input)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def driver(ctx):
        ctx.set(dut.reset, 1)
        ctx.tick()
        ctx.set(dut.reset, 0)

        while not sender.done:
            await ctx.tick()
        assert ctx.get(dut.accepted)

    sim.add_testbench(driver)
    sim.add_process(sender.send_passive(map(ord, "This is a test of string contains")))

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.0001)

def test_ididx():
    dut = StringContainsMatch("ididx")
    sender = StreamSender(stream=dut.input)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def driver(ctx):
        ctx.set(dut.reset, 1)
        ctx.tick()
        ctx.set(dut.reset, 0)

        while not sender.done:
            await ctx.tick()
        await ctx.tick()
        assert ctx.get(dut.accepted)

    sim.add_testbench(driver)
    sim.add_process(sender.send_passive(map(ord, "idididx")))

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.0001)

def test_no_match():
    dut = StringContainsMatch("test")
    sender = StreamSender(stream=dut.input)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def driver(ctx):
        ctx.set(dut.reset, 1)
        ctx.tick()
        ctx.set(dut.reset, 0)

        while not sender.done:
            await ctx.tick()
        assert ctx.get(dut.accepted)==0

    sim.add_testbench(driver)
    sim.add_process(sender.send_passive(map(ord, "This is a trial of string contains")))

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.0001)



if __name__ == "__main__":
    test_finds_substring()
    test_ididx()
    test_no_match()
