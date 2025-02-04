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
from asyncio import locks, Queue, QueueEmpty


class NotEnoughDataError(Exception):
    """
    Exception raised when there is not enough data to encode/decode a packet.
    """

    def __init__(self, message=""):
        if self.message:
            self.add_note(message)


class ConnectionFailedError(Exception):
    """
    Exception raised when a connection cannot be established.
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
        # We've consumed len(p) bytes of data from the buffer.
        # Update the buffer.
        self._buffer = self._buffer[len(p):]

        # Check if we have a stream to send it to.
        if p.header.stream in self._active_streams:
            self._active_streams[p.header.stream]._handle_recv(p)
        elif not p.header.flags.rst:
            self.log.info(
                f"received packet for stream {p.header.stream} " +
                "which is not connected")
            # We received a non-reset packet for a stream we don't have.
            # respond with a reset.
            packet = Packet(
                header=Header(
                    flags=Flags(rst=True),
                    stream=p.header.stream,
                ), body=bytes())
            self._send_packet(packet)
        else:
            self.log.info(
                f"received RST for disconnected stream {p.header.stream}")

    def send_packet(self, packet: Packet):
        # The transport layer takes care of buffering.
        self._transport.write(packet.encode())

    def connect(self, recv_size=4096) -> "AlmostTCPStream":
        """
        Create a new connection.

        Use the returned object with an async context manager:
            async with atcp.connect() as conn:
                await conn.write("GET / HTTP/1.1")

        Arguments:
            recv_size: integer, how many bytes in the receive buffer.
        """
        return AlmostTCPStream(self, self.log, _recv_size=recv_size)

    def _claim_stream(self, stream_obj: "AlmostTCPStream") -> int:
        """
        Lay claim to a candidate stream identifier,
        registering for it in the stream dictionary.

        Returns: the stream ID assigned to this stream.
        """
        for i in range(self._next_stream):
            if i not in self._active_streams:
                self._active_streams[i] = stream_obj
                return i
        # Didn't get a hit; use next_stream.
        i = self._next_stream
        self._active_streams[i] = stream_obj
        self._next_stream += 1
        return i

    def _disconnect_stream(self, stream: "AlmostTCPStream"):
        """
        Disconnect the stream in the internal database, and send a reset.
        """
        stream_id = stream._stream_id
        if (stream_id in self._active_streams
                and self._active_streams[stream_id] == stream):
            # Yes, this is indeed the stream registered for that ID.
            del self._active_streams[stream_id]
            self.send_packet(Packet(
                Header(flags=Flags(rst=True), stream=stream_id),
                body=bytes()
            ))


class AlmostTCPStream:
    """
    A single almost-TCP stream, from a connector.

    Use this in an 'async with' context to actually connect.
    """

    log: logging.Logger

    # The parent connection multiplexer
    _packetizer: AlmostTCP
    # Which stream we are
    _stream_id: Optional[int] = None
    # Initial (constructed / reset) size of the receive window.
    _recv_size: int

    # Bytes that have not yet been acknowledged by the receiver.
    # They may not have been sent either!
    _send_buffer: bytes = bytes([0])
    # How many bytes remain in the receiver's window, i.e. how many we can send
    # before blocking on an acknowledgement
    _send_window: int = 0
    # Sequence number: of the byte at the beginning of _send_buffer
    _sequence: int = 0
    # Sequence number: of the first unsent packet.
    _sent: int = 0

    # Whether this end has closed the stream; no more data to be sent.
    _send_closed: bool = False

    # How many bytes we will accept (in the receive buffer).
    _recv_window: int
    _recv_buf: bytes()
    _recv_notify: locks.Condition = locks.Condition

    # Peer's sequence number: the number of the next byte we expect.
    _expected: Optional[int] = None
    # Whether the peer has closed the stream; no more data to receive.
    _recv_closed: bool = False

    def __init__(self, packetizer: AlmostTCP, log: logging.Logger):
        self._packetizer = packetizer

    async def read(self, max: int) -> bytes:
        """
        Read up to N bytes from the stream.

        Raises:
            EOFError at end-of-stream.
        """
        await self._recv_notify.wait_for(
            lambda: (len(self._recv_buf) > 0) or self._recv_closed)
        length = min(len(self._recv_buf), max)
        result = self._recv_buf[length:]
        self._recv_buf = self._recv_buf[:length]
        self._recv_window += length
        if length > 0 and self._recv_window > 0:
            # Allow the sender to send more data.
            # We don't do delayed ack -- just send it right away.
            self._send()

        if length == 0 and self._recv_closed:
            raise EOFError()

        return result

    async def write(self, data: bytes):
        """
        Send the provided bytes into the stream.

        Raises:
            EOFError if the stream has already been closed.
        """
        if self._send_closed:
            raise EOFError("stream closed")

        self._send_buffer += data
        if self._send_window > 0:
            # If we're already backpressured, just wait.
            self._send()
        # TODO: try send_size

    def _handle_recv(self, packet: Packet):
        """
        Handle receipt of a packet.
        """

        if packet.header.rst:
            self.log.warn(f"got RST for stream {self._stream_id}")
            self._send_closed = True
            self._recv_closed = True
            self._recv_notify.notify_all()
            return

        bytes_acked = 0
        if packet.header.ack:
            # Ack field is significant, handle acknowledgement.
            # TODO: Handle wrapping
            assert packet.header.ack >= self._sequence
            if packet.header.ack > self._sent:
                self.log.warn(
                    f"stream {self._stream_id} received invalid ACK: " +
                    f"acked up to {packet.header.ack}, but " +
                    f"{self._sent} was the last sent")
            else:
                bytes_acked = packet.header.ack - self._sequence
                self._send_buffer = self._send_buffer[bytes_acked:]
                # Send recv_notify for synack notification too.
                # TODO: A little noisy during normal operation.
                self._recv_notify.notify_all()
        # TODO: Acknowledge handling of "fin";
        # not handling it properly right now.
        self._send_window = packet.header.window

        if packet.heaer.syn:
            # The syn byte occupies a virtual first-byte-in-stream position.
            self._expected = packet.header.seq + 1
            # Ignore this when processing the data in the packet, if any.
            packet.header.seq += 1
            self._recv_notify.notify_all()

        assert packet.header.length == len(packet.body)
        # TODO: handle wrapping properly
        next_byte = min(self._recv_window,
                        packet.header.seq + packet.header.length)
        # New bytes received: We received data that we haven't seen before.
        new_bytes_received = next_byte > self._expected
        # Old bytes received: We received data that we had already acknowledged
        # (Or, we assume we had acked it.)
        old_bytes_received = packet.header.seq < self._expected

        if new_bytes_received > 0:
            self._recv += packet.body[:-new_bytes_received]
            self._recv_window -= new_bytes_received
            assert self._recv_window >= 0
            self._expected = next_byte
            self._recv_notify.notify()

        if packet.fin:
            self._recv_closed = True
            # FIN occupies a virtual byte; we acknowlege the FIN by acking
            # data so far + 1.
            self._expected += 1
            self._recv_notify.notify()

        # Do we have data to send, after window updates etc?

        if new_bytes_received or old_bytes_received or (
            len(self._send_window) > 0 and len(self._send_buffer) > 0
        ):
            self._send()

    def _send(self):
        """
        Send: acknowledge data receipt, send data if the window permits.
        """
        bytes_to_send = min(self._send_window, len(self._send_buffer))
        body = self._send_buffer[bytes_to_send:]
        # TODO: We shouldn't actually "ack" unless we've synchronized.
        p = Packet(
            Header(flags=Flags(ack=True, fin=self._send_closed),
                   stream=self._stream_id,
                   seq=self._sequence,
                   ack=self._expected,
                   window=self._recv_window,
                   length=bytes_to_send,
                   ),
            body=body
        )
        # TODO: Is this right?
        self._sent = self._sequence + bytes_to_send
        self._packetizer.send_packet(p)

    def finish(self):
        """
        Report that no more data will be sent, and gracefully shut down.
        """
        # TODO: Gracefully!
        self._reset()

    def _reset(self):
        """
        Force a reset of the connection, disconnect from packet receipt.
        """
        self._send_closed = True
        self._recv_closed = True
        self._recv_notify.notify_all()
        if self._stream_id is not None:
            self._packetizer._disconnect_stream(self)
        self._stream_id = None

    async def __aenter__(self):
        await self.open()

    async def open(self):
        """
        Open this connection.

        """
        for i in range(10):
            # Reset state:
            self._send_buffer = bytes([0])  # SYN placeholder
            # TODO: Make this 2**16 - 10, exercise wraparound handling.
            self._sequence = 10
            self._recv_buf = bytes()
            self._recv_window = self._recv_size
            self._recv_closed = False
            self._send_closed = False
            self._expected = None
            try:
                while True:
                    self._incoming.get_nowait()
            except QueueEmpty:
                pass

            init_sequence = self._sequence

            syn = Packet(
                header=Header(
                    flags=Flags(syn=True),
                    stream=self._stream_id,
                    seq=self._sequence,
                    window=self._recv_window,
                ),
                body=bytes()
            )
            self._sent = self._sequence + 1
            self._packetizer.send_packet(syn)

            self._stream = self._packetizer._claim_stream(self)
            # Wait for "reset or synced":
            await self._recv_notify.wait_for(
                lambda:
                (self._recv_closed and self._send_closed)  # reset
                or (self._expected is not None  # synced
                    and self._sequence > init_sequence)
            )
            if self._recv_closed and self._send_closed:
                self.log.warn(
                    f"early close for stream {self._stream_id}; reset")
                continue
            self.log.info(
                f"stream {self._stream_id} synced: " +
                f"local seq {self._sequence}, " +
                f"ack {self._expected}")

        # TODO: Consider blocking until a connection frees up.
        raise ConnectionError("could not find an open stream")

    async def __aexit__(self):
        # TODO: Graceful-with-a-timeout?
        self._reset()
