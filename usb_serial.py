import sys
import pdb

import amaranth as am
from amaranth_boards.fomu_pvt import FomuPVTPlatform
from luna.gateware.interface.gateware_phy import GatewarePHY
from luna.gateware.usb.usb2.device import USBDevice
from usb_protocol.emitters import DeviceDescriptorCollection
from up_counter import UpCounter
from luna.full_devices import USBSerialDevice

__all__ = ["FomuUSBUART"]


class FomuUSBUART(am.Elaboratable):

    def elaborate(self, platform):
        m = am.Module()

        # Use a 12MHz clock as the default: 48MHz / (2^div)
        platform.default_clk = "SB_HFOSC"
        platform.hfosc_div = 2

        clk48 = am.ClockDomain("clk48", local=True)
        clk48.clk = platform.request("clk48", dir="i").i
        m.domains.clk48 = clk48

        rename = am.DomainRenamer({"usb_io": "clk48", "usb": "sync"})

        # Get the external pins from the platform.
        # dir="-" says "give me an IOValue",
        # self.d.comb += usb.pullup.o.eq(1)
        m.submodules.phy = phy = rename(
            GatewarePHY(io=platform.request("usb")))

        # from luna/examples/usb/acm_serial.py
        m.submodules.usb_serial = usb_serial = \
            rename(USBSerialDevice(bus=phy, idVendor=0x1209, idProduct=0x5411))
        m.d.comb += [
            # Place the streams into a loopback configuration...
            usb_serial.tx.payload  .eq(usb_serial.rx.payload),
            usb_serial.tx.valid    .eq(usb_serial.rx.valid),
            usb_serial.tx.first    .eq(usb_serial.rx.first),
            usb_serial.tx.last     .eq(usb_serial.rx.last),
            usb_serial.rx.ready    .eq(usb_serial.tx.ready),

            # ... and always connect by default.
            usb_serial.connect     .eq(1)
        ]

        # Show USB activity?
        leds = platform.request("rgb_led")
        # m.d.comb += leds.r.o.eq(usb_serial.rx_activity_led)
        # m.d.comb += leds.b.o.eq(usb_serial.tx_activity_led)

        # Blink the green channel to show liveness:
        m.submodules.up_counter = up_counter = UpCounter(
            int(platform.default_clk_frequency) // 2)
        m.d.comb += up_counter.en.eq(am.Const(1))
        lit = am.Signal(1)
        with m.If(up_counter.ovf):
            m.d.sync += lit.eq(~lit)
        with m.Else():
            m.d.sync += lit.eq(lit)
        m.d.comb += leds.g.o.eq(lit)

        return m


def debughook(etype, value, tb):
    pdb.pm()


# sys.excepthook = debughook


if __name__ == "__main__":
    FomuPVTPlatform().build(FomuUSBUART(), do_program=True,
                            verbose=True, debug_verilog=True)
