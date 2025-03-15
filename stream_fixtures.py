"""
Test fixtures for sending and receiving in streams.
"""
import random
import sys
from typing import Iterable

__all__ = ["StreamCollector", "StreamSender"]


class StreamCollector:
    """
    Collects raw data from an Amaranth data stream.
    """

    # Set to true to apply random backpressure.
    # Otherwise, the stream is always ready.
    random_backpressure: bool = False

    body: bytes = bytes()

    def __init__(self, stream, random_backpressure=False):
        super().__init__()
        self.random_backpressure = random_backpressure
        self._stream = stream

    def is_ready(self):
        """
        Return a ready value, possibly incorporating random backpressure.
        """

        if self.random_backpressure:
            return random.randint(0, 1)
        else:
            return 1

    def collect(self):
        stream = self._stream

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
                else:
                    # Don't become un-ready until we transver a payload byte.
                    ready = ready | self.is_ready()
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


class StreamSender:
    """
    Transmit bytes into an Amaranth stream.
    """

    # Set to true to apply random delays to input.
    # Otherwise, the stream is always ready.
    random_delay: bool = False

    # Flag bit, signaled when all bytes from all packets have been delivered.
    done: bool = False

    def __init__(self,
                 stream,
                 random_delay=False,
                 ):
        """
        Construct a packet sender.

        Arguments:
        stream: Amaranth stream.Signature(8) component to write the packets to.
        random_delay: Introduce random delay before bytes are ready.
        """
        super().__init__()
        self.random_delay = random_delay
        self._stream = stream

    def is_valid(self):
        """
        Return a valid value, possibly incorporating random delay.
        """

        if self.random_delay:
            return random.randint(0, 1)
        else:
            return 1

    def send_passive(self, data: Iterable[int]):
        """
        Transmit the given packets serially into stream.
        Does not drive the SUT.
        """
        stream = self._stream
        self.done = False

        async def sender(ctx):
            counter = 0
            # send_len = len(data)
            for datum in data:
                # sys.stderr.write(f"writing byte {counter}/{send_len}\n")
                valid = self.is_valid()
                ctx.set(stream.valid, valid)
                ctx.set(stream.payload, datum)
                async for clk_edge, rst_value, ready in (
                        ctx.tick().sample(stream.ready)):
                    if ready == 1 and valid == 1:
                        # We just transferred the byte.
                        # Skip out of the async loop, to the next byte.
                        break
                    else:
                        # Don't become in-valid until the byte is transferred.
                        valid = valid | self.is_valid()
                counter += 1
            # sys.stderr.write("writing done\n")
            # All done with the data input.
            ctx.set(stream.valid, 0)
            self.done = True

        return sender
