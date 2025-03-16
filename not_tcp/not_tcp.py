"""
Not TCP is a simple protocol for running HTTP/1.0 sessions over a
serial stream.

Each packet includes a short header: flags, a session ID, and a body-length.

"""

from amaranth import Module, Signal, unsigned, Const
from amaranth.lib.wiring import Component, In, Out, Signature, connect
from amaranth.lib import stream
from amaranth.lib.data import UnionLayout, ArrayLayout, Struct
from amaranth.lib.fifo import SyncFIFOBuffered

import session
from http_server.stream_mux import StreamMux
from http_server.stream_demux import StreamDemux


class Flags(Struct):
    """
    Flags in a Not TCP header.
    """

    # Start-of-stream marker.
    start: 1

    # End-of-stream marker.
    end: 1

    # Direction marker: 0 for "client to server", 1 for "server to client"
    to_host: 1

    # Additional bits for the future.
    unused: 5


class Header(Struct):
    """
    Layout of a Not TCP header.
    """

    # Stream identifier.
    stream: 8

    # Length of the body following the header
    # (# of bytes to the next header)
    length: 8

    # Session-state indicators
    flags: Flags


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

    NOTE: the Not TCP bus currently uses broadcast sends; it is not a ring bus.

    Parameters
    ----------
    stream_id: stream ID to match / generate packets with

    Attributes
    ----------
    session: Inner interface
    bus: Bus interface
    """

    stop: Out(session.BidiSessionSignature().flip())
    bus: Out(BusStopSignature())

    def __init__(self, stream_id):
        super().__init__()
        self._stream_id = stream_id

    def elaborate(self, platform):
        m = Module()

        bus_buffer = m.submodules.bus_buffer = SyncFIFOBuffered(
            width=8, depth=4)
        # Each of these is big enough to buffer one full packet.
        input_buffer = m.submodules.input_buffer = SyncFIFOBuffered(
            width=8, depth=256)
        output_buffer = m.submodules.output_buffer = SyncFIFOBuffered(
            witdh=8, depth=256)

        connect(m, bus_buffer.r_stream, self.bus.downstream)
        connect(m, self.session.outbound.data, output_buffer.w_stream)
        connect(m, input_buffer.r_stream, self.session.inbound.data)

        # TODO: Muxes for inbound connections?
        # Or connect as part of the state machines?

        # Default state: don't transfer any data.
        m.d.comb += [
            self.session.inbound.active.eq(0),
            self.bus_buffer.w_stream.valid.eq(0),
            self.input_buffer.r_stream.ready.eq(0),
            self.output_buffer.r_stream.ready.eq(0),
        ]


        ## INBOUND DATA HANDLING
        mixed_view = UnionLayout(
            {
                "bytes": ArrayLayout(unsigned(8), 10),
                "header": Header,
            })
        network = Signal(Header)
        pun = mixed_view(network)

        return m
