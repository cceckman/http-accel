
from amaranth_boards.fomu_pvt import FomuPVTPlatform
from fomu_http_accel import FomuHttpAccelerator


def test_build():
    FomuPVTPlatform().build(FomuHttpAccelerator(), verbose=True)
