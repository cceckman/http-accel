import sys
from amaranth.sim import Simulator

from .parse_start import ParseStart
from stream_fixtures import StreamSender

paths = ["/led", "/count"]
PATH_NO_MATCH = 0
PATH_LED = 1
PATH_COUNT = 2


def run_test(send_line, check):
    dut = ParseStart(["/led", "/count"])
    sender = StreamSender(stream=dut.input)
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    checked = False

    async def driver(ctx):
        nonlocal checked
        ctx.set(dut.reset, 1)
        ctx.tick()
        ctx.set(dut.reset, 0)

        while not sender.done:
            await ctx.tick()
        check(ctx, dut)
        checked = True

    sim.add_testbench(driver)
    sim.add_process(sender.send_passive(map(ord, send_line)))

    with sim.write_vcd(sys.stdout):
        sim.run_until(0.0001)
    assert checked


def test_good_parse():
    def check(ctx, dut):
        assert ctx.get(dut.method[dut.METHOD_NO_MATCH]) == 0
        assert ctx.get(dut.method[dut.METHOD_GET]) == 0
        assert ctx.get(dut.method[dut.METHOD_POST]) == 1
        assert ctx.get(dut.path[PATH_NO_MATCH]) == 0
        assert ctx.get(dut.path[PATH_LED]) == 1
        assert ctx.get(dut.path[PATH_COUNT]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_NO_MATCH]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_HTTP1_0]) == 1

    run_test("POST /led HTTP/1.0\r\n", check)


def test_no_method_match():
    def check(ctx, dut):
        assert ctx.get(dut.method[dut.METHOD_NO_MATCH]) == 1
        assert ctx.get(dut.method[dut.METHOD_GET]) == 0
        assert ctx.get(dut.method[dut.METHOD_POST]) == 0
        assert ctx.get(dut.path[PATH_NO_MATCH]) == 0
        assert ctx.get(dut.path[PATH_LED]) == 1
        assert ctx.get(dut.path[PATH_COUNT]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_NO_MATCH]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_HTTP1_0]) == 1

    run_test("REQUEST /led HTTP/1.0\r\n", check)


def test_no_protocol_match():
    def check(ctx, dut):
        assert ctx.get(dut.method[dut.METHOD_NO_MATCH]) == 0
        assert ctx.get(dut.method[dut.METHOD_GET]) == 1
        assert ctx.get(dut.method[dut.METHOD_POST]) == 0
        assert ctx.get(dut.path[PATH_NO_MATCH]) == 0
        assert ctx.get(dut.path[PATH_LED]) == 0
        assert ctx.get(dut.path[PATH_COUNT]) == 1
        assert ctx.get(dut.protocol[dut.PROTOCOL_NO_MATCH]) == 1
        assert ctx.get(dut.protocol[dut.PROTOCOL_HTTP1_0]) == 0

    run_test("GET /count HTTP/3.0\r\n", check)


def test_no_path_match():
    def check(ctx, dut):
        assert ctx.get(dut.method[dut.METHOD_NO_MATCH]) == 0
        assert ctx.get(dut.method[dut.METHOD_GET]) == 1
        assert ctx.get(dut.method[dut.METHOD_POST]) == 0
        assert ctx.get(dut.path[PATH_NO_MATCH]) == 1
        assert ctx.get(dut.path[PATH_LED]) == 0
        assert ctx.get(dut.path[PATH_COUNT]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_NO_MATCH]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_HTTP1_0]) == 1

    run_test("GET /index.html HTTP/1.0\r\n", check)


def test_double_start_line():
    def check(ctx, dut):
        assert ctx.get(dut.method[dut.METHOD_NO_MATCH]) == 0
        assert ctx.get(dut.method[dut.METHOD_GET]) == 1
        assert ctx.get(dut.method[dut.METHOD_POST]) == 0
        assert ctx.get(dut.path[PATH_NO_MATCH]) == 1
        assert ctx.get(dut.path[PATH_LED]) == 0
        assert ctx.get(dut.path[PATH_COUNT]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_NO_MATCH]) == 0
        assert ctx.get(dut.protocol[dut.PROTOCOL_HTTP1_0]) == 1

    # TODO: #4 - This should raise an error so the HTTP responder can return a 400 Bad Request.
    run_test("GET /index.html HTTP/1.0\rPOST /help HTTP/1.1\r\n", check)


if __name__ == "__main__":
    test_good_parse()
    test_no_method_match()
    test_no_path_match()
    test_no_protocol_match()
    test_double_start_line()
