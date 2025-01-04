import pdb
import pathlib

import amaranth as am
from amaranth_boards.fomu_pvt import FomuPVTPlatform
# from amaranth_soc import wishbone

__all__ = ["FomuUSBUART"]


class FomuUSBUART(am.Elaboratable):

    def elaborate(self, platform):
        m = am.Module()

        # Use a 12MHz clock as the default: 48MHz / (2^div)
        #   platform.default_clk = "SB_HFOSC"
        #   platform.hfosc_div = 2

        clk48 = am.ClockDomain("clk48", local=True)
        clk48.clk = platform.request("clk48", dir="i").i
        m.domains.clk48 = clk48

        # Get the external pins from the platform.
        # dir="-" says "give me an IOValue",
        # which is what we need to pass to an Instance.
        usb = platform.request("usb", dir="-")
        d_p = usb.d_p.io
        d_n = usb.d_n.io
        # self.d.comb += usb.pullup.o.eq(1)

        # Ensure all TinyFPGA_BX_USB files are available.
        tinyfpga_dir = pathlib.Path("tinyfpga_usb")
        for f in tinyfpga_dir.glob("*.v"):
            with f.open() as fd:
                platform.add_file(f.as_posix(), fd)

        m.submodules.usb_uart = am.Instance(
            "usb_uart",
            ("i", "clk_48mhz", am.ClockSignal("clk48")),
            ("i", "reset", am.ResetSignal("clk48")),
            ("io", "pin_usb_p", d_p),
            ("io", "pin_usb_n", d_n),
            ("i", "uart_in_data", am.Const(0x21)),  # !
            ("i", "uart_in_valid", am.Const(0)),
            ("i", "uart_out_ready", am.Const(0)),
        )

        return m


def debughook(etype, value, tb):
    pdb.pm()

# import sys
# sys.excepthook = debughook


if __name__ == "__main__":
    FomuPVTPlatform().build(FomuUSBUART(), do_program=True,
                            verbose=True, debug_verilog=True)
