import sys

from amaranth.sim import Simulator

from .simple_led_http import SimpleLedHttp
from stream_fixtures import StreamCollector


def test_ok_handling():
    dut = SimpleLedHttp()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    input = ("POST /led HTTP/1.0\r\n"
             "Host: test\r\n"
             "User-Agent: test-agent\r\n"
             "Content-Type: text/plain\r\n"
             "\r\n"
             "123456\r\n")
    expected_output = ("HTTP/1.0 200 OK\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
                       "👍\r\n")

    async def driver(ctx):
        ctx.set(dut.session.inbound.active, 1)
        await ctx.tick().until(dut.session.outbound.active)

        in_stream = dut.session.inbound.data
        ctx.set(in_stream.valid, 1)
        idx = 0
        while idx < len(input):
            ctx.set(in_stream.payload, ord(input[idx]))
            if ctx.get(in_stream.ready):
                idx += 1
            await ctx.tick()
        # After all input data is read, deassert inbound session
        ctx.set(dut.session.inbound.active, 0)
        # Keep driving clock until the outbound session is deasserted
        await ctx.tick().until(~dut.session.outbound.active)
        assert not ctx.get(dut.session.outbound.data.valid)

        assert ctx.get(dut.red) == 0x12
        assert ctx.get(dut.green) == 0x34
        assert ctx.get(dut.blue) == 0x56

        # Add some nice margins for our vcd
        await ctx.tick()

    sim.add_testbench(driver)

    collector = StreamCollector(stream=dut.session.outbound.data)
    sim.add_process(collector.collect())

    # Doesn't appear to be a way to _remove_ a testbench;
    # I guess .reset() is "just" to allow a different initial state?
    #with sim.write_vcd("test.vcd"):
    sim.run_until(0.0005)

    # Now that the test is done:
    collector.assert_eq(expected_output)

def test_404_handling():
    dut = SimpleLedHttp()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    input = ("POST /bad_uri HTTP/1.0\r\n"
             "Host: evil_test\r\n"
             "User-Agent: evil-agent\r\n"
             "Content-Type: text/bad\r\n"
             "\r\n"
             "123456\r\n")
    expected_output = ("HTTP/1.0 404 Not Found\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
                       "👎\r\n")

    async def driver(ctx):
        ctx.set(dut.session.inbound.active, 1)
        await ctx.tick().until(dut.session.outbound.active)

        in_stream = dut.session.inbound.data
        ctx.set(in_stream.valid, 1)
        idx = 0
        while idx < len(input):
            ctx.set(in_stream.payload, ord(input[idx]))
            if ctx.get(in_stream.ready):
                idx += 1
            await ctx.tick()
        # After all input data is read, deassert inbound session
        ctx.set(dut.session.inbound.active, 0)
        # Keep driving clock until the outbound session is deasserted
        await ctx.tick().until(~dut.session.outbound.active)
        assert not ctx.get(dut.session.outbound.data.valid)

        # Add some nice margins for our vcd
        await ctx.tick()

    sim.add_testbench(driver)

    collector = StreamCollector(stream=dut.session.outbound.data)
    sim.add_process(collector.collect())

    sim.run_until(0.001)

    # Now that the test is done:
    collector.assert_eq(expected_output)


def test_405_handling():
    dut = SimpleLedHttp()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    input = ("GET /led HTTP/1.0\r\n"
             "Host: curious_test\r\n"
             "User-Agent: evil-agent\r\n"
             "Content-Type: text/bad\r\n"
             "\r\n"
             "What're your LEDs doing?\r\n")
    expected_output = ("HTTP/1.0 405 Method Not Allowed\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
                       "🛑\r\n")

    async def driver(ctx):
        ctx.set(dut.session.inbound.active, 1)
        await ctx.tick().until(dut.session.outbound.active)

        in_stream = dut.session.inbound.data
        ctx.set(in_stream.valid, 1)
        idx = 0
        while idx < len(input):
            ctx.set(in_stream.payload, ord(input[idx]))
            if ctx.get(in_stream.ready):
                idx += 1
            await ctx.tick()
        # After all input data is read, deassert inbound session
        ctx.set(dut.session.inbound.active, 0)
        # Keep driving clock until the outbound session is deasserted
        await ctx.tick().until(~dut.session.outbound.active)
        assert not ctx.get(dut.session.outbound.data.valid)

        # Add some nice margins for our vcd
        await ctx.tick()

    sim.add_testbench(driver)

    collector = StreamCollector(stream=dut.session.outbound.data)
    sim.add_process(collector.collect())

    sim.run_until(0.001)

    # Now that the test is done:
    collector.assert_eq(expected_output)

def test_count_handling():
    dut = SimpleLedHttp()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    led_input = ("POST /led HTTP/1.0\r\n"
             "Host: test\r\n"
             "User-Agent: test-agent\r\n"
             "Content-Type: text/plain\r\n"
             "\r\n"
             "123456\r\n")
    error_input = ("BREW /cocoa HTTP/1.0\r\n"
             "Host: test\r\n"
             "User-Agent: test-agent\r\n"
             "Content-Type: text/plain\r\n"
             "\r\n"
             "With marshmallows, please\r\n")
    count_input = ("GET /count HTTP/1.0\r\n"
             "Host: test\r\n"
             "User-Agent: test-agent\r\n"
             "Content-Type: text/plain\r\n"
             "\r\n"
             "\r\n")

    expected_output = ("HTTP/1.0 200 OK\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
                       "👍\r\n"
                       "HTTP/1.0 404 Not Found\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
                       "👎\r\n"
                       "HTTP/1.0 200 OK\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
                       "👍\r\n"
                       "requests: 0003 ok_responses: 0002 error_responses: 0001\r\n")

    async def driver(ctx):

        async def send_data(data):
            ctx.set(dut.session.inbound.active, 1)
            await ctx.tick().until(dut.session.outbound.active)
            in_stream = dut.session.inbound.data
            ctx.set(in_stream.valid, 1)
            idx = 0
            while idx < len(data):
                ctx.set(in_stream.payload, ord(data[idx]))
                if ctx.get(in_stream.ready):
                    idx += 1
                await ctx.tick()
            # After all input data is read, deassert inbound session and data valid
            ctx.set(dut.session.inbound.active, 0)
            ctx.set(in_stream.valid, 0)
            # Keep driving clock until the outbound session is deasserted
            await ctx.tick().until(~dut.session.outbound.active)
            # assert not ctx.get(dut.session.outbound.data.valid)

        await send_data(led_input)
        await send_data(error_input)
        await send_data(count_input)

        assert ctx.get(dut.red) == 0x12
        assert ctx.get(dut.green) == 0x34
        assert ctx.get(dut.blue) == 0x56

        # Add some nice margins for our vcd
        await ctx.tick()

    sim.add_testbench(driver)

    collector = StreamCollector(stream=dut.session.outbound.data)
    sim.add_process(collector.collect())

    sim.run_until(0.001)

    # Now that the test is done:
    collector.assert_eq(expected_output)

def test_coffee_handling():
    dut = SimpleLedHttp()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    input = ("BREW /coffee HTTP/1.0\r\n"
             "Host: curious_test\r\n"
             "User-Agent: evil-agent\r\n"
             "Content-Type: text/bad\r\n"
             "\r\n"
             "Black, medium roast Ethiopian, pour over\r\n")
    expected_output = ("HTTP/1.0 418 I'm a teapot\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
                       "short and stout\r\n")

    async def driver(ctx):
        ctx.set(dut.session.inbound.active, 1)
        await ctx.tick().until(dut.session.outbound.active)

        in_stream = dut.session.inbound.data
        ctx.set(in_stream.valid, 1)
        idx = 0
        while idx < len(input):
            ctx.set(in_stream.payload, ord(input[idx]))
            if ctx.get(in_stream.ready):
                idx += 1
            await ctx.tick()
        # After all input data is read, deassert inbound session
        ctx.set(dut.session.inbound.active, 0)
        # Keep driving clock until the outbound session is deasserted
        await ctx.tick().until(~dut.session.outbound.active)
        assert not ctx.get(dut.session.outbound.data.valid)

        # Add some nice margins for our vcd
        await ctx.tick()

    sim.add_testbench(driver)

    collector = StreamCollector(stream=dut.session.outbound.data)
    sim.add_process(collector.collect())

    sim.run_until(0.001)

    # Now that the test is done:
    collector.assert_eq(expected_output)
