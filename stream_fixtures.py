"""
Test fixtures for sending and receiving in streams.
"""
import sys
import time
import random
import queue
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

    def collect_queue(self, q: queue.Queue[bytes], batch_size: int = 100,
                      timeout=100):
        """
        Collect bytes into the provided queue.

        Returns a coroutine suitable as a test process, which feeds bytes from
        the stream into a queue.

        Arguments
        ---------
        q:      the queue to write bytes into. Note that collect_queue does not
                shut down the queue; the listener must have some other way to
                respond.
        batch_size: Default number of bytes to wait for before forwarding into
                    the queue. If the batch_size is reached, the bytes received
                    are immediately sent into the queue.
        timeout:    Number of cycles to wait before forwarding more bytes into
                    the queue, if fewer than batch_size are received.
        """

        stream = self._stream

        async def collector(ctx):
            ctx.set(stream.ready, 1)
            countup = 0
            batch = bytes()

            async for clk_edge, rst_value, valid, payload in ctx.tick().sample(
                    stream.valid, stream.payload):
                if rst_value or (not clk_edge):
                    continue
                if valid == 1:
                    # We just transferred a payload byte.
                    batch += bytes([payload])
                countup += 1

                batch_exceeded = len(batch) >= batch_size
                countup_exceeded = len(batch) > 0 and countup >= timeout
                if batch_exceeded or countup_exceeded:
                    # Send data.
                    try:
                        q.put(batch, block=False)
                    except queue.Full:
                        sys.stderr.write(
                            f"queue full, saving {len(batch)} bytes "
                            "for later\n"
                        )
                        countup = 0
                        continue
                    except Exception as e:
                        sys.stderr.write(
                            f"error in sending data from sim: {e}\n")
                        return
                    batch = bytes()
                    countup = 0

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

    def send_queue_active(self, q: queue.Queue[bytes], idle_ticks=100):
        """
        Returns a coroutine that drives the simulation while consuming
        from the queue.

        The provided coroutine returns when the queue is shut down
        (python 3.12+?), or when self.done is set.

        Arguments
        ---------
        queue:      Queue of bytes() to consume from.
        idle_ticks: When no data is present, how many ticks to run before
                    checking for more data.
        """
        stream = self._stream

        async def sender(ctx):
            while not self.done:
                try:
                    data = q.get_nowait()
                except queue.Empty:
                    sys.stderr.write("no data ready")
                    data = bytes()
                except queue.ShutDown:
                    sys.stderr.write("send queue shut down")
                    return

                # Send the data we have.
                for datum in data:
                    while True:
                        ctx.set(stream.valid, 1)
                        ctx.set(stream.payload, ord(datum))
                        ready = ctx.get(stream.ready)
                        await ctx.tick()
                        if ready == 1:
                            # Just transferred a byte.
                            # Go to the next datum.
                            break
                ctx.set(stream.valid, 0)
                for _ in range(0, idle_ticks):
                    await ctx.tick()

        return sender

    def send_active(self, data: Iterable[int]):
        """
        Returns a coroutine that drives the simulation while sending the
        provided data.
        The provided coroutine returns when all the data are sent.
        """
        stream = self._stream
        self.done = False

        async def sender(ctx):
            for datum in data:
                valid = self.is_valid()
                while True:
                    ctx.set(stream.valid, valid)
                    ctx.set(stream.payload, datum)
                    ready = ctx.get(stream.ready)
                    await ctx.tick()
                    if ready == 1 and valid == 1:
                        # Just transferred a byte.
                        # Go to the next datum.
                        break
                    else:
                        # Have a chance at becoming valid.
                        valid = valid | self.is_valid()
            # All done with the data input.
            ctx.set(stream.valid, 0)
            self.done = True
        return sender

    def send_passive(self, data: Iterable[int]):
        """
        Returns a coroutine that transmit the given packets serially into stream.
        Does not drive the SUT.
        """
        stream = self._stream
        self.done = False

        async def sender(ctx):
            counter = 0
            # send_len = len(data)
            for datum in data:
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
            # All done with the data input.
            ctx.set(stream.valid, 0)
            self.done = True

        return sender
