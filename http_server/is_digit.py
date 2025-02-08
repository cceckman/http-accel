import amaranth as am
from amaranth.lib.wiring import In, Out, Const, Component

class IsDigit(Component):
    """
    Detects if the last value recieved on the input stream was an ASCII digit.

    Attributes
    ----------
    input:      Signal(8), input
                Input characters to detect if they're a digit.
    is_digit:   Signal(1), out
                High if the input has been rejected (not a number).
    """

    input: In(8)
    is_digit: Out(1)

    def elaborate(self, platform):
        m = am.Module()

        # Fancy idea: ORD(0-9) looks like:
        # 0b0011_0000 ('0' : 48)
        # ...
        # 0b0011_0111 ('7')
        # 0b0011_1000 ('8')
        # 0b0011_1001 ('9')
        # So, if we match bit pattern 0b0011_0xxx or 0b0011_100x, the input is ASCII '0'-'9'
        low_bits = Const(0b00110)
        high_bits = Const(0b0011100)

        low = am.Signal(8)
        high = am.Signal(8)

        m.d.comb += [
            high.eq(self.input[3:]),
            low.eq(self.input[1:]),
            self.is_digit.eq(
                (low == low_bits) |
                (high == high_bits)
            )
        ]

        return m