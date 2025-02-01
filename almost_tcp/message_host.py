"""
Host-side implementation of the Almost TCP protocol.
"""

import logging
import serial
import serial_asyncio
import asyncio
import sys
from dataclasses import dataclass
from typing import Dict, Optional
import itertools
import struct
import contextlib
from asyncio import locks, Queue


class NotEnoughDataError(Exception):
    """
    Exception raised when there is not enough data to encode/decode a packet.
    """

    def __init__(self, message=""):
        if self.message:
            self.add_note(message)


@dataclass
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

    # Number of bytes in the header.
    BYTES = 10

    flags: Flags
    stream: int
    length: int = 0
    window: int = 0
    seq: int = 0
    ack: int = 0

    def __len__(self):
        return Header.BYTES

    def encode(self):
        return self.flags.encode() + struct.pack(
            "!BHHHH",
            self.stream, self.length, self.window, self.seq, self.ack)

    def decode(buffer):
        if len(buffer) < Header.BYTES:
            raise NotEnoughDataError(
                f"not enough bytes for header: {len(buffer)} < 10")
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

    def __len__(self):
        return len(self.header) + len(self.body)

    def decode(buffer):
        header = Header.decode(buffer)
        tail = buffer[Header.BYTES:]
        if len(tail) < header.length:
            raise NotEnoughDataError(
                f"not enough bytes for body: {len(tail)} < {header.length}")
        body = tail[:header.length]

        return Packet(header, body)

    def encode(self):
        return self.header.encode() + self.body


class AlmostTCP(asyncio.Protocol):
    """
    AsyncIO protocol for AlmostTCP.

    AlmostTCP multiplexes streams across a serial transport,
    including providing flow-control for those streams.
    This provides the lower layer: packets across the serial stream.
    """

    _transport: Optional[asyncio.Transport] = None
    _next_stream: int = 0
    _active_streams: Dict[int, "AlmostTCPStream"] = dict()
    _buffer: bytes = bytes()

    log: logging.Logger = logging.getLogger(__name__)

    def connection_made(self, transport: asyncio.Transport):
        """
        "Connected" callback for the serial layer.
        """
        self._transport = transport

    def connection_lost(self, exc):
        self._transport = None

    def data_received(self, data: bytes):
        self._buffer += data
        self.log.debug(
            f"received {len(data)} bytes, {len(self._buffer)} total")

        # Check if we have a complete packet:
        try:
            p = Packet.decode(self._buffer)
        except NotEnoughDataError as e:
            self.log.debug(f"skipping processing: {e}")
            # That's fine, wait for more data.
            return
        # Trim the buffer:
        self._buffer = self._buffer[:len(p)]

        # Check if we have a stream to send it to.
        if p.header.stream in self._active_streams:
            self._active_streams[p.header.stream]._incoming.put(p)
        elif not p.header.flags.rst:
            # We received a non-reset packet for a stream we don't have.
            # respond with a reset.
            flags = Flags(rst=True)
            header = Header(flags, stream=p.header.stream)
            packet = Packet(header, body=bytes())
            self._send_packet(packet)

    def send_packet(self, packet: "Packet"):
        # TODO: Handle write-side buffering?
        self._transport.write(packet.encode())

    def connect(self) -> "AlmostTCPStream":
        """
        Create a new connection.

        Use the returned object with an async context manager:
            async with atcp.connect() as conn:
                await conn.write("GET / HTTP/1.1")
        """
        return AlmostTCPStream(self)


class AlmostTCPStream:
    """
    A single almost-TCP stream, from a connector.

    Use this in an 'async with' context to actually connect.
    """

    # The parent connection multiplexer
    _packetizer: AlmostTCP
    # Which stream we are
    _stream_id: int

    # Bytes that have not yet been acknowledged by the receiver
    _send_buffer: bytes = [0]
    # Sequence number: the number of the byte at the beginning of _send_buffer
    _sequence: int = 0
    # Whether this end has closed the stream; no more data to be sent.
    _send_closed: bool = False

    # Peer's sequence number: the number of the next byte we expect.
    _expected: int = 0
    # Whether the peer has closed the stream; no more data to receive.
    _rcv_closed: bool = False

    # Packets incoming on this stream, to be processed
    _incoming: Queue = Queue()

    def __init__(self, packetizer: AlmostTCP):
        self._packetizer = packetizer

    async def __aenter__(self):
        # Try to claim a sequence number, synchronize.
        pass

    async def __aexit__(self):
        # FIN the connection with a timeout, then just reset.
        pass
