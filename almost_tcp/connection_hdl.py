"""
Almost TCP block for a single connection.
"""

from amaranth import Module, Const, Signal
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib import stream, fifo
from .session import Signature
from message_hdl import PacketSignature


class Connection(Component):
    """
    An Almost TCP connection.
    Converts between a packetized data stream (to/from the host)
    and a plain bytestream  (on the hardware).

    Parameters
    ----------
    id: :py:`int`
        Session ID.
    bufsz: :py:`int`
        Buffer size, for input and output buffers.

    Attributes
    ----------
    session: :py:`session.Signature(stream.Signature(8))`
        Inner interface, to the hardware.
        Input and output data streams.

    packet_in: `:py:`In(message_hdl.PacketSignature)`
        Packet receipt interface.
    packet_out: `:py:`Out(message_hdl.PacketSignature)`
        Packet sending interface.

    """

    session: Out(Signature(stream.Signature(8)))
    packet_in: In(PacketSignature())
    packet_out: Out(PacketSignature())

    def __init__(self, id: int, bufsz: int):
        super().__init__()
        self._id = id
        self._bufsz = bufsz

    def elaborate(self, platform):
        m = Module()

        # TODO: Engage with session.
        # "Await accept" timer before RST?

        # TODO:
        # - Declare an inner clock domain; the builtin FIFOs don't have a
        #   separate reset.
        # - Figure out how to receive packets
        # - Figure out how to send packets

        packet_in_ready = Signal(1)
        m.d.comb += packet_in_ready.eq(
            self.packet_in.header_valid &
            self.packet_in.header.stream == Const(self._id)
        )

        m.submodules.input_buffer = input_buffer = fifo.SyncFifoBuffered(
            8, self._bufsz)
        m.d.comb += [
            self.session.input.payload.eq(input_buffer.r_data),
            self.session.input.valid.eq(input_buffer.r_rdy),
            input_buffer.r_en.eq(self.session.input.ready),
        ]
        m.submodules.output_buffer = fifo.SyncFifoBuffered(8, self._bufsz)
        m.d.comb += [
            self.session.input.payload.eq(input_buffer.r_data),
            self.session.input.valid.eq(input_buffer.r_rdy),
            input_buffer.r_en.eq(input_buffer.r_en),
        ]

        # TODO: Get sizes from HeaderLayout -- length parameter
        input_count = Signal(16)
        m.d.comb += [input_buffer.w_data.eq(self.packet_in.data.payload)]

        # Read side
        with m.FSM(name="reader"):
            with m.State("closed"):
                m.next = "closed"
                # TODO: Transmit first:

                # Then read:
                with m.If(packet_in_ready):
                    m.d.sync += input_count.eq(self.packet_in.header.length)
                    with m.If(input_buffer.w_rdy):
                        m.next = "reading"
                    with m.Else():
                        m.next = "skipping"
            with m.State("reading"):
                m.next = "reading"
                with m.If(input_count > 0):
                    with m.If(input_buffer.w_rdy):
                        # Read a byte.
                        m.d.comb += input_buffer.w_en.eq(1)
                        m.d.sync += input_count.eq(input_count - 1)
                    with m.Else():
                        m.next = "skipping"
                with m.Else():
                    m.next = "closed"

            with m.State("skipping"):
                m.next = "skipping"
                m.d.comb += self.packet_in.data.ready.eq(1)
                # If the FIFO filled up, drain the input packet
                # but don't write to the FIFO.
                with m.If(input_count > 0):
                    with m.If(self.packet_in.data.valid):
                        m.d.sync += input_count.eq(input_count - 1)
                with m.Else():
                    m.next = "closed"

        return m
