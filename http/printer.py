from amaranth import Module, Signal, unsigned, Array, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream


class Printer(Component):
    """
    When activated, prints a constant string to its output stream.

    Parameters
    ----------
    message: str
        The string to print to output.

    Attributes
    ----------
    output: Stream(8), out
            The data stream to write the message to.
    en:     Signal(1), in
            One-shot trigger; start writing the message to output.
    done:   Signal(1), out
            High when inactive, i.e. writing is done.
    """

    output: Out(stream.Signature(unsigned(8)))
    en: In(1)
    done: Out(1, init=1)

    def __init__(self, message):
        self._message = Array(map(ord, message))
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # How many states we need:
        # one for each character ("current printable")
        # plus a "reset" and a "terminal"
        import math
        size = math.ceil(math.log2(len(self._message) + 2))
        count = Signal(size)

        m.d.comb += self.done.eq(count == 0)
        m.d.sync += self.output.valid.eq(0)
        m.d.sync += self.output.payload.eq(0)

        with m.If((count == 0) & self.en):
            # Start writing.
            m.d.sync += count.eq(count + 1)
        with m.Elif(count == Const(len(self._message) + 1)):
            # We've written all the characters; reset.
            # TODO: This spends an extra cycle resetting.
            # I'm letting it slide; we could do an additional comparison
            # in the below Else block instead to save one cycle.
            m.d.sync += count.eq(0)
        with m.Else():
            m.d.sync += self.output.payload.eq(self._message[count - 1]),
            # Try to write this character.
            with m.If(self.output.ready):
                m.d.sync += [
                    self.output.valid.eq(1),
                    count.eq(count + 1)
                ]

        return m
