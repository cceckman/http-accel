import sys
from amaranth.sim import Simulator

from simple_led_http import SimpleLedHttp
from almost_tcp.packet_fixtures import StreamCollector


def test_ok_handling():
    dut = SimpleLedHttp()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    input = ("POST /led HTTP/1.0\r\n"
             "Host: test\r\n"
             "User-Agent: test-agent\r\n"
             "Content-Type: text/plain\r\n"
             "\r\n"
             "\r\n"
             "123456\r\n")
    expected_output = ("HTTP/1.0 200 OK\r\n"
                       "Host: Fomu\r\n"
                       "Content-Type: text/plain; charset=utf-8\r\n"
                       "\r\n"
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

        # TODO: #3 -- Implement getting LED colors from the message.
        #   assert ctx.get(dut.red) == 0x12
        #   assert ctx.get(dut.green) == 0x34
        #   assert ctx.get(dut.blue) == 0x56

        # Add some nice margins for our vcd
        await ctx.tick()

    sim.add_testbench(driver)

    collector = StreamCollector()
    sim.add_process(collector.collect(dut.session.outbound.data))

    # Doesn't appear to be a way to _remove_ a testbench;
    # I guess .reset() is "just" to allow a different initial state?
    with sim.write_vcd(sys.stdout):
        sim.run_until(0.1)

    # Now that the test is done:
    collector.assert_eq(expected_output)


if __name__ == "__main__":
    # TODO: #3 enable this test
    test_ok_handling()
