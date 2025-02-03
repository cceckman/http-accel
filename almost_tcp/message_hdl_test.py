from amaranth.sim import Simulator

from message_hdl import PacketReader
from message_host import Header

import random

dut = PacketReader()

body = bytes()


async def packet_sender(ctx):
    b = bytes([
        0xA5,  # CWR, URG, RST, FIN
        0x3,  # stream number
        # Big-endian numbers:
        0x04, 0x01,  # size: 260
        0x02, 0x03,  # window: 770
        0x01, 0x10,  # seq: 4097
        0x02, 0x30,  # ack: 12290
    ])
    counter = 0
    valid = 1
    ctx.set(dut.input.valid, valid)
    ctx.set(dut.input.payload, b[counter])
    async for clk_edge, rst_value, ready in ctx.tick().sample(dut.input.ready):
        if ready == 1 and valid == 1:
            # We just transferred the byte.
            counter += 1
        # Update the payload:
        if counter < len(b):
            ctx.set(dut.input.payload, b[counter])
        else:
            ctx.set(dut.input.payload, counter % 256)
        # And randomly pick whether or not we're ready on the next tick:
        valid = random.randint(0, 1)
        # valid = 1
        ctx.set(dut.input.valid, valid)


async def packet_receiver(ctx):
    global body
    ready = 1
    ctx.set(dut.data.ready, ready)
    async for clk_edge, rst_value, valid, payload in ctx.tick().sample(
            dut.data.valid, dut.data.payload):
        if not clk_edge:
            continue
        if ready == 1 and valid == 1:
            assert (payload % 256) == payload
            # We just transferred the payload byte.
            body = body + bytes([payload])
        # And randomly pick whether or not we're ready on the next tick:
        ready = random.randint(0, 1)
        # ready = 1
        ctx.set(dut.data.ready, ready)


async def bench(ctx):
    global body

    while ctx.get(dut.stream_valid) != 1:
        await ctx.tick()
    assert ctx.get(dut.stream_valid)
    assert ctx.get(dut.header.stream) == 0x3
    assert not ctx.get(dut.header_valid)

    while ctx.get(dut.header_valid) != 1:
        await ctx.tick()
    assert ctx.get(dut.stream_valid)
    assert ctx.get(dut.header_valid)
    assert ctx.get(dut.header.flags.fin)
    assert ctx.get(dut.header.flags.rst)
    assert ctx.get(dut.header.flags.urg)
    assert ctx.get(dut.header.flags.cwr)
    assert not ctx.get(dut.header.flags.syn)
    assert not ctx.get(dut.header.flags.psh)
    assert not ctx.get(dut.header.flags.ack)
    assert not ctx.get(dut.header.flags.ecn)
    assert ctx.get(dut.header.stream) == 0x3
    assert ctx.get(dut.header.length) == 260
    assert ctx.get(dut.header.window) == 770
    assert ctx.get(dut.header.seq) == 4097
    assert ctx.get(dut.header.ack) == 12290

    # Wait until all the data are read:
    while ctx.get(dut.header_valid):
        await ctx.tick()

    assert len(body) == 260, f"got: {len(body)} want: 260"
    for b in range(260):
        got = body[b]
        want = (b + Header.BYTES) % 256
        assert got == want

# Doesn't appear to be a way to _remove_ a testbench;
# I guess .reset() is "just" to allow a different initial state?
if __name__ == "__main__":
    import sys

    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_process(packet_sender)
    sim.add_process(packet_receiver)
    sim.add_testbench(bench)

    with sim.write_vcd(sys.stdout):
        sim.run()
