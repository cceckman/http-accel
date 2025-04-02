"""
Not TCP is a simple protocol for running HTTP/1.0 sessions over a
serial stream.

Each packet includes a short header: flags, a session ID, and a body-length.

"""

from amaranth import Module, Signal, unsigned, Const, Assert
from amaranth.lib.wiring import Component, In, Out, Signature, connect
from amaranth.lib import stream
from amaranth.lib.data import UnionLayout, Struct
from amaranth.lib.fifo import SyncFIFOBuffered

import session
from stream_utils import LimitForwarder


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
    and sorts packets between upstream and downstream.
    """

    bus: Out(BusStopSignature())
    tx: Out(stream.Signature(8))
    rx: In(stream.Signature(8))

    def elaborate(self, platform):
        m = Module()

        # Degenerate implementation for a single stop with no arbitration,
        # or with all stops forwarding unmatched packets.
        connect(m, self.rx, self.bus.upstream)
        connect(m, self.bus.downstream, self.tx)

        return m


class InboundStop(Component):
    """
    Inbound half of an nTCP stop.

    Parameters
    ---------
    stream_id


    Attributes:
    ----------
    stop: inbound session interface
    accepted: "active" from the outbound direction
    connected: indicator that the session has connected in at least one direction
    upstream: inbound bus interface
    """

    stop: Out(session.SessionSignature())
    accepted: In(1)
    connected: Out(1)
    bus: In(stream.Signature(8))

    def __init__(self, stream_id):
        super().__init__()
        self._stream_id = Const(stream_id)

    def elaborate(self, platform):
        m = Module()
        connected = self.connected
        input_buffer = m.submodules.input_buffer = SyncFIFOBuffered(
            width=8, depth=256)
        m.d.comb += [
            self.stop.data.payload.eq(input_buffer.r_stream.payload),
            self.stop.data.valid.eq(input_buffer.r_stream.valid),
            input_buffer.r_stream.ready.eq(self.stop.data.ready),
        ]

        input_limiter = m.submodules.input_limiter = LimitForwarder(
            width=8, max_count=256)

        # Default state: don't transfer any data.
        m.d.comb += [
            input_limiter.start.eq(0),
        ]
        connect(m, input_limiter.outbound, input_buffer.w_stream)

        flags_layout = UnionLayout({"bytes": unsigned(8), "flags": Flags})
        # Header from inbound packet:
        read_len = Signal(8)
        read_flags = Signal(flags_layout)
        read_stream = Signal(8)

        this_stop = read_stream == self._stream_id

        with m.FSM(name="read"):
            bus = self.bus
            with m.State("read-stream"):
                m.next = "read-stream"
                m.d.comb += bus.ready.eq(1)
                m.d.sync += read_flags.eq(0)
                m.d.sync += read_len.eq(0)
                with m.If(bus.valid):
                    m.d.sync += read_stream.eq(bus.payload)
                    m.next = "read-len"
            with m.State("read-len"):
                m.next = "read-len"
                m.d.comb += bus.ready.eq(1)
                with m.If(bus.valid):
                    m.d.sync += read_len.eq(bus.payload)
                    m.next = "read-flags"
            with m.State("read-flags"):
                m.next = "read-flags"
                m.d.comb += bus.ready.eq(1)
                with m.If(bus.valid):
                    m.d.sync += read_flags.bytes.eq(bus.payload)
                    is_start = flags_layout(bus.payload).flags.start

                    # If the packet is for this channel
                    # and we're already connected or it's a start panic,
                    # handle it in the local path
                    with m.If(this_stop & (connected | is_start)):
                        with m.If(is_start):
                            m.d.sync += self.stop.active.eq(1)
                            m.next = "await-accept"
                        with m.Else():
                            m.d.comb += input_limiter.count.eq(read_len)
                            m.d.comb += input_limiter.start.eq(1)
                            m.next = "read-body"
                    # Otherwise, ignore the packet.
                    with m.Else():
                        # TODO: Forward data to downstream stop if stream
                        # doesn't match.
                        # For now: if this isn't for our stream,
                        # proceed to read (and discard)
                        m.d.comb += input_limiter.count.eq(read_len)
                        m.d.comb += input_limiter.start.eq(1)
                        m.next = "read-body"
            with m.State("await-accept"):
                m.next = "await-accept"
                # Flags handling. We only do this if we've matched the stop ID.
                m.d.comb += Assert(this_stop)
                m.d.comb += Assert(read_flags.flags.start)

                with m.If(self.accepted):
                    m.d.sync += connected.eq(1)
                    m.d.comb += input_limiter.count.eq(read_len)
                    m.d.comb += input_limiter.start.eq(1)
                    m.next = "read-body"

            with m.State("read-body"):
                m.next = "read-body"
                m.d.comb += [
                    input_limiter.inbound.payload.eq(self.bus.payload),
                    input_limiter.inbound.valid.eq(self.bus.valid),
                    self.bus.ready.eq(input_limiter.inbound.ready),
                ]
                with m.If(read_stream != self._stream_id):
                    # Disconnect from the input buffer, just discard the data:
                    m.d.comb += [
                        input_buffer.w_stream.valid.eq(0),
                        input_limiter.outbound.ready.eq(1),
                    ]
                m.d.comb += input_limiter.start.eq(0)
                with m.If(input_limiter.done):
                    m.next = "read-stream"
                    m.d.sync += [read_len.eq(0), read_stream.eq(0)]
                    with m.If(read_flags.flags.end):
                        m.d.sync += [
                            self.stop.active.eq(0),
                            connected.eq(0)
                        ]

        return m


class OutboundStop(Component):
    stop: In(session.SessionSignature())
    bus: Out(stream.Signature(8))
    connected: Out(1)

    def __init__(self, stream_id):
        super().__init__()
        self._stream_id = Const(stream_id)

    def elaborate(self, platform):
        m = Module()

        # Each of these is big enough to buffer one full packet.
        output_buffer = m.submodules.output_buffer = SyncFIFOBuffered(
            width=8, depth=256)

        m.d.comb += [
            output_buffer.w_stream.payload.eq(self.stop.data.payload),
            output_buffer.w_stream.valid.eq(self.stop.data.valid),
            self.stop.data.ready.eq(output_buffer.w_stream.ready),
        ]

        output_limiter = m.submodules.output_limiter = LimitForwarder(
            width=8, max_count=256)

        # Default state: don't transfer any data.
        m.d.comb += [
            output_limiter.start.eq(0),
            self.bus.valid.eq(0)
        ]
        connect(m, output_buffer.r_stream, output_limiter.inbound)

        flags_layout = UnionLayout({"bytes": unsigned(8), "flags": Flags})

        # Flags for outbound packet:
        send_flags = Signal(flags_layout)
        m.d.sync += send_flags.flags.to_host.eq(1)
        send_len = Signal(8)

        # Cases in which we want to send a packet:
        with m.FSM(name="write"):
            with m.State("disconnected"):
                m.next = "disconnected"
                with m.If(self.stop.active):
                    # Immediately send a "start" packet.
                    m.d.sync += send_flags.flags.start.eq(1)
                    m.d.sync += send_flags.flags.end.eq(0)
                    m.d.sync += self.connected.eq(1)
                    m.next = "write-stream"

            with m.State("write-stream"):
                m.next = "write-stream"

                with m.If(
                        send_flags.flags.start
                        | ~self.stop.active
                        | output_buffer.level > 0):
                    # Start sending.
                    m.d.comb += self.bus.payload.eq(self._stream_id)
                    m.d.comb += self.bus.valid.eq(1)
                    # Lock in the level as the length of this packet.
                    # We may send a short (zero-length) packet
                    # to start or end the connection.
                    m.d.sync += send_len.eq(output_buffer.r_level)
                    # We send an explicit empty END packet.
                    m.d.sync += send_flags.flags.end.eq(
                        ~self.stop.active &
                        (output_buffer.r_level == Const(0)))
                    with m.If(self.bus.ready):
                        m.next = "write-len"
            with m.State("write-len"):
                m.next = "write-len"
                m.d.comb += self.bus.payload.eq(send_len)
                m.d.comb += self.bus.valid.eq(1)
                with m.If(self.bus.ready):
                    m.next = "write-flags"
            with m.State("write-flags"):
                m.next = "write-flags"
                m.d.comb += [
                    self.bus.payload.eq(send_flags.bytes),
                    self.bus.valid.eq(1),
                ]
                with m.If(self.bus.ready):
                    m.d.comb += [
                        output_limiter.count.eq(send_len),
                        output_limiter.start.eq(1),
                    ]
                    m.next = "write-body"
            with m.State("write-body"):
                m.next = "write-body"
                m.d.comb += [
                    self.bus.payload.eq(output_limiter.outbound.payload),
                    self.bus.valid.eq(output_limiter.outbound.valid),
                    output_limiter.outbound.ready.eq(self.bus.ready),
                ]

                with m.If(output_limiter.done):
                    m.d.sync += [
                        send_flags.flags.start.eq(0),
                        send_flags.flags.end.eq(0),
                    ]
                    with m.If(send_flags.flags.end):
                        m.d.sync += self.connected.eq(0)
                        m.next = "disconnected"
                    with m.Else():
                        m.next = "write-stream"

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
    stop: Inner interface
    bus: Bus interface

    connected:  Debug/test interface indicating connection status.
                Testonly, for now.
    """

    stop: Out(session.BidiSessionSignature())
    bus: In(BusStopSignature())
    connected: Out(1)

    def __init__(self, stream_id):
        super().__init__()
        self._stream_id = stream_id

    def elaborate(self, platform):
        m = Module()

        inbound_inner = m.submodules.inbound = InboundStop(self._stream_id)
        inbound_outer = self.stop.inbound
        outbound_inner = m.submodules.outbound = OutboundStop(self._stream_id)
        outbound_outer = self.stop.outbound

        m.d.comb += [
            self.connected.eq(
                inbound_inner.connected | outbound_inner.connected
            ),

            inbound_outer.active.eq(inbound_inner.stop.active),
            inbound_outer.data.payload.eq(inbound_inner.stop.data.payload),
            inbound_outer.data.valid.eq(inbound_inner.stop.data.valid),
            inbound_inner.stop.data.ready.eq(inbound_outer.data.ready),

            outbound_inner.stop.active.eq(outbound_outer.active),
            outbound_inner.stop.data.payload.eq(
                outbound_outer.data.payload),
            outbound_inner.stop.data.valid.eq(outbound_outer.data.valid),
            outbound_outer.data.ready.eq(outbound_inner.stop.data.ready),

            inbound_inner.accepted.eq(outbound_inner.stop.active),

            inbound_inner.bus.payload.eq(self.bus.upstream.payload),
            inbound_inner.bus.valid.eq(self.bus.upstream.valid),
            self.bus.upstream.ready.eq(inbound_inner.bus.ready),

            self.bus.downstream.payload.eq(outbound_inner.bus.payload),
            self.bus.downstream.valid.eq(outbound_inner.bus.valid),
            outbound_inner.bus.ready.eq(self.bus.downstream.ready),
        ]

        return m
