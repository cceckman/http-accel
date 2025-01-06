import amaranth as am
from amaranth.lib.wiring import In, Out, Component


class Capitalizer(Component):
    """
    Combinatorial-logic (un)capitalizer:
    maps ASCII characters to their uppercase/lowercase equivalent.

    Parameters
    ----------
    to_upper: bool, default True
        True to map to uppercase, False to map to lowercase.


    Attributes
    ----------
    input: Signal(8), input
        Input character to capitalize.
    output: Signal(8), output
        Capitalized character, or the same character.
    """

    input: In(8)
    output: Out(8)

    def __init__(self, *args, to_upper=True, **kwargs):
        super().__init__(*args, **kwargs)
        self._to_upper = to_upper

    def elaborate(self, platform):
        m = am.Module()

        in_bounds = am.Signal()
        m.d.comb += self.output.eq(self.input)

        # We have to ensure this is an 8-bit wide value.
        cap_const = am.Const(32, 8)

        if self._to_upper:
            m.d.comb += in_bounds.eq(
                (self.input >= am.Const(ord('a')))
                &
                (self.input <= am.Const(ord('z')))
            )
            with m.If(in_bounds):
                # To uppercase an ASCII letter, mask off the 32s place.
                m.d.comb += self.output.eq(self.input & ~cap_const)
        else:
            m.d.comb += in_bounds.eq(
                (self.input >= am.Const(ord('A')))
                &
                (self.input <= am.Const(ord('Z')))
            )
            with m.If(in_bounds):
                # To lowercase an ASCII letter, set the 32s place.
                m.d.comb += self.output.eq(self.input | cap_const)

        return m
