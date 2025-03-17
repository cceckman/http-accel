import sys

from amaranth.sim import Simulator

from simple_led_body import SimpleLedBody
from stream_fixtures import StreamSender

def test_simple_good_case():
    dut = SimpleLedBody()
    sender = StreamSender(stream=dut.input)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def driver(ctx):
        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)

        while not sender.done:
            assert ctx.get(dut.accepted) == 0
            assert ctx.get(dut.red) == 0
            assert ctx.get(dut.green) == 0
            assert ctx.get(dut.blue) == 0
            await ctx.tick()
        await ctx.tick()
        assert ctx.get(dut.accepted)
        assert ctx.get(dut.red) == 0x1A
        assert ctx.get(dut.green) == 0x3B
        assert ctx.get(dut.blue) == 0x5C

    sim.add_testbench(driver)
    sim.add_process(sender.send_passive(map(ord, "1A3B5C\r\n")))

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.0001)

def test_send_two_bodies():
    dut = SimpleLedBody()
    sender = StreamSender(stream=dut.input)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def driver(ctx):
        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)

        while not ctx.get(dut.accepted):
            await ctx.tick()

        assert ctx.get(dut.red) == 0x1A
        assert ctx.get(dut.green) == 0x2B
        assert ctx.get(dut.blue) == 0x3C

        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)
        await ctx.tick()

        assert ctx.get(dut.accepted) == 0

        while not ctx.get(dut.accepted):
            assert ctx.get(dut.red) == 0x1A
            assert ctx.get(dut.green) == 0x2B
            assert ctx.get(dut.blue) == 0x3C
            await ctx.tick()

        # After the 2nd body is accepted, should get the 2nd inptu
        assert ctx.get(dut.red) == 0x4D
        assert ctx.get(dut.green) == 0x5E
        assert ctx.get(dut.blue) == 0x6F

    sim.add_testbench(driver)
    sim.add_process(sender.send_passive(map(ord, "1A2B3C\r\n4D5E6F\r\n")))

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.0001)

def test_invalid_hex():
    dut = SimpleLedBody()
    sender = StreamSender(stream=dut.input)
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    async def driver(ctx):
        ctx.set(dut.reset, 1)
        await ctx.tick()
        ctx.set(dut.reset, 0)

        while not sender.done or ctx.get(dut.rejected):
            await ctx.tick()
        assert ctx.get(dut.accepted) == 0
        assert ctx.get(dut.rejected) == 1

    sim.add_testbench(driver)
    sim.add_process(sender.send_passive(map(ord, "test")))

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.0001)


if __name__ == "__main__":
    test_simple_good_case()
    test_send_two_bodies()
    test_invalid_hex()
