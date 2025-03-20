from dataclasses import dataclass
import struct
from typing import Optional


@dataclass
class Header:
    """
    Not TCP header.
    """

    start: bool
    end: bool
    to_host: bool

    stream: int
    length: int

    @classmethod
    def length(cls):
        return 3

    def __len__(self):
        return 3

    def to_bytes(self) -> bytes:
        flags = 0
        flags += 1 if self.start else 0
        flags += 2 if self.end else 0
        flags += 4 if self.to_host else 0
        return struct.pack("BBB", self.stream, self.length, flags)

    def from_bytes(buffer: bytes) -> "Header":
        (stream, length, flags) = struct.unpack("BBB", buffer)
        return Header(
            start=bool(flags & 1),
            end=bool(flags & 2),
            to_host=bool(flags & 4),
            stream=stream,
            length=length,
        )


@dataclass
class Packet:
    """
    Not TCP packet.
    """

    start: bool = False
    end: bool = False
    to_host: bool = False

    stream: int = 0
    body: bytes = bytes()

    @classmethod
    def from_header(cls, header: Header, body: bytes) -> "Packet":
        assert header.length == len(body), f"{header.length} != {len(body)}"
        return Packet(
            start=header.start,
            end=header.end,
            to_host=header.to_host,
            stream=header.stream,
            body=body
        )

    def __len__(self):
        return len(Header) + len(self.body)

    def header(self) -> Header:
        assert self.stream >= 0
        assert self.stream < 256

        return Header(self.start, self.end, self.to_host, self.stream,
                      length=len(self.body))

    def to_bytes(self) -> bytes:
        return self.header().to_bytes() + self.body

    @classmethod
    def from_bytes(cls, buf: bytes) -> ("Packet", bytes):
        header = Header.from_bytes(buf[:Header.length()])
        buf = buf[Header.length():]
        body = buf[:header.length]
        buf = buf[header.length:]
        return (Packet.from_header(header, body), buf)
