from dataclasses import dataclass
import struct
from enum import IntFlag
from typing import Optional


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
