import amaranth as am
from amaranth_boards.fomu_pvt import FomuPVTPlatform
from amaranth_soc import wishbone

__all__ = ["HTTPAccel"]


class HTTPAccel(am.Elaboratable):
    def __init__(self):
        self.sig = wishbone.Signature(
            addr_width=8,
            data_width=8,
            granularity=8,
            features=[wishbone.Feature.STALL],
        )

    def elaborate(self, platform):
        from up_counter import UpCounter
        m = am.Module()

        # A free-running cycle counter, to ease debugging.
        m.submodules.counter = UpCounter(2**16-1)
        m.submodules.counter.en = am.Signal(1, init=1)

        m.submodules.arbiter = wishbone.Arbiter(
            addr_width=self.sig.addr_width,
            data_width=self.sig.data_width,
            granularity=self.sig.granularity,
            features=self.sig.features)

        return m


if __name__ == "__main__":
    FomuPVTPlatform().build(HTTPAccel(), do_program=True)
