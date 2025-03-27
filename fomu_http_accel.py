import amaranth as am
from amaranth_boards.fomu_pvt import FomuPVTPlatform
from luna.gateware.interface.gateware_phy import GatewarePHY
from luna.full_devices import USBSerialDevice
from ntcp_http import NtcpHttpServer

__all__ = ["FomuHttpAccelerator"]


class FomuHttpAccelerator(am.Elaboratable):

    def elaborate(self, platform):
        m = am.Module()

        # Use a 12MHz clock as the default: 48MHz / (2^div)
        platform.default_clk = "SB_HFOSC"
        platform.hfosc_div = 2

        clk48 = am.ClockDomain("clk48", local=True)
        clk48.clk = platform.request("clk48", dir="i").i
        m.domains.clk48 = clk48

        rename = am.DomainRenamer({"usb_io": "clk48", "usb": "sync"})

        # From the outside in:
        # USB PHY:
        phy = m.submodules.phy = rename(
            GatewarePHY(io=platform.request("usb")))
        # USB Serial:
        usb_serial = m.submodules.usb_serial = \
            rename(USBSerialDevice(bus=phy, idVendor=0x1209, idProduct=0x5411))
        m.d.comb += usb_serial.connect.eq(1)

        # Server:
        server = m.submodules.server = NtcpHttpServer()
        m.d.comb += [
            usb_serial.rx.ready.eq(server.rx.ready),
            server.rx.payload.eq(usb_serial.rx.payload),
            server.rx.valid.eq(usb_serial.rx.valid),


            server.tx.ready.eq(usb_serial.tx.ready),
            usb_serial.tx.payload.eq(server.tx.payload),
            usb_serial.tx.valid.eq(server.tx.valid),
        ]

        # LED output:
        leds = platform.request("rgb_led")
        m.d.comb += [
            leds.r.o.eq(server.red),
            leds.g.o.eq(server.green),
            leds.b.o.eq(server.blue),
        ]

        return m


if __name__ == "__main__":
    FomuPVTPlatform().build(FomuHttpAccelerator(),
                            # do_program=True,
                            verbose=True)
