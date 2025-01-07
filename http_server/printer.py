from amaranth import Module, Signal, unsigned, Array, Const, Assert
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
        import math
        size = math.ceil(math.log2(len(self._message)))
        count = Signal(size)

        m.d.comb += [
            self.output.valid.eq(0),
            self.output.payload.eq(self._message[count]),

        ]

        with m.FSM():
            with m.State("idle"):
                m.d.comb += self.done.eq(Const(1))
                m.next = "idle"
                m.d.sync += Assert(count == 0)
                with m.If(self.en):
                    m.d.comb += self.done.eq(Const(0))
                    m.next = "running"
            with m.State("running"):
                m.d.comb += [
                    self.done.eq(Const(0)),
                    self.output.valid.eq(Const(1)),
                ]
                m.next = "running"
                with m.If(self.output.ready):
                    # At the next clock cycle,
                    # either reset and become "done"
                    # or print a character.
                    # Ready to advance to the next state.
                    with m.If(count == len(self._message) - 1):
                        # At the end of the message; return to idle.
                        m.d.sync += count.eq(Const(0))
                        m.next = "idle"
                    with m.Else():
                        # Continue printing the message.
                        m.d.sync += count.eq(count + 1)

        return m
