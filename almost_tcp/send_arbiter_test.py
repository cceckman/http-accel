from amaranth.sim import Simulator
from amaranth.lib.wiring import Component, In, Out, connect
from amaranth import Module
from amaranth.lib import stream

from message_hdl import ReadPacketStop, PacketSignature, SendPacketRoot, SendPacketStop
from message_host import Header, Packet, Flags
from packet_fixtures import StreamCollector, MultiPacketSender, arbitrary_packet
from hypothesis import given
from hypothesis.strategies import data


class AtcpSendBus(Component):
    """
    A two-stop packet-send arbiter.

    Packets come in on ports `a` and `b`,
    and come out of `outbus`.
    """

    outbus: Out(stream.Signature(8))
    a: In(PacketSignature())
    b: In(PacketSignature())

    def elaborate(self, platform):
        m = Module()

        m.submodules.a = a = SendPacketStop()
        m.submodules.b = b = SendPacketStop()
        m.submodules.root = root = SendPacketRoot()

        # Inputs:
        self.a = a.packet
        self.b = b.packet
        # Output:
        self.outbus = root.output
        # Ring:
        connect(m, a.upstream, root.downstream)
        connect(m, b.upstream, b.downstream)
        connect(m, root.upstream, a.downstream)

        return m


@given(data())
def test_packet_transmission():
    pass
