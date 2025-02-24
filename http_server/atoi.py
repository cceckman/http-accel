import amaranth as am

from amaranth import Module, Signal, unsigned, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

class AtoI(Component):
    """
    Converts ASCII digit inputs to an positive integer output

    Parameters
    ----------
    width: int
           Number of output bits.

    Attributes
    input:  Stream(8), in
            Datastream of characters to convert
    reset:  Signal(1), in
            Reset and await a new input
    error:  Signal(1), out
            Recieved a non-'0'-'9' input.
    value:  Signal(width), out
    """

    def __init__(self, width: int, **kwargs):
        super().__init__({
                "input" : In(stream.Signature(unsigned(8))),
                "reset" : In(1),
                "error" : Out(1, init=0),
                "value" : Out(width, init=0),
            },  **kwargs)
        self._width = width

    def elaborate(self, _platform):
        m = Module()

        next = Signal(self._width)
        shifted = Signal(self._width)
        increment = Signal(self._width)
        error_comb = Signal(1)

        # Ready to get data if we're out of reset.
        m.d.comb += self.input.ready.eq(~self.reset)

        m.d.comb += [
            error_comb.eq(am.Mux(self.input.valid, 
                                 (self.input.payload < Const(48)) | (self.input.payload > Const(57)),
                                 0)),
            # x*10 = x*8+x*2 = x<<3+x<<1
            shifted.eq((self.value << 3) + (self.value << 1)),
            increment.eq(self.input.payload - Const(48)),
            next.eq(am.Mux(self.input.valid, shifted + increment, self.value))
        ]

        # Error latches, and holds until next reset
        with m.If(self.reset):
            m.d.sync += [
                self.error.eq(0),
                self.value.eq(0),
            ]
        with m.Else():
            m.d.sync += [
                self.error.eq(self.error | error_comb),
                self.value.eq(next),
            ]

        return m
