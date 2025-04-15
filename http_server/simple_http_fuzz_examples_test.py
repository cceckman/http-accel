import sys
import string

from amaranth.sim import Simulator

from .simple_led_http import SimpleLedHttp
from stream_fixtures import StreamCollector
from hypothesis import given, strategies as st, settings, Phase, Verbosity
from hypothesis.errors import InvalidArgument

def run_fuzz_http_request(method, path, headers, body): 
    """
    Same test as in simple_http_fuzz_test, but for manually re-running examples.
    """
    dut = SimpleLedHttp()
    sim = Simulator(dut)
    sim.add_clock(1e-6)

    header = "".join(f"{k} : {v}\r\n" for k,v in headers.items())

    input = f"{method} {path} HTTP/1.0\r\n{header}\r\n\r\n{body}"
    sys.stderr.write(f"Testing with {input}")


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
        ctx.set(dut.session.inbound.active, 0)
        await ctx.tick().until(~dut.session.outbound.active)
        assert not ctx.get(dut.session.outbound.data.valid)
        await ctx.tick()

    sim.add_testbench(driver)
    collector = StreamCollector(stream=dut.session.outbound.data)
    sim.add_process(collector.collect())
    with sim.write_vcd(sys.stdout):
        sim.run_until(0.01)

    # All we're really checking is that every packet gets _some_ kind of response.
    assert len(collector) != 0

def test_simple_get():
    run_fuzz_http_request("POST", "/led", {}, "") 