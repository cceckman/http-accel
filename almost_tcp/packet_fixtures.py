"""
Test fixtures for sending and receiving packets and streams.
"""
import random
from message_host import Packet, Header, Flags
from typing import List
from functools import reduce
from hypothesis import strategies as st


@st.composite
def arbitrary_packet(
    draw,
    flags=st.integers(0, 255),
    stream=st.integers(0, 255),
    window=st.integers(0, (2**16)-1),
    seq=st.integers(0, (2**16)-1),
    ack=st.integers(0, (2**16)-1),
    body=st.binary(),
):
    """
    Hypothesis strategy for generating an arbitrary packet.
    The length matches the data length.
    """
    body = draw(body)
    length = len(body)
    header = Header(
        flags=Flags.decode(bytes([flags])),
        stream=draw(stream), window=draw(window), seq=draw(seq), ack=draw(ack),
        length=length,
    )
    return Packet(header=header, body=body)


class StreamCollector:
    """
    Collects raw data from an Amaranth data stream.
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

    def assert_eq(self, other: bytes):
        got = self.body
        want = other
        assert len(got) == len(want), f"got: {len(got)} want: {len(want)}"
        for b in range(len(want)):
            assert got[b] == want[b]

    def __len__(self):
        return len(self.body)


class MultiPacketSender:
    """
    Transmit multiple packets into an Amaranth object.
    """

    # Set to true to apply random delays to input.
    # Otherwise, the stream is always ready.
    random_delay: bool = False

    def __init__(self,
                 random_delay=False,
                 stream=None,
                 packet=None
                 ):
        super().__init__()
        self.random_delay = random_delay
        self._stream = stream
        self._packet = packet

    def is_valid(self):
        """
        Return a valid value, possibly incorporating random delay.
        """

        if self.random_delay:
            return random.randint(0, 1)
        else:
            return 1

    def send(self, packets: List[Packet]):
        if self._stream is not None:
            return self.send_stream(packets)
        elif self._packet is not None:
            assert False, "TODO: Support sending into PacketSignature"
        else:
            assert False, "MultiPacketSender is not configured with any output"

    def send_stream(self, packets: List[Packet]):
        byte_arrays = [p.encode() for p in packets]
        b = reduce(lambda a, b: a + b, byte_arrays, bytes())

        async def sender(ctx):
            stream = self._stream
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
    Transmit a single packet into Amaranth.
    """

    def send(self, packet: Packet):
        return super().send([packet])
