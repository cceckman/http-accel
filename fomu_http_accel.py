from amaranth_boards.fomu_pvt import FomuPVTPlatform

__all__ = ["FomuHTTPAccel"]


class FomuHTTPAccel(FomuPVTPlatform):
    pass


if __name__ == "__main__":
    from amaranth_boards.test.blinky import Blinky
    FomuHTTPAccel().build(Blinky(), do_program=True)
