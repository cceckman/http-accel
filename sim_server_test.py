
from amaranth import Module
from amaranth.lib.wiring import Component, In, connect
from amaranth.lib import stream
from amaranth.lib import fifo

from sim_server import SimServer

from http_server.capitalizer import Capitalizer


class DelayCapitalizer(Component):
    """
    A capitalizer but on a one-cycle delay.
    """

    rx: In(stream.Signature(8))
    # This should be Out...but runs into the cases where wiring.connect
    # mistakes In and Out for submodules.
    tx: In(stream.Signature(8))

    def elaborate(self, platform):
        m = Module()
        caps = m.submodules.caps = Capitalizer()
        queue = m.submodules.fifo = fifo.SyncFIFOBuffered(width=8, depth=1)

        m.d.comb += [
            caps.input.eq(self.rx.payload),
            queue.w_stream.payload.eq(caps.output),
            queue.w_stream.valid.eq(self.rx.valid),
            self.rx.ready.eq(queue.w_stream.ready),
        ]
        connect(m, queue.r_stream, self.tx)
        return m


def test_sim():
    dut = DelayCapitalizer()

    with SimServer(dut, dut.tx, dut.rx) as srv:
        hello = "hello, world"
        print("sending data")
        srv.send(hello)
        print("sent data, awaiting response")

        got = srv.recv(len(hello))
        print("got response")
        want = b"HELLO, WORLD"
        assert got == want, (
            f"unexpected result: got \"{got}\", want \"{want}\""
        )
