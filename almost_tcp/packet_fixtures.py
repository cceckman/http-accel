"""
Test fixtures for sending and receiving packets and streams.
"""
import random
from almost_tcp.message_host import Packet
from typing import List
from functools import reduce


class StreamCollector:
    """
    Collects data from an Amaranth data stream.
    """

    # Set to true to apply random backpressure.
    # Otherwise, the stream is always ready.
    random_backpressure: bool = False

    body: bytes = bytes()

    def __init__(self, random_backpressure=False):
        super().__init__()
        self.random_backpressure = random_backpressure

    def is_ready(self):
        """
        Return a ready value, possibly incorporating random backpressure.
        """

        if self.random_backpressure:
            return random.randint(0, 1)
        else:
            return 1

    def collect(self, stream):
        async def collector(ctx):
            ready = self.is_ready()
            ctx.set(stream.ready, ready)
            async for clk_edge, rst_value, valid, payload in ctx.tick().sample(
                    stream.valid, stream.payload):
                if rst_value or (not clk_edge):
                    continue
                if ready == 1 and valid == 1:
                    # We just transferred a payload byte.
                    self.body = self.body + bytes([payload])
                ready = self.is_ready()
                ctx.set(stream.ready, ready)
        return collector

    def assert_eq(self, other):
        if isinstance(other, str):
            other = other.encode("utf-8")
        elif isinstance(other, bytes):
            pass
        else:
            raise ValueError("other must be a string or byte array")

        got = self.body
        want = other

        debug = f"got body:\n{got}\nwant body:\n{want}"

        assert len(got) == len(want), debug
        for b in range(len(want)):
            assert got[b] == want[b], debug

    def __len__(self):
        return len(self.body)


class MultiPacketSender:
    """
    Transmit multiple packets into an Amaranth data stream.
    """

    # Set to true to apply random delays to input.
    # Otherwise, the stream is always ready.
    random_delay: bool = False

    def __init__(self, random_delay=False):
        super().__init__()
        self.random_delay = random_delay

    def is_valid(self):
        """
        Return a valid value, possibly incorporating random delay.
        """

        if self.random_delay:
            return random.randint(0, 1)
        else:
            return 1

    def send(self, packets: List[Packet], stream):
        byte_arrays = [p.encode() for p in packets]
        b = reduce(lambda a, b: a + b, byte_arrays, bytes())

        async def sender(ctx):
            counter = 0
            valid = self.is_valid()
            ctx.set(stream.valid, valid)
            ctx.set(stream.payload, b[counter])
            async for clk_edge, rst_value, ready in (
                    ctx.tick().sample(stream.ready)):
                if ready == 1 and valid == 1:
                    # We just transferred the byte.
                    counter += 1
                # Update the payload:
                if counter >= len(b):
                    break
                ctx.set(stream.payload, b[counter])
                valid = self.is_valid()
                ctx.set(stream.valid, valid)
            # Break: end of stream.
            ctx.set(stream.valid, 0)

        return sender


class PacketSender(MultiPacketSender):
    """
    Transmit a single packet into an Amaranth data stream.
    """

    def send(self, packet: Packet, stream):
        return super().send([packet], stream)
