"""
Almost TCP data structures: messages and packet decoder.

Almost TCP is a protocol designed to tunnel data streams
(specifically, HTTP requests) over a serial port.
It consists of a subset of TCP's functionality,
including reduced sizes for some fields,
with the goal of enabling a small hardware implementation.

Each ATCP message consists of a fixed-length header
followed by variable-length data.

All numeric fields are network-endian (big-endian).

-   Connection-oriented: syn/synack/ack setup
-   Single stream number, not two port numbers
    -   Stream number probing to determine # of hardware resources available

"""

from amaranth import Module, Signal, unsigned, Const
from amaranth.lib.wiring import Component, In, Out, Signature
from amaranth.lib import stream
from amaranth.lib.data import UnionLayout, ArrayLayout, Struct
from amaranth.lib.fifo import SyncFIFOBuffered


class FlagsLayout(Struct):
    """
    Layout of the flags in an ATCP header.
    """

    # Indicates the sender has sent all the data it will send on this stream.
    fin: 1
    # Indicates a desire to open a new stream,
    # starting at 1 more than the provided sequence number.
    syn: 1
    # Indicates the provided stream should be immediately reset.
    rst: 1
    # Unused: push data to the receiver.
    psh: 1
    # The acknowledgement number is significant.
    ack: 1
    # Unused: urgent
    urg: 1
    # Unused: explicit congestion notification
    ecn: 1
    # Unused: congestion window reduced
    cwr: 1


class HeaderLayout(Struct):
    """
    Layout of a full ATCP header.
    """

    flags: FlagsLayout
    # Stream: identity of the stream this message is intended for.
    stream: 8

    # Length of the data that follows the header.
    length: 16

    # Amount of additional data (after the acknowledged data)
    # the sender can accept before buffering.
    window: 16

    # Sequence number: number in this stream of the
    # first octet in the data section.
    # The "syn" message is considered to occupy the first octet of the stream.
    seq: 16
    # Acknowledgement number: the next number the sender of this ACK expects.
    ack: 16


class PacketSignature(Signature):
    """
    Signature of a packet producer.

    Attributes
    ----------
    header:         Header, out
                    The header curently read in to the buffer.
    stream_valid:   Out(1)
                    High if the "stream" value from the header is valid.
    header_valid:   Out(1)
                    High if the whole header is valid and for this stream.

    data:           Stream(8), out
                    Output stream for the body of the packet.
                    The valid bits automatically deassert after the body
                    has been fully read from the data stream.
    """

    def __init__(self):
        super().__init__({
            "header": Out(HeaderLayout),
            "stream_valid": Out(1),
            "header_valid": Out(1),
            "data": Out(stream.Signature(8)),
        })


class ReadPacketStop(Component):
    """
    Stop on a packet-reading bus.

    Each stream should have a stop on the same bus,
    chained by their "inbus" and "outbus" connections.
    When a stop spots a packet for its stream,
    it tees off the input into its own PacketSignature output.

    All stops get all bytes, even those not destined for this stop.

    Parameters
    ----------
    id: int
        Stream ID for this stop.

    Attributes
    -----------
    inbus: Out(Stream(8))
        Input from the bus.
    outbus: In(Stream(8))
        Output to the next stop on the bus.
    packet:   Out(PacketSignature)
        The currently-buffered packet.
    """

    inbus: In(stream.Signature(8))
    outbus: Out(stream.Signature(8))
    packet: Out(PacketSignature())

    def __init__(self, id: int):
        super().__init__()
        self._stream_id = id

    def elaborate(self, platform):
        m = Module()

        # Our header may be locally valid but not a match for the stream.
        local_header_valid = Signal(1)
        local_stream_valid = Signal(1)
        header_valid_and_matched = self.packet.header_valid
        stream_valid_and_matched = self.packet.stream_valid
        data = self.packet.data
        stream_match = Signal(1)

        # Add a FIFO in the hope of avoiding long combinational paths.
        # According to the simulator, this needs to be at least 3 deep to avoid
        # backpressure into the input.
        m.submodules.outbus = outbus = SyncFIFOBuffered(width=8, depth=4)
        m.d.comb += [
            self.outbus.payload.eq(outbus.r_data),
            self.outbus.valid.eq(outbus.r_rdy),
            outbus.r_en.eq(self.outbus.ready),
        ]
        # We don't do the same on the "local data" side;
        # we assume the reader of the body will have its own
        # (connection-level) buffer.

        # Our state machine: what byte do we read in to next?
        byte_counter = Signal(4)
        m.d.comb += [
            # Stream is valid once we've read byte[1]
            local_stream_valid.eq(byte_counter > 1),
            stream_match.eq(
                self.packet.header.stream == Const(self._stream_id)
            ),
            # Whole header is valid once we've read byte[9]
            local_header_valid.eq(byte_counter > 9),
            header_valid_and_matched.eq(stream_match & local_header_valid),
            stream_valid_and_matched.eq(stream_match & local_stream_valid),
            # We always tee data to both outputs:
            data.payload.eq(self.inbus.payload),
            outbus.w_data.eq(self.inbus.payload),
            # But by default, produce no transfers.
            self.inbus.ready.eq(0),
            data.valid.eq(0),
            outbus.w_en.eq(0),
        ]
        remaining_len = Signal(16)

        mixed_view = UnionLayout(
            {
                "bytes": ArrayLayout(unsigned(8), 10),
                "header": HeaderLayout
            })
        network = Signal(HeaderLayout)
        pun = mixed_view(network)

        # We combinatorially convert between the network order
        # and little-endian.
        m.d.comb += [
            self.packet.header.flags.eq(network.flags),
            self.packet.header.stream.eq(network.stream),
            self.packet.header.length[0:8].eq(network.length[8:16]),
            self.packet.header.length[8:16].eq(network.length[0:8]),
            self.packet.header.window[0:8].eq(network.window[8:16]),
            self.packet.header.window[8:16].eq(network.window[0:8]),
            self.packet.header.seq[0:8].eq(network.seq[8:16]),
            self.packet.header.seq[8:16].eq(network.seq[0:8]),
            self.packet.header.ack[0:8].eq(network.ack[8:16]),
            self.packet.header.ack[8:16].eq(network.ack[0:8]),
        ]

        # We may have to wait for the next stop on the bus, or our local stop,
        # before we take from the input.
        # In either case, every byte from the inbus goes to the outbus.
        can_transfer = Signal(1)
        m.d.comb += [
            outbus.w_en.eq(can_transfer),
            self.inbus.ready.eq(can_transfer),
        ]
        # State machine is encoded in byte count & stream match.
        with m.If(~local_header_valid):
            # Read in a byte to the header,
            # not to local data.
            m.d.comb += [
                can_transfer.eq(self.inbus.valid & outbus.w_rdy),
                data.valid.eq(0),
            ]
            with m.If(can_transfer):
                # Byte transferred at the end of this cycle.
                m.d.sync += [
                    byte_counter.eq(byte_counter + 1),
                    pun.bytes[byte_counter].eq(self.inbus.payload),
                ]
                with m.If(byte_counter == 4):
                    # Capture the length.
                    m.d.sync += remaining_len.eq(self.packet.header.length)
        with m.Else():
            # Forward bytes around the bus,
            # and optionally to the local channel too.
            m.d.comb += [
                can_transfer.eq(self.inbus.valid &
                                outbus.w_rdy & (data.ready | ~stream_match)),
                data.valid.eq(can_transfer & stream_match),
            ]

            with m.If(can_transfer):
                m.d.sync += remaining_len.eq(remaining_len - 1)
                with m.If(remaining_len == 1):
                    m.d.sync += byte_counter.eq(0)

        return m
