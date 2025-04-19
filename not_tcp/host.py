from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass
from enum import IntFlag
from typing import Optional
import asyncio
import logging
import struct

log = logging.getLogger(__name__)


class Flag(IntFlag):
    START = 1
    END = 2
    TO_HOST = 4


@dataclass
class Header:
    """
    Not TCP header.
    """

    flags: Flag

    stream_id: int
    body_length: int

    @classmethod
    def length(cls):
        return 3

    def __len__(self):
        return 3

    def to_bytes(self) -> bytes:
        return struct.pack("BBB", self.stream_id, self.body_length, self.flags)

    def from_bytes(buffer: bytes) -> "Header":
        (stream, length, flags) = struct.unpack("BBB", buffer)
        return Header(
            flags=Flag(flags),
            stream_id=stream,
            body_length=length,
        )


@dataclass
class Packet:
    """
    Not TCP packet.
    """

    flags: Flag = Flag(0)

    stream_id: int = 0
    body: bytes = bytes()

    @property
    def start(self):
        return bool(self.flags & Flag.START)

    @property
    def end(self):
        return bool(self.flags & Flag.END)

    @property
    def to_host(self):
        return bool(self.flags & Flag.TO_HOST)

    @classmethod
    def from_header(cls, header: Header, body: bytes) -> "Packet":
        assert header.body_length == len(
            body), f"{header.body_length} != {len(body)}"
        return Packet(
            flags=header.flags,
            stream_id=header.stream_id,
            body=body
        )

    def __len__(self):
        return len(Header) + len(self.body)

    def header(self) -> Header:
        assert self.stream_id >= 0
        assert self.stream_id < 256

        return Header(self.flags, self.stream_id, body_length=len(self.body))

    def to_bytes(self) -> bytes:
        return self.header().to_bytes() + self.body

    @classmethod
    def from_bytes(cls, buf: bytes) -> (Optional["Packet"], bytes):
        if len(buf) < Header.length():
            return None, buf
        header = Header.from_bytes(buf[:Header.length()])
        body_and_remainder = buf[Header.length():]
        if len(body_and_remainder) < header.body_length:
            return None, buf
        body = body_and_remainder[:header.body_length]
        remainder = body_and_remainder[header.body_length:]
        return (Packet.from_header(header, body), remainder)


# Use as superclass; subclass to simulator or real
class StreamProxy:
    lock = asyncio.Lock()
    request_number = 0

    def send(self, b: bytes()):
        # Must be implemented by subclass
        pass

    def recv(self) -> bytes:
        # Must be implemented by subclass
        pass

    def client_connected(
            self, reader: StreamReader, writer: StreamWriter):
        r = self.request_number = self.request_number + 1
        log.info(f'client {r} connected')
        asyncio.create_task(self.client_loop(r, reader, writer))

    async def client_loop(self, number: int,
                          reader: StreamReader, writer: StreamWriter):
        async with self.lock, asyncio.TaskGroup() as tg:
            log.info(f'starting client {number} handler')
            tg.create_task(self.run_inbound(number, reader))
            tg.create_task(self.run_outbound(number, writer))
        log.info(f'completed client {number} handlers')

    async def run_inbound(self, number: int, reader: StreamReader):
        p1 = Packet(flags=Flag.START, stream_id=1, body=bytes())
        self.send(p1.to_bytes())
        want_bytes = 256
        while True:
            try:
                async with asyncio.timeout(1):
                    buffer = await reader.read(want_bytes)
                    if len(buffer) == 0:
                        # Zero bytes returned at EOF; but not a timeout.
                        # That's end-of-stream.
                        break
                    # On a successful read, keep that many bytes
                    want_bytes = 256
                    p2 = Packet(flags=0, stream_id=1, body=buffer)
                    self.send(p2.to_bytes())
            except asyncio.TimeoutError:
                want_bytes = want_bytes // 2
                if want_bytes == 0:
                    want_bytes = 1
        # Input is done, in theory
        p3 = Packet(flags=Flag.END, stream_id=1, body=bytes())
        self.send(p3.to_bytes())
        log.info(f"client {number} closed inbound connection")

    async def run_outbound(self, number: int, writer: StreamWriter):
        olog = log.getChild("outbound")
        total_bytes = 0
        buffer = bytes()
        packet_count = 0
        while True:
            if len(buffer) > 0:
                olog.debug(
                    f"buffer contains bytes: "
                    f"{total_bytes}:{total_bytes+len(buffer)}\n")

            buffer_len = len(buffer)
            (p, buffer) = Packet.from_bytes(buffer)
            consumed = (buffer_len - len(buffer))
            total_bytes += consumed
            if p is None:
                continue
            buffer = rem
            if packet_count == 0:
                assert p.start
            packet_count += 1
            if not p.to_host:
                # Ignore the packet
                continue
            writer.write(p.body)
            await writer.drain()
            if p.end:
                break
        writer.close()
        await writer.wait_closed()
