from amaranth import Module, Signal, Array
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

# TODO: extract "StringMatch" as a signature.


class StringSeqMatch(Component):
    """
    Match a set of strings in sequence.
    Returns "accepted" once all accept.

    Acceptances and rejections are processed eagerly.
    As soon as one stage accepts, input passes to the
    nexst stage. As soon as a stage rejects,
    the StringSeqMatch rejects.

    Parameters
    ----------
    sequence: List[StringMatch]
                List of StringMatch (or similar objects) to be matched in sequence.

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

    def __init__(self, sequence, **kwargs):
        import math
        size = math.ceil(math.log2(len(sequence)))
        self._sequence = sequence
        super().__init__({
                         "input": In(stream.Signature(8)),
                         "accepted": Out(1),
                         "which": Out(size),
                         "rejected": Out(1),
                         "reset": In(1),
                         })

    def elaborate(self, platform):
        m = Module()

        # Accept / reject:
        # - Reject if any reject
        # - Accept iff the last accepts
        rejected_vec = Signal(len(self._sequence))
        m.d.comb += [rejected_vec[i].eq(self._sequence[i].rejected)
                     for i in range(len(self._sequence))]
        m.d.comb += self.rejected.eq(rejected_vec.any())
        m.d.comb += self.accepted.eq(self._sequence[-1].accepted)

        ready_vec = Signal(len(self._sequence))
        for i in range(0, len(self._sequence)):
            m.submodules += self._sequence[i]
            if i == 0:
                accepted = 0
            else:
                accepted = ~self._sequence[i-1].accepted
            # Remain in reset if:
            # - the sequence is in reset, or
            # - the prior sequence has not accepted
            # (for index 0, ignore the "prior")
            m.d.comb += [
                self._sequence[i].reset.eq(self.reset | accepted)
            ]

            # I/O:
            m.d.comb += [
                self._sequence[i].input.payload.eq(self.input.payload),
                self._sequence[i].input.valid.eq(self.input.valid),
            ]

            m.d.comb += ready_vec[i].eq(
                # If ready, and not accepted / rejected / reset
                self._sequence[i].input.ready
                & ~self._sequence[i].reset
                & ~self._sequence[i].rejected
                & ~self._sequence[i].accepted
            )
        m.d.comb += self.input.ready.eq(ready_vec.any() & ~self.reset)

        return m
