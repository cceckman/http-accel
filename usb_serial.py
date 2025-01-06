import sys
import pdb

import amaranth as am
from amaranth_boards.fomu_pvt import FomuPVTPlatform
from luna.gateware.interface.gateware_phy import GatewarePHY
from luna.full_devices import USBSerialDevice
from http_server.up_counter import UpCounter
from http_server.http_server import HTTP10Server

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
            # usb_serial.tx.payload  .eq(usb_serial.rx.payload),
            # usb_serial.tx.valid    .eq(usb_serial.rx.valid),
            # usb_serial.tx.first    .eq(usb_serial.rx.first),
            # usb_serial.tx.last     .eq(usb_serial.rx.last),
            # usb_serial.rx.ready    .eq(usb_serial.tx.ready),

            # ... and always connect by default.
            usb_serial.connect     .eq(1)
        ]

        # Show USB activity?
        leds = platform.request("rgb_led")

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

        # Connect the HTTP server.
        # Looks like Luna doesn't yet use wiring,
        # so we'll have to connect() manually
        m.submodules.server = server = HTTP10Server()
        m.d.comb += [
            server.input.valid.eq(usb_serial.rx.valid),
            server.input.payload.eq(usb_serial.rx.payload),
            usb_serial.rx.ready.eq(server.input.ready),
        ]
        m.d.comb += [
            usb_serial.tx.valid.eq(server.output.valid),
            usb_serial.tx.payload.eq(server.output.payload),
            server.output.ready.eq(usb_serial.tx.ready),
        ]

        # And show some additional data in the b channel
        m.d.comb += leds.b.o.eq(server.output.valid)

        return m


def debughook(etype, value, tb):
    pdb.pm()


# sys.excepthook = debughook


if __name__ == "__main__":
    FomuPVTPlatform().build(FomuUSBUART(), do_program=True,
                            verbose=True, debug_verilog=True)
