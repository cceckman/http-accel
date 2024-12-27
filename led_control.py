import amaranth as am
from amaranth.lib import Component


class LedDriver(Component):
    """
    Wishbone interface to the iCE40UL/iCE40UP LED driver.

    For the iCE40UP5K (Fomu),

    Based on Lattice TN1228 - iCE40 LED Driver Usage Guide.

    """

    def __init__(self):
        # TODO: Instance to access "external" signals?
        # https://amaranth-lang.org/docs/amaranth/v0.5.3/guide.html#instances
        super().__init__()

    def elaborate(self, platform):
        m = am.Module()

        return m
