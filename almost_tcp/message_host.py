"""
Host-side implementation of the Almost TCP protocol.
"""

import sys
from dataclasses import dataclass
from typing import Dict
import itertools
import struct
import contextlib
from asyncio import locks, Queue


class AlmostTcpStreams:
    """
    Read and write access to the Almost TCP streams.
    """

    def __init__(self, conn):
        self._conn = conn
        self._server_closed = False
        self._queue = Queue()
        self._buffer = bytes()

    async def write(self, buffer):
        """
        Write the provided bytes to the stream.
        """
        pass

    async def read(self, limit) -> bytes:
        """
        Read up to the provided number of bytes from the stream.
        May return fewer bytes than limit; always blocks until
        some bytes are available.
        """
        # Pull up to limit bytes from the buffer:
        def from_buffer():
            result = self._buffer[:limit]
            self._buffer = self._buffer[limit:]
            return result

        # Return from the local buffer first,
        # even if it's for fewer bytes than desired.
        if len(self._buffer) != 0:
            return from_buffer()

        # Otherwise, refill the buffer and send what we can.
        self._buffer = await self._queue.get()
        return from_buffer()


class ConnectionFailedError(Exception):
    pass


class AlmostTcpConnection(contextlib.AbstractAsyncContextManager):
    """
    A connection manager to an Almost TCP server.

    Each entry and exit to the context manager results in a new connection.
    """

    def __init__(self, connector):
        self._connector = connector
        self.queue = asyncio.Queue()

        # Transmission Control Block:
        self._stream_number = None
        self._local_window = 256
        self._remote_window = 0

        # All unacknowledged bytes to be sent.
        self._send_buffer = bytes()
        # The last byte that was acknowledged by the receiver.
        # This also gives the sequence number of the first
        # byte in the buffer.
        self._last_acked = 7

        # The next byte that we expect == the last byte we acked.
        self._rcv_sequence = 0

    def pick_stream_id(self) -> int:
        """
        Subroutine of a connection: pick stream ID to attempt a connection on.

        Requires the _connector mutex is held.
        """
        # Pick the lowest number that is not in the table.
        for i in range(0, 256):
            if self._connector.streams.get(i) is None:
                return i
        raise ConnectionFailedError("no streams available")

    def prep_header(self, len) -> Header:
        """
        Prepare a header for len bytes of data.
        Does not set any flags.

        """
        h = Header()
        h.length = len
        h.stream = self._stream_number
        h.window = self._local_window
        h.seq = self._last_acked
        h.ack = self._rcv_sequence
        return h

    async def attempt_connection(self):
        # A single cycle of attempting a connection.
        # Pick an unused sequence number, attempt to connect to it.
        async with self._connector.mu:
            self._stream_number = self.pick_stream_id()
            # TODO Attempt a connection.
            # We have to set up the stream to get the responses.
            self._connector.streams[self._stream_number] = self
            # We have the connector lock; send a syn message.
            h = self.prep_header(0)
            h.flags.sync = True
            await self._connector.send(h, bytes())

        # Now we wait for the return...
        packet = await self.queue.get()
        flags = packet.header.flags
        if (not flags.rst
                and flags.syn
                and flags.ack
                and packet.header.ack == self._last_acked + 1):
            # Update our acknowledgement
            self._last_acked = packet.header.ack
            # Synchronize their sequence number.
            # The "syn" occupies the first byte.
            self._rcv_sequence = packet.header.seq + 1
            # Send the acknowledgement:
            h = self.prep_header(0)
            h.flags.ack = True
            await self._connector.send(h, bytes())

            # TODO: Link up receiver path, to push down into streams buffer

            return
        raise ConnectionFailedError(
            "got improper acknowledgement for stream {}: {}".format(
                self._stream_number, packet))

    async def __aenter__(self) -> AlmostTcpStreams:
        while True:
            try:
                await self.attempt_connection()
                return AlmostTcpStreams(self)
            except ConnectionFailedError as e:
                sys.stderr.write("failed to connect: {}\n".format(e))
            # Fall back to waiting for a stream ID to open up.
            await self._connector.stream_notify.acquire()

    async def __aexit__(self):
        # Close the ATCP stream.
        # TODO: Protocol-level stuff

        # Release the stream ID.
        async with self._connector.mu:
            self._connector.streams.pop(self._stream_number)
            self._connector.stream_notify.increment(1)


class AlmostTcpClientConnector:
    """
    Host-side hookup to an Almost TCP server.

    Since ATCP works over serial, there has to be one "owner" of the serial
    connection. That's this class.

    Typical usage:

        import asyncio

        async with AlmostTcpClientConnector("/dev/ttyS1") as connector:
            async with connector.connect() as conn:
                # Read and write concurrently,
                # to avoid hardware buffering limitations
                async with asyncio.TaskGroup as tg:
                    tg.create_task(conn.write("GET / HTTP/1.0\r\n\r\n"))
                    results = tg.create_task(conn.read("GET / HTTP/1.0\r\n\r\n"))
                )
                print(results)
        print("closed connection")
    """

    mu = locks.Lock()

    # The next stream ID to try to connect to.
    next_stream: int = 0
    # The maximum stream ID that we've successfully connected to.
    max_stream: int = 0
    # All streams currently active.
    streams: Dict[int, AlmostTcpConnection] = dict()
    # Wait for a stream to become available.
    # Every successful stream-closure increments this,
    # so it's a decent signal that a stream should be available.
    stream_notify: locks.Condition = locks.Semahore()

    def __init__(self, serial_path):
        self.serial = open(serial_path, "bar", buffering=0)

    async def __aenter__(self):
        # TODO: Start the reader coroutine

    async def __aexit(self):
        # TODO: Shut down the reader coroutine

    def connect(self) -> AlmostTcpConnection:
        return AlmostTcpConnection(self)


@ dataclass
class Flags:
    """
    Host-side codec for the flags structure.
    """
    fin: bool = False
    syn: bool = False
    rst: bool = False
    psh: bool = False
    ack: bool = False
    urg: bool = False
    ecn: bool = False
    cwr: bool = False

    def encode(self):
        x = 0
        for (i, v) in itertools.zip_longest(range(0, 8), [
                self.fin, self.syn, self.rst, self.psh,
                self.ack, self.urg, self.ecn, self.cwr]):
            x |= v << i

        return bytes([x])

    def decode(buffer):
        z = buffer[0]
        x = Flags()
        x.fin = ((z >> 0) & 1) == 1
        x.syn = ((z >> 1) & 1) == 1
        x.rst = ((z >> 2) & 1) == 1
        x.psh = ((z >> 3) & 1) == 1
        x.ack = ((z >> 4) & 1) == 1
        x.urg = ((z >> 5) & 1) == 1
        x.ecn = ((z >> 6) & 1) == 1
        x.cwr = ((z >> 7) & 1) == 1
        return x


@dataclass
class Header:
    """
    Almost TCP header structure.
    """
    flags: Flags
    stream: int
    length: int
    window: int
    seq: int
    ack: int

    def encode(self):
        return self.flags.encode() + struct.pack(
            "!BHHHH",
            self.stream, self.length, self.window, self.seq, self.ack)

    def decode(buffer):
        flags = Flags.decode(buffer)
        (stream, length, window, seq, ack) = struct.unpack(
            "!BHHHH", buffer[1:])
        return Header(flags, stream, length, window, seq, ack)


@dataclass
class Packet:
    """
    Almost TCP packet structure.
    """
    header: Header
    body: bytes
