import amaranth as am
from amaranth.lib.wiring import Out
from amaranth.lib import wiring
# from amaranth_soc import wishbone

__all__ = ["BusBanger"]

# "A component is an elaboratable that declares the shapes and
# directions for its ports in its _signature_."
# https://amaranth-lang.org/docs/amaranth/v0.5.3/stdlib/wiring.html#motivation


class BusBanger(wiring.Component):
    """
    Repeatedly writes an counter to a Wishbone bus.
    The counter's data width equals that of the Wishbone bus.

    Parameters
    ----------
    addr : :class:`Constant` address to write to the bus at.
    wb: :class:`wishbone.Signature` instance to use as an initiator.
        (Note that Signature represents the initiator's perspective
        by default).

    Attributes
    ----------
    wb: `Out(wishbone.Interface)`, outbound Wishbone interface.
    """

    def __init__(self, addr, wbsignature):
        self._addr = addr
        super().__init__({
            "wb": Out(wbsignature),
        })

    @property
    def addr(self):
        return self._addr

    def elaborate(self, platform):
        m = am.Module()

        wb_sig = self.signature.members["wb"].signature
        count = am.Signal(am.unsigned(wb_sig.data_width))
        wb = self.wb

        m.d.comb += wb.adr.eq(self._addr)
        m.d.comb += wb.sel.eq(wb_sig.data_width // 8)
        m.d.comb += wb.we.eq(1)
        m.d.sync += count.eq(count + 1)
        with m.FSM():
            with m.State("Start"):
                # Start a new cycle.
                m.d.sync += wb.cyc.eq(1)
                m.next = "Run"
            with m.State("Run"):
                m.d.sync += wb.cyc.eq(1)
                with m.If(~wb.ack):
                    m.next = "Run"
                with m.Else():
                    m.next = "Done"
            with m.State("Done"):
                m.d.sync += wb.dat_w.eq(count)
                m.d.sync += wb.cyc.eq(0)
                # While still ACKed, hold cyc down and update.
                with m.If(wb.ack):
                    m.next = "Done"
                with m.Else():
                    m.next = "Start"
        return m
