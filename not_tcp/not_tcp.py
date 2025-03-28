"""
Not TCP is a simple protocol for running HTTP/1.0 sessions over a
serial stream.

Each packet includes a short header: flags, a session ID, and a body-length.

"""

from amaranth import Module, Signal, unsigned, Const
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

        # Each of these is big enough to buffer one full packet.
        input_buffer = m.submodules.input_buffer = SyncFIFOBuffered(
            width=8, depth=256)
        output_buffer = m.submodules.output_buffer = SyncFIFOBuffered(
            width=8, depth=256)

        connect(m, self.stop.outbound.data, output_buffer.w_stream)
        connect(m, input_buffer.r_stream, self.stop.inbound.data)
        input_limiter = m.submodules.input_limiter = LimitForwarder(
            width=8, max_count=256)
        output_limiter = m.submodules.output_limiter = LimitForwarder(
            width=8, max_count=256)

        # Default state: don't transfer any data.
        m.d.comb += [
            self.stop.inbound.active.eq(0),
            input_limiter.start.eq(0),
            output_limiter.start.eq(0),
        ]
        connect(m, input_limiter.outbound, input_buffer.w_stream)
        connect(m, output_buffer.r_stream, output_limiter.inbound)

        flags_layout = UnionLayout({"bytes": unsigned(8), "flags": Flags})

        # Header from inbound packet:
        read_len = Signal(8)
        read_flags = Signal(flags_layout)
        stream = Signal(8)

        # Flags for outbound packet:
        send_flags = Signal(flags_layout)
        m.d.comb += send_flags.flags.to_host.eq(1)
        sent_start = Signal(1)
        sent_end = Signal(1)

        # Connection-state handling:
        m.d.comb += [self.stop.inbound.active.eq(0),
                     self.connected.eq(0)]
        with m.FSM(name="connection"):
            with m.State("closed"):
                m.next = "closed"
                with m.If(
                        read_flags.flags.start &
                        (stream == Const(self._stream_id))):
                    m.d.sync += sent_start.eq(0)
                    m.d.sync += sent_end.eq(0)
                    m.next = "requested"
            with m.State("requested"):
                m.next = "requested"
                m.d.comb += [self.stop.inbound.active.eq(1)]
                with m.If(self.stop.outbound.active):
                    m.next = "open"
            with m.State("open"):
                m.next = "open"
                m.d.comb += [
                    self.stop.inbound.active.eq(1),
                    self.connected.eq(1),
                ]
                with m.If(sent_end):
                    m.next = "server-done"
                with m.Elif(
                        read_flags.flags.end &
                        (stream == Const(self._stream_id))):
                    # Client has marked end-of-stream.
                    # Consume the input buffer.
                    m.next = "client-done"
            with m.State("client-done"):
                m.next = "client-done"
                m.d.comb += [self.connected.eq(1)]
                with m.If(sent_end):
                    # Server is also done, and flushed.
                    m.next = "flush"
            with m.State("server-done"):
                m.next = "server-done"
                m.d.comb += [self.connected.eq(1),
                             self.stop.inbound.active.eq(1)]
                with m.If(
                    ~read_flags.flags.end &
                        (stream == Const(self._stream_id))):
                    m.next = "flush"
            with m.State("flush"):
                m.next = "flush"
                m.d.comb += [self.connected.eq(1)]
                with m.If(
                    (read_len == Const(0)) &
                    (input_buffer.r_level == Const(0)) &
                    (output_buffer.r_level == Const(0))
                ):
                    # All data processing done.
                    m.next = "closed"
        # END of connection-state FSM

        with m.FSM(name="read"):
            bus = self.bus.upstream
            with m.State("read-stream"):
                m.next = "read-stream"
                m.d.comb += bus.ready.eq(1)
                with m.If(bus.valid):
                    m.d.sync += stream.eq(bus.payload)
                    # Zero the flags, so we don't get a false start/end
                    m.d.sync += read_flags.eq(0)
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
                    # At the cycle edge, capture the flags byte...
                    m.d.sync += read_flags.bytes.eq(bus.payload)
                    with m.If(stream == Const(self._stream_id)):
                        # maybe block until accepted.
                        # TODO: This introduces an extra cycle of delay
                        # when we're "already connected",
                        # but keeps the logic blocks simpler.
                        m.next = "await-accept"
                    with m.Else():
                        # If this isn't for our stream, proceed to read
                        # (and discard)
                        m.d.comb += input_limiter.count.eq(read_len)
                        m.d.comb += input_limiter.start.eq(1)
                        m.next = "read-body"
            with m.State("await-accept"):
                m.next = "await-accept"
                with m.If(self.connected):
                    # trigger the input-limiter to begin starting with
                    # the byte following that.
                    m.d.comb += input_limiter.count.eq(read_len)
                    m.d.comb += input_limiter.start.eq(1)
                    m.next = "read-body"
            with m.State("read-body"):
                m.next = "read-body"
                connect(m, self.bus.upstream, input_limiter.inbound)
                with m.If(stream != Const(self._stream_id)):
                    # Disconnect from the input buffer, just discard the data:
                    m.d.comb += [
                        input_buffer.w_stream.valid.eq(0),
                        input_limiter.outbound.ready.eq(1),
                    ]
                m.d.comb += input_limiter.start.eq(0)
                with m.If(input_limiter.done):
                    # Clear the input from the last packet, so we don't
                    # think that we have one pending until we read it again.
                    m.d.sync += [read_len.eq(0), stream.eq(self._stream_id+1)]
                    m.next = "read-stream"

        # Cases in which we want to send a packet:
        data_to_send = output_buffer.r_level > 0
        not_yet_started = self.connected & ~sent_start
        not_yet_ended = (self.connected &
                         ~self.stop.outbound.active & ~sent_end)
        with m.FSM(name="write"):
            bus = self.bus.downstream
            write_len = Signal(8)

            with m.State("write-stream"):
                m.next = "write-stream"

                with m.If(data_to_send | not_yet_started | not_yet_ended):
                    # We're ready to start sending...
                    m.d.comb += bus.payload.eq(self._stream_id)
                    m.d.comb += bus.valid.eq(1)
                    # Lock in the level as the length of this packet.
                    # We may send a short (zero-length) packet
                    # to start or end the connection.
                    m.d.sync += write_len.eq(output_buffer.r_level)
                    with m.If(bus.ready):
                        # Only transition if we are ready-to-send.
                        m.next = "write-len"
                with m.Else():
                    m.d.comb += bus.valid.eq(0)
            with m.State("write-len"):
                m.next = "write-len"
                # Write the length.
                m.d.comb += bus.payload.eq(write_len)
                m.d.comb += bus.valid.eq(1)
                with m.If(bus.ready):
                    m.next = "write-flags"
            with m.State("write-flags"):
                m.next = "write-flags"
                # Send the "end" bit if:
                # - we haven't yet sent one,
                # - the server has closed the connection, and
                # - we have sent all the data from the server
                # This generates an extra empty "end" packet-
                # noisy, but correct.
                send_end = not_yet_ended & (output_buffer.r_level == 0)

                m.d.comb += [
                    send_flags.flags.start.eq(~sent_start),
                    send_flags.flags.end.eq(send_end),
                    bus.payload.eq(send_flags.bytes),
                    bus.valid.eq(1),
                ]
                m.d.comb += [
                    output_limiter.count.eq(write_len),
                    output_limiter.start.eq(1),
                ]
                with m.If(bus.ready):
                    m.d.sync += [
                        sent_start.eq(1),
                        sent_end.eq(send_end),
                    ]
                    m.next = "write-body"
            with m.State("write-body"):
                m.next = "write-body"
                connect(m, output_limiter.outbound, bus)
                with m.If(output_limiter.done):
                    m.next = "write-stream"
        return m
