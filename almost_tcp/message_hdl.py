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

from amaranth.lib import data


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

    def length(self) -> int:
        """
        Return the length of the header in bytes (octets).
        """
        self.width / 8
