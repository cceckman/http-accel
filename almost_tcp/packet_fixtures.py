"""
Test fixtures for sending and receiving packets and streams.
"""
import random
from message_host import Packet


class StreamCollector:
    """
    Collects data from an Amaranth data stream.
    """

    # Set to true to apply random backpressure.
    # Otherwise, the stream is always ready.
    random_backpressure: bool = False

    # The collected body.
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
                # ready = 1
                ctx.set(stream.ready, ready)
        return collector

    def assert_eq(self, other: bytes):
        got = self.body
        want = other
        assert len(got) == len(want), f"got: {len(got)} want: {len(want)}"
        for b in range(len(want)):
            assert got[b] == want[b]

    def __len__(self):
        return len(self.body)


class PacketSender:
    """
    Transmit a packet into an Amaranth data stream.
    """

    # Set to true to apply random delays to input.
    # Otherwise, the stream is always ready.
    random_delay: bool = False

    # The collected body.
    body: bytes = bytes()

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

    def send(self, packet: Packet, stream):
        b = packet.encode()

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
                if counter < len(b):
                    ctx.set(stream.payload, b[counter])
                else:
                    ctx.set(stream.payload, counter % 256)
                valid = self.is_valid()
                ctx.set(stream.valid, valid)

        return sender
