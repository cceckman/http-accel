import amaranth as am

from amaranth import Module
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
                "input" : In(stream.Signature(8)),
                "reset" : In(1),
                "error" : Out(1),
                "value" : Out(width),
            },  **kwargs)

    def elaborate(self, platform):
        m = Module()

        return m