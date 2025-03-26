from amaranth import Module, Signal, Array
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

from .capitalizer import Capitalizer


class StringMatch(Component):
    """
    Matches a literal string in a stream.
    Returns "accepted" or "rejected" immediately upon match

    Parameters
    ----------
    message:     str
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
    rejected:   Signal(1), out
                High if the input has been rejected (will never match).
    reset:      Signal(1), in
                Reset and await new input.
    """

    def __init__(self, message: str, match_case: bool = True, **kwargs):
        super().__init__(**kwargs)

        cased_message = message
        if not match_case:
            cased_message = message.upper()
        self._message = Array(map(ord, cased_message))

        self._match_case = match_case

    input: In(stream.Signature(8))
    accepted: Out(1)
    rejected: Out(1)
    reset: In(1)

    def elaborate(self, platform):
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

        import math
        size = math.ceil(math.log2(len(self._message))) + 1
        idx = Signal(size)

        m.d.comb += [
            self.accepted.eq(0),
            self.rejected.eq(0),
            self.input.ready.eq(1),
        ]
        with m.FSM():
            with m.State("matching"):
                m.d.comb += self.input.ready.eq(1)
                m.next = "matching"
                with m.If(self.input.valid & ~self.reset):
                    # Consume one byte; we're already holding "ready".
                    with m.If(c == self._message[idx]):
                        with m.If(idx < len(self._message) - 1):
                            # Accept this character and move on.
                            m.d.sync += idx.eq(idx + 1)
                        with m.Else():
                            # At the end of the string.
                            m.next = "accepted"
                    with m.Else():
                        # Invalid character.
                        m.next = "rejected"
            with m.State("accepted"):
                m.d.comb += [self.accepted.eq(1)]
                m.next = "accepted"

                m.d.comb += self.input.ready.eq(0)
                m.d.sync += idx.eq(0)
                with m.If(self.reset):
                    m.d.comb += self.input.ready.eq(1)
                    m.next = "matching"

            with m.State("rejected"):
                m.d.comb += [self.rejected.eq(1)]
                m.next = "rejected"

                m.d.comb += self.input.ready.eq(0)
                m.d.sync += idx.eq(0)
                with m.If(self.reset):
                    m.d.comb += self.input.ready.eq(1)
                    m.next = "matching"

        return m
