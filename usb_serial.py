import sys
import pdb
import os
import pathlib

import amaranth as am
from amaranth_boards.fomu_pvt import FomuPVTPlatform
# from amaranth_soc import wishbone

__all__ = ["FomuUSBUART"]


class FomuUSBUART(am.Elaboratable):

    def elaborate(self, platform):
        m = am.Module()

        uart_data = am.Signal(8)
        uart_ready = am.Signal()
        uart_valid = am.Signal()

        # Bind directly to the external ports, so we can pass through to the instance.
        # The metadata here are, it seems, required.
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
            ("i", "clk_48mhz", am.ClockSignal()),
            ("i", "reset", am.ResetSignal()),
            ("io", "pin_usb_p", d_p),
            ("io", "pin_usb_n", d_n),
            ("i", "uart_in_data", uart_data),
            ("i", "uart_in_valid", uart_valid),
            ("o", "uart_in_ready", uart_ready),
        )
        m.d.comb += uart_data.eq(0x21)  # !
        m.d.sync += uart_valid.eq(uart_valid)

        return m


def debughook(etype, value, tb):
    pdb.pm()

# sys.excepthook = debughook


if __name__ == "__main__":
    FomuPVTPlatform().build(FomuUSBUART(), do_program=True)
