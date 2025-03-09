import sys
from amaranth.sim import Simulator

from simple_led_http import SimpleLedHttp

async def test_ok_handling(ctx):
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
    
    ctx.set(dut.request, 1)
    await ctx.tick()
    ctx.set(dut.request, 0)

    ctx.set(dut.input.valid, 1)
    idx = 0
    while idx < len(input):
        ctx.set(dut.input.payload, ord(input[idx]))
        if ctx.get(dut.input.ready):
            idx+=1
        await ctx.tick()

    ctx.set(dut.out.ready, 1)
    collected = []
    while not ctx.get(dut.out.complete):
        if ctx.get(dut.out.valid):
            collected.append(ctx.get(dut.out.payload))
        await ctx.tick()

    assert "".join(collected) == expected_output
    assert ctx.get(dut.red) == 0x12
    assert ctx.get(dut.green) == 0x34
    assert ctx.get(dut.blue) == 0x56


async def bench(ctx):
    # TODO #3 - enable this test.
    # await test_ok_handling(ctx)
    pass

dut = SimpleLedHttp()
sim = Simulator(dut)
sim.add_clock(1e-6)
sim.add_testbench(bench)

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    with sim.write_vcd(sys.stdout):
        sim.run()
