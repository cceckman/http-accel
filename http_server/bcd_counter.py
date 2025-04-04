from amaranth import Module, Signal, unsigned, Array, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

from .printer import AbstractPrinter

class BcdDigit(Component):
    """
    A single Binary-Coded Decimal Digit

    The 'ovf' of one digit should be connected to the 'inc' of the next digit.

    reset : Signal(1), in. Resets the counter.
    inc    : Signal(1), in
           The counter is incremented on each cycle where `inc` is asserted,
           otherwise retains its value.
    ovf   : Signal(1), out
            `ovf` is asserted when the counter overflows
    digit : Signal(4), out
            The current value of the digit.
    """

    reset: In(1)
    inc: In(1)
    ovf: Out(1, init=1)
    digit: Out(4, init=0)

    def __init__(self):
        super().__init__()

    def elaborate(self, unused_platform):
        m = Module()

        m.d.comb += self.ovf.eq(self.inc & (self.digit == 9))

        with m.If(self.reset):
            m.d.sync += self.digit.eq(0)
        with m.Elif(self.inc):
            with m.If(self.ovf):
                m.d.sync += self.digit.eq(0)
            with m.Else():
                m.d.sync += self.digit.eq(self.digit + 1)
        return m

class BcdCounter(AbstractPrinter):
    """
    An up-counter that uses Binary Coded Decimal (BCD) internally.

    Combines the functionality of the 'UpCounter' and 'Number'. Wraps around and
    sets `ovf` on overflow.

    By counting in BCD, it is able to efficiently print the output as a decimal
    number. Outputs can either be numeric, or ASCII-encoded.

    Note that if counting is enabled after output has been enabled, the results
    may be strange.
    
    Parameters
    ----------
    digits : int
        The number of internal digits.
    ascii : bool
        If true, the output will be ASCII codes

    Attributes
    ----------
    reset   : Signal(1), in. Resets the counter.
    inc     : Signal(1), in
              The counter is incremented on each cycle where `inc` is asserted,
              otherwise retains its value.
    ovf     : Signal(1), out
              `ovf` is asserted when the counter overflows

    AbstractPrinter Attributes
    ----------
    output  : Stream(8), out
              The data stream to write the message to.
    done    : High when stream is inactive, i.e., writing is done.
    en      : Signal(1), in
              One-shot trigger, start writing the message to output.
    """

    reset: In(1)
    inc: In(1)
    ovf: Out(1)

    def __init__(self, width, ascii):
        self._width = width
        self._ascii = ascii
        super().__init__()


    def elaborate(self, unused_platform):
        m = Module()

        digits = Array()
        for d in range(self._width):
            m.submodules[f"digit_{d}"] = BcdDigit()
            m.submodules[f"digit_{d}"].reset = self.reset
            digits.append(m.submodules[f"digit_{d}"].digit)
        m.submodules.digit_0.inc = self.inc

        for d in range(1, self._width):
            m.submodules[f"digit_{d}"].inc = m.submodules[f"digit_{d-1}"].ovf
        self.ovf = m.submodules[f"digit_{self._width-1}"].ovf

        # This really just needs to be ceil(log_2(10^width)) bits wide, but 4*width 
        # should be good enough.
        count = Signal(4*self._width)

        with m.FSM():
            with m.State("idle"):
                m.d.comb += self.done.eq(Const(1)),
                m.d.sync += count.eq(Const(self._width-1))
                with m.If(self.en):
                    m.next = "print"
                    m.d.comb += self.done.eq(Const(0)),
                with m.Else():
                    m.next = "idle"
            with m.State("print"):
                m.d.comb += [
                    self.output.payload.eq(
                        digits[count]+48 if self._ascii else digits[count]
                    ),
                    self.output.valid.eq(Const(1)),
                    self.done.eq(Const(0))
                ]
                with m.If(self.output.ready):
                    with m.If(count > 0):
                        m.d.sync += count.eq(count-1)
                    with m.Else():
                        m.next = "idle"

        return m
