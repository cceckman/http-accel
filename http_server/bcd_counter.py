from amaranth import Module, unsigned 
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

class BcdCounter(Component):
    """
    An up-counter that uses Binary Coded Decimal (BCD) internally.

    Combines the functionality of the 'UpCounter' and 'Number'. Wraps around and
    sets `ovf` on overflow.

    By counting in BCD, it is able to efficiently print the output as a decimal
    number. Outputs can either be numeric, or ASCII-encoded.

    Parameters
    ----------
    digits : int
        The number of internal digits.
    ascii : bool
        If true, the output will be ASCII codes

    Attributes
    ----------
    reset    : Signal(1), in. Resets the counter.
    en       : Signal(1), in
               The counter is incremented on each cycle where `en` is asserted,
               otherwise retains its value.
    triggger : Signal(1), in
               One-shot trigger, start writing the message to output.
    ovf      : Signal(1), out
               `ovf` is asserted when the counter overflows
    output   : Stream(8), out
               The data stream to write the message to.
    done     : High when stream is inactive, i.e., writing is done.
    """

    def __init__(self, width, ascii):
        super().__init__({
            "reset": In(1),
            "en": In(1),
            "trigger": In(1),
            "ovf": Out(1),
            "output": Out(stream.Signature(unsigned(8))),
            "done": Out(1, init=1),
        })

        self._width = width
        self._ascii = ascii

    def elaborate(self, unused_platform):
        m = Module()

        return m