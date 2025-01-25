from amaranth import Module, Signal
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

# TODO: extract "StringMatch" as a signature.


class StringAltMatch(Component):
    """
    Match a number of alternative strings.
    Returns "accepted" once any accepts (shortest-match),
    or returns "rejected" once all reject.

    Parameters
    ----------
    alternatives: List[StringMatch]
                List of StringMatch (or similar objects) as alternatives.

    Attributes
    ----------
    input:      Stream(8), in
                Data stream to match.
    accepted:   Signal(1), out
                High if the string has been matched.
    which:      Signal(n), out
                If accepted, the index of the matched alternative.
    rejected:   Signal(1), out
                High if the input has been rejected (will never match).
    reset:      Signal(1), in
                Reset and await new input.
    """

    def __init__(self, alternatives, **kwargs):
        import math
        size = math.ceil(math.log2(len(alternatives)))
        self._alternatives = alternatives
        super().__init__({
                         "input": In(stream.Signature(8)),
                         "accepted": Out(1),
                         "which": Out(size),
                         "rejected": Out(1),
                         "reset": In(1),
                         })

    def elaborate(self, platform):
        m = Module()

        # Aggregate signals:
        ready_vec = Signal(len(self._alternatives))
        accepted_vec = Signal(len(self._alternatives))
        rejected_vec = Signal(len(self._alternatives))
        terminated_vec = Signal(len(self._alternatives))

        for i in range(0, len(self._alternatives)):
            alt = self._alternatives[i]
            # These have to be contained somewhere...
            m.submodules += self._alternatives[i]
            m.d.comb += [
                alt.reset.eq(self.reset),
                alt.input.payload.eq(self.input.payload),
                accepted_vec[i].eq(alt.accepted),
                rejected_vec[i].eq(alt.rejected),
                terminated_vec[i].eq(alt.accepted | alt.rejected),
                # We want all matchers to be ready -- or terminated --
                # before we consume, since we consume to all matchers
                # simultaneously.
                ready_vec[i].eq(alt.input.ready | terminated_vec[i]),
                # That also means we need to mask "valid" against readiness,
                # so we only appear valid to sub-matches if we actually are.
                alt.input.valid.eq(self.input.valid & ready_vec.all()),
            ]
        m.d.comb += [
            self.accepted.eq(accepted_vec.any()),
            self.rejected.eq(rejected_vec.all()),
            self.input.ready.eq(ready_vec.all() & ~(
                self.accepted | self.rejected)),
        ]
        # Inline priority encoder:
        for i in reversed(range(len(self._alternatives))):
            with m.If(accepted_vec[i]):
                m.d.comb += self.which.eq(i)

        return m
