from dataclasses import dataclass
import struct
from enum import IntFlag


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
    length: int

    @classmethod
    def length(cls):
        return 3

    def __len__(self):
        return 3

    def to_bytes(self) -> bytes:
        return struct.pack("BBB", self.stream_id, self.length, self.flags)

    def from_bytes(buffer: bytes) -> "Header":
        (stream, length, flags) = struct.unpack("BBB", buffer)
        return Header(
            flags=Flag(flags),
            stream_id=stream,
            length=length,
        )


@dataclass
class Packet:
    """
    Not TCP packet.
    """

    flags: Flag = Flag(0)

    stream_id: int = 0
    body: bytes = bytes()

    @classmethod
    def from_header(cls, header: Header, body: bytes) -> "Packet":
        assert header.length == len(body), f"{header.length} != {len(body)}"
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

        return Header(self.flags, self.stream_id, length=len(self.body))

    def to_bytes(self) -> bytes:
        return self.header().to_bytes() + self.body

    @classmethod
    def from_bytes(cls, buf: bytes) -> ("Packet", bytes):
        header = Header.from_bytes(buf[:Header.length()])
        buf = buf[Header.length():]
        body = buf[:header.length]
        buf = buf[header.length:]
        return (Packet.from_header(header, body), buf)
