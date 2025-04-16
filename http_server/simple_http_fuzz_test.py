import sys
import string

from amaranth.sim import Simulator

from .simple_led_http import SimpleLedHttp
from stream_fixtures import StreamCollector
from hypothesis import given, strategies as st, settings, Phase, Verbosity
from hypothesis.errors import InvalidArgument

st_methods = st.sampled_from(["GET", "POST", "PUT", "DELETE", "BREW"])
st_paths = st.sampled_from(["/", "/led", "/count", "/coffee", "/asdf"])

st_header_names = st.sampled_from(["Host", "User-Agent", "Content-Type", 
                                    "Content-Length", "Accept", "Accept-Additions" "Cookie"])
st_header_values = st.text(
    alphabet=st.characters(codec='utf-8', exclude_characters="\r\n"),
    min_size=1,
    max_size=32)
st_headers = st.dictionaries(st_header_names, st_header_values, min_size=0, max_size=10)

st_bodies = st.text(
    alphabet=st.characters(codec='utf-8'),
    min_size=0,
    max_size=256)

@settings(
    max_examples=2, # Increase for more testing.
    verbosity=Verbosity.normal,
    deadline=None,
)
@given(
    method=st_methods,
    path=st_paths,
    headers=st_headers,
    body=st_bodies
)
def test_fuzz_http_request(method, path, headers, body): 
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
    sim.run_until(0.01)

    # All we're really checking is that every packet gets _some_ kind of response.
    sys.stderr.write(f"Got resonse {collector.body}")
    assert len(collector) != 0