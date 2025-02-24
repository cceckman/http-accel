"""
Host-side implementation of the Almost TCP protocol.
"""

from dataclasses import dataclass
import itertools
import struct


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


class AlreadyFinishedError(Exception):
    """
    When the client attempts an operation after finishing the connection.
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
    FORMAT = "!BHHHH"

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
            Header.FORMAT,
            self.stream, self.length, self.window, self.seq, self.ack)

    def decode(buffer):
        if len(buffer) < Header.BYTES:
            raise NotEnoughDataError(
                f"not enough bytes for header: {len(buffer)} < 10")
        flags = Flags.decode(buffer)
        (stream, length, window, seq, ack) = struct.unpack(
            Header.FORMAT, buffer[1:])
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
