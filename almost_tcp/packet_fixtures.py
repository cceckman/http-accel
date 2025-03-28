"""
Test fixtures for sending and receiving packets and streams.
"""
import random
from almost_tcp.message_host import Packet, Header, Flags
from typing import List
from functools import reduce
from hypothesis import strategies as st
from stream_fixtures import StreamCollector, StreamSender


__all__ = ["arbitrary_packet", "StreamCollector",
           "PacketCollector", "PacketSender", "MultiPacketSender"]


@st.composite
def arbitrary_packet(
    draw: st.DrawFn,
    flags=st.integers(0, 255),
    stream=st.integers(0, 255),
    window=st.integers(0, (2**16)-1),
    seq=st.integers(0, (2**16)-1),
    ack=st.integers(0, (2**16)-1),
    body=st.binary(),
):
    """
    Hypothesis strategy for generating an arbitrary packet.
    The length matches the data length.
    """
    body = draw(body)
    length = len(body)
    header = Header(
        flags=Flags.decode(bytes([draw(flags)])),
        stream=draw(stream), window=draw(window), seq=draw(seq), ack=draw(ack),
        length=length,
    )
    return Packet(header=header, body=body)


# Apparently it doesn't work to register within an import. Boo.
# st.register_type_strategy(Packet, arbitrary_packet())


class PacketCollector:
    """
    Collect packets from a data stream.
    """
    # Set to true to apply random backpressure.
    # Otherwise, the stream is always ready.
    random_backpressure: bool = False

    packets: List[Packet]

    def __init__(self, stream, random_backpressure=False):
        super().__init__()
        self.random_backpressure = random_backpressure
        self._stream = stream
        self.packets = []

    def is_ready(self):
        """
        Return a ready value, possibly incorporating random backpressure.
        """

        if self.random_backpressure:
            return random.randint(0, 1)
        else:
            return 1

    def recv(self):
        async def receiver(ctx):
            stream = self._stream
            data = bytes()

            header = None

            ready = self.is_ready()
            ctx.set(stream.ready, ready)
            async for clk_edge, rst_value, valid, payload in ctx.tick().sample(
                    stream.valid, stream.payload):
                if rst_value or (not clk_edge):
                    continue
                if ready == 1 and valid == 1:
                    # We just transferred a payload byte.
                    data = data + bytes([payload])
                    ready = self.is_ready()
                else:
                    # Don't become un-ready until we transfer a payload byte
                    ready = ready | self.is_ready()
                ctx.set(stream.ready, ready)

                if header is None and len(data) == Header.BYTES:
                    # Accumulate into a header.
                    header = Header.decode(data)
                    data = bytes()
                elif header is not None and len(data) == header.length:
                    # Completed a packet.
                    self.packets.append(Packet(header=header, body=data))
                    header = None
                    data = bytes()

        return receiver


class MultiPacketSender:
    """
    Transmit multiple packets into an Amaranth object.
    """

    # Set to true to apply random delays to input.
    # Otherwise, the stream is always ready.
    random_delay: bool = False

    # Flag bit, signaled when all bytes from all packets have been delivered.
    done: bool = False

    def __init__(self,
                 random_delay=False,
                 stream=None,
                 packet=None
                 ):
        """
        Construct a packet sender.

        Arguments:
        random_delay: Introduce random delay before bytes are ready.
        stream: Amaranth stream.Signature(8) component to write the packets to.
        packet: PacketSignature() component to write packets to.
        """
        super().__init__()
        self.random_delay = random_delay
        self._stream = stream
        self._packet = packet

    def is_valid(self):
        """
        Return a valid value, possibly incorporating random delay.
        """

        if self.random_delay:
            return random.randint(0, 1)
        else:
            return 1

    def send(self, packets: List[Packet]):
        if self._stream is not None:
            return self.send_to_stream(packets)
        elif self._packet is not None:
            return self.send_packets(packets)
        else:
            assert False, "MultiPacketSender is not configured with any output"

    def send_packets(self, packets: List[Packet]):
        """
        Transmit the packets serially into the constructor-provided
        packet interface.
        """
        async def sender(ctx):
            self.done = False
            iface = self._packet
            for packet in packets:
                ctx.set(iface.header.flags.fin, packet.header.flags.fin)
                ctx.set(iface.header.flags.syn, packet.header.flags.syn)
                ctx.set(iface.header.flags.rst, packet.header.flags.rst)
                ctx.set(iface.header.flags.psh, packet.header.flags.psh)
                ctx.set(iface.header.flags.ack, packet.header.flags.ack)
                ctx.set(iface.header.flags.urg, packet.header.flags.urg)
                ctx.set(iface.header.flags.ecn, packet.header.flags.ecn)
                ctx.set(iface.header.flags.cwr, packet.header.flags.cwr)
                ctx.set(iface.header.stream, packet.header.stream)
                ctx.set(iface.header.length, packet.header.length)
                ctx.set(iface.header.window, packet.header.window)
                ctx.set(iface.header.seq, packet.header.seq)
                ctx.set(iface.header.ack, packet.header.ack)

                # Mark the header present:
                ctx.set(iface.stream_valid, 1)
                ctx.set(iface.header_valid, 1)

                counter = 0
                # We have one cycle before the body is ready
                # just to let the loop below be tidy.
                valid = 0
                async for clk_edge, rst_value, ready in (
                        ctx.tick().sample(iface.data.ready)):
                    if ready == 1 and valid == 1:
                        counter += 1
                        valid = self.is_valid()
                    else:
                        # Become valid, but don't drop validity.
                        valid = valid | self.is_valid()
                    if counter >= len(packet.body):
                        break

                    ctx.set(iface.data.payload, packet.body[counter])
                    ctx.set(iface.data.valid, valid)

                ctx.set(iface.data.valid, 0)
                ctx.set(iface.header_valid, 0)

                # Spend at least once cycle with header !valid
                # before moving to the next example.
                async for _clk_edge, _rst_value, _ready in (
                        ctx.tick().sample(iface.data.ready)):
                    pass

                self.done = True

        return sender

    def send_to_stream(self, packets: List[Packet]):
        """
        Transmit the given packets serially into stream.
        """
        byte_arrays = [p.encode() for p in packets]
        b = reduce(lambda a, b: a + b, byte_arrays, bytes())
        self.done = False

        stream_sender = StreamSender(
            self._stream, random_delay=self.random_delay)

        async def sender(ctx):
            inner_sender = stream_sender.send_passive(b)
            await inner_sender(ctx)
            self.done = True

        return sender


class PacketSender(MultiPacketSender):
    """
    Transmit a single packet into Amaranth.
    """

    def send(self, packet: Packet):
        return super().send([packet])
