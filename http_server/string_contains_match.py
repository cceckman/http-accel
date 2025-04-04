from amaranth import Module, Signal, Array, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

from .capitalizer import Capitalizer


class StringContainsMatch(Component):
    """
    Matches a literal string in a stream.

    Looks to see if the stream contains the substring, even if it doesn't start
    with it. Equivalent to the regex ".*{message}"

    Returns "accepted" upon match.

    Parameters
    ----------
    message:    str
                String to match.
    match_case: bool, default true
                Perform a case-sensitive match.
                Case folding is ASCII-only.

    Attributes
    ----------
    input:      Stream(8), in
                Data stream to match.
    accepted:   Signal(1), out
                High if the string has been matched.
    reset:      Signal(1), in
                Reset and await new input.
    """

    input: In(stream.Signature(8))
    accepted: Out(1)
    reset: In(1)

    def __init__(self, message: str, match_case: bool = True, **kwargs):
        super().__init__(**kwargs)

        cased_message = message
        if not match_case:
            cased_message = message.upper()
        self._message = Array(map(ord, cased_message))

        self._match_case = match_case


    def elaborate(self, _platform):
        m = Module()

        # Case-normalized data:
        c = Signal(8)
        if self._match_case:
            m.d.comb += c.eq(self.input.payload)
        else:
            m.submodules.capitalizer = capitalizer = Capitalizer()
            m.d.comb += [
                    capitalizer.input.eq(self.input.payload),
                    c.eq(capitalizer.output),
            ]

        with m.If(self.reset):
            m.d.comb += self.input.ready.eq(Const(0))
        with m.Else():
            m.d.comb += self.input.ready.eq(Const(1))

        shift_reg = [Signal(8) for _ in range(len(self._message))]

        latched_accept = Signal(1)

        matched = Signal(len(self._message))
        m.d.comb += matched[0].eq(c == self._message[len(self._message)-1])
        for i in range(1,len(self._message)):
            m.d.comb += matched[i].eq(shift_reg[i-1] == self._message[len(self._message)-i-1])

        with m.If(matched.all()):
            m.d.sync += latched_accept.eq(1)
        m.d.comb += self.accepted.eq(matched.all() | latched_accept)


        with m.If(self.reset):
            m.d.sync += latched_accept.eq(0)
            for i in range(len(self._message)):
                m.d.sync += shift_reg[i].eq(0)
        with m.Elif(self.input.valid):
            for i in range(len(self._message)-2,-1,-1):
                m.d.sync += shift_reg[i+1].eq(shift_reg[i])
            m.d.sync += shift_reg[0].eq(c)

        
        return m
