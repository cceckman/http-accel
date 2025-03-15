from dataclasses import dataclass
import struct


@dataclass
class Header:
    """
    Not TCP header.
    """

    start: bool
    end: bool
    to_host: bool

    session: int
    length: int

    def __len__(cls):
        return 3

    def to_bytes(self) -> bytes:
        flags = 0
        flags += 1 if self.start else 0
        flags += 2 if self.end else 0
        flags += 4 if self.to_host else 0
        return struct.pack("BBB", flags, self.session, self.length)

    def from_bytes(buffer: bytes) -> "Header":
        (flags, session, length) = struct.unpack("BBB", buffer)
        return Header(
            start=bool(flags & 1),
            end=bool(flags & 2),
            to_host=bool(flags & 4),
            session=session,
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

    session: int = 0
    body: bytes = bytes()

    def __len__(self):
        return len(Header) + len(self.body)

    def header(self) -> Header:
        assert self.session >= 0
        assert self.session < 256

        return Header(self.start, self.end, self.to_host, self.session,
                      length=len(self.body))

    def to_bytes(self) -> bytes:
        return self.header.to_bytes() + self.body
