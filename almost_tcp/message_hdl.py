"""
Almost TCP data structures: messages and TCB.

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

from amaranth import Module, Signal, unsigned
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib import data, stream


class FlagsLayout(data.Struct):
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


class HeaderLayout(data.Struct):
    """
    Layout of a full ATCP header.

    TODO: Fix byte order!
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


class PacketReader(Component):
    """
    Reads an AlmostTCP packet into a buffer.

    Attributes
    -----------
    input:  Stream(8), in
            Input stream.

    header:         Header, out
                    The header curently read in to the buffer.
    stream_valid:   Out(1)
                    High if the "stream" value from the header is valid.
    header_valid:   Out(1)
                    High if the whole header is valid.

    data:           Stream(8), out
                    Output stream for the body of the packet.
                    The PacketReader is automatically reset when the
                    body is read from the data stream.
    """

    input: In(stream.Signature(8))
    header: Out(HeaderLayout)
    stream_valid: Out(1)
    header_valid: Out(1)
    data: Out(stream.Signature(8))

    def elaborate(self, platform):
        m = Module()

        # Our state machine: what byte do we read in to next?
        byte = Signal(4)
        m.d.comb += [
            # Stream is valid once we've read byte[1]
            self.stream_valid.eq(byte > 1),
            # Whole header is valid once we've read byte[9]
            self.header_valid.eq(byte > 9),
            self.data.valid.eq(0),
            self.data.payload.eq(self.input.payload),
        ]
        remaining_len = Signal(16)

        # TODO: ...byte order, little/big endian?
        mixed_view = data.UnionLayout(
            {
                "bytes": data.ArrayLayout(unsigned(8), 10),
                "header": HeaderLayout
            })
        pun = mixed_view(self.header)

        # State machine is encoded in the byte marker.
        with m.If(~self.header_valid):
            m.d.comb += self.input.ready.eq(1)
            with m.If(self.input.valid):
                m.d.sync += [
                    byte.eq(byte + 1),
                    pun.bytes[byte].eq(self.input.payload),
                ]
                with m.If(byte == 4):
                    m.d.sync += remaining_len.eq(pun.header.length)
        with m.Else():
            # TODO: Only report "ready" for as many bytes as there
            # are in the input.
            m.d.comb += [
                self.data.valid.eq(self.input.valid),
                self.input.ready.eq(self.data.ready),
            ]
            with m.If(self.input.valid & self.data.ready):
                m.d.sync += remaining_len.eq(remaining_len - 1)
                with m.If(remaining_len == 1):
                    m.d.sync += byte.eq(0)

        return m
