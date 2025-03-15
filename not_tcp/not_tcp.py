"""
Not TCP is a simple protocol for running HTTP/1.0 sessions over a
serial stream.

Each packet includes a short header: flags, a session ID, and a body-length.

"""

from amaranth import Module, Signal, unsigned, Const
from amaranth.lib.wiring import Component, In, Out, Signature
from amaranth.lib import stream
from amaranth.lib.data import UnionLayout, ArrayLayout, Struct
from amaranth.lib.fifo import SyncFIFOBuffered
import session


class Flags(Struct):
    """
    Flags in a Not TCP header.
    """

    # Start-of-stream marker.
    start: 1

    # End-of-stream marker.
    end: 1

    # Direction marker: 0 for "client to server", 1 for "server to client"
    direction: 1

    # Additional bits for the future.
    unused: 5


class Header(Struct):
    """
    Layout of a Not TCP header.
    """

    flags: Flags

    # Session identifier.
    session: 8

    # Length of the body following the header
    # (bytes to the next header)
    length: 8


class BusStopSignature(Signature):
    """
    Signature of a stop on a Not TCP local bus.

    Attributes
    ----------
    upstream:   Stream(8), In
    downstream: Stream(8), Out
    """

    def __init__(self):
        super().__init__({
            "upstream": In(stream.Signature(8)),
            "downstream": Out(stream.Signature(8)),
        })


class BusRoot(Component):
    """
    Root of a Not TCP bus.
    Connects the (host) serial lines to the (device-local) bus
    and sorts packets between upstrema and downstream.
    """

    bus: Out(BusStopSignature())
    tx: Out(stream.Signature(8))
    rx: In(stream.Signature(8))

    def elaborate(self, platform):
        m = Module()

        return m


class StreamStop(Component):
    """
    A stop for a Not TCP stream on the local bus.

    Attributes
    ----------
    session: Inner interface
    bus: Bus interface
    """

    session: Out(session.BidiSessionSignature().flipped())
    bus: BusStopSignature()

    def elaborate(self, platform):
        m = Module()

        return m
