from amaranth import Module
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class UpCounter(wiring.Component):
    """
    An up-counter with a fixed limit.
    Automatically uses as many bits as necessary.

    Parameters
    ----------
    limit : int
        The value at which the counter overflows.

    Attributes
    ----------
    en :    Signal, in
            The counter is incremented on each cycle where ``en`` is asserted,
            and otherwise retains its value.
    ovf:    Signal, out
            ``ovf`` is asserted when the counter reaches its limit.
    count:  Signal(...), out
            The current count.count.

    """

    def __init__(self, limit):
        # Ensure we have enough space:
        import math
        size = math.ceil(math.log2(limit))

        super().__init__({
            "en": In(1),
            "ovf": Out(1),
            "count": Out(size),
        })

        self.limit = limit

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.ovf.eq(self.count == self.limit)

        with m.If(self.en):
            with m.If(self.ovf):
                m.d.sync += self.count.eq(0)
            with m.Else():
                m.d.sync += self.count.eq(self.count + 1)
        return m
