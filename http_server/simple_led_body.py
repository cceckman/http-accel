from amaranth import Module, Signal, Array, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

class SimpleLedBody(Component):
    """
    Handler for a simple HTTP LED body.

    Expects the body to be formated as: "rrggbb\r\n"
      where rr, gg, and bb are two-digit hex values (0-9A-F)

    If the body is well-formed, after the whole body has been
    consumed, will latch the outputs and set accepted.

    If the body is badly-formed, will set the "rejected" output.

    In either event, it will not consume more data until "reset"
    has been asserted.

    Attributes
    ----------
    input:      Stream(8), in
                Data stream to match.
    reset:      Signal(1), in
                Reset and await new input.

    accepted:   Signal(1), out
                High if the string has been matched.
    rejected:   Signal(1), out
                High if the input has been rejected.
    
    red:    Signal(8), out
            Red channel output.
    green:  Signal(8), out
            Green channel output.
    blue:   Signal(8), out
            Blue channel output.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    input: In(stream.Signature(8))
    reset: In(1)

    accepted: Out(1)
    rejected: Out(1)

    red:   Out(8, init=0)
    green: Out(8, init=0)
    blue:  Out(8, init=0)

    def elaborate(self, _platform):
        m = Module()

        hex_numeric = Signal(1)
        m.d.comb += hex_numeric.eq(  (self.input.payload >= ord('0')) 
                                   & (self.input.payload <= ord('9')))

        hex_alpha = Signal(1)
        m.d.comb += hex_alpha.eq(  (self.input.payload >= ord('A'))
                                 & (self.input.payload <= ord('F')))

        valid_hex = Signal(1)
        m.d.comb += valid_hex.eq(hex_numeric | hex_alpha)

        hex_atoi = Signal(4)
        with m.If(hex_numeric):
            m.d.comb += hex_atoi.eq(self.input.payload - ord('0'))
        with m.Elif(hex_alpha):
            m.d.comb += hex_atoi.eq(self.input.payload - ord('A') + 0xA)
        with m.Else():
            m.d.comb += hex_atoi.eq(0)

        idx = Signal(4, init=0)
        pending = Array(Signal(8, init=0) for _ in range(3))

        with m.FSM():
            with m.State("reset"):
                m.next = "matching"
                m.d.sync += [
                    idx.eq(0),
                    pending[Const(0)].eq(0),
                    pending[Const(0)].eq(0),
                    pending[Const(0)].eq(0),
                    self.accepted.eq(0),
                ]
            with m.State("matching"):
                m.d.comb += self.input.ready.eq(1)
                with m.If(self.reset):
                    m.next = "reset"
                with m.If(self.input.valid): 
                    with m.If(valid_hex & (idx < 6)):
                        m.next = "matching"
                        m.d.sync += idx.eq(idx+1)
                        digit = pending[idx >> 1]
                        with m.If(idx & 1):
                            m.d.sync += digit[0:4].eq(hex_atoi)
                        with m.Else():
                            m.d.sync += digit[4:8].eq(hex_atoi)
                    with m.Elif((idx == 6) & (self.input.payload == ord('\r'))):
                        m.d.sync += idx.eq(7)
                        m.next = "matching"
                    with m.Elif((idx == 7) & (self.input.payload == ord('\n'))):
                        m.next = "matched"
                    with m.Else():
                        m.next = "error"
            with m.State("error"):
                m.next = "error"
                m.d.comb += self.input.ready.eq(0)
                with m.If(self.reset):
                    m.next = "reset"
            with m.State("matched"):
                m.next = "matched"
                m.d.comb += self.input.ready.eq(0)
                m.d.sync += [
                    self.accepted.eq(1),
                    self.red.eq(pending[Const(0)]),
                    self.green.eq(pending[Const(1)]),
                    self.blue.eq(pending[Const(2)]),
                ]
                with m.If(self.reset):
                    m.next = "reset"

        return m


