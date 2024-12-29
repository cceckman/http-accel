#!/usr/bin/env python3
#
# This file is part of LUNA.
#
# Copyright (c) 2020-2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause

import os
from dataclasses import dataclass

from amaranth import (
    Elaboratable, Module, ClockDomain, Signal, DomainRenamer,
    ClockSignal
)
from amaranth.lib.wiring import Component, Out
# from usb_protocol.emitters import DeviceDescriptorCollection

#   from luna.gateware.platform import NullPin, LUNAPlatform
#   from luna.gateware.usb.usb2.device import USBDevice
#   from luna.gateware.interface.gateware_phy import GatewarePHY
from amaranth_boards.fomu_pvt import FomuPVTPlatform


class USBDeviceExample(Component):
    """ Simple example of a USB device using the LUNA framework. """

    usb_clk: Out(1)
    usb_io_clk: Out(1)

    def __init__(self):
        super().__init__()

    def create_descriptors(self):
        """ Create the descriptors we want to use for our device. """

       # descriptors = DeviceDescriptorCollection()

       ##
       # We'll add the major components of the descriptors we we want.
       # The collection we build here will be necessary to create a standard
       # endpoint.
       ##

       # We'll need a device descriptor...
       # with descriptors.DeviceDescriptor() as d:
       #    d.idVendor = 0x1209
       #    d.idProduct = 0x5bf0

       #    d.iManufacturer = "0xcce"
       #    d.iProduct = "HTTP Accelerator"
       #    d.iSerialNumber = "1234"

       #    d.bNumConfigurations = 1

       # ... and a description of the USB configuration we'll provide.
       # with descriptors.ConfigurationDescriptor() as c:

       #    with c.InterfaceDescriptor() as i:
       #        i.bInterfaceNumber = 0

       #        with i.EndpointDescriptor() as e:
       #            e.bEndpointAddress = 0x01
       #            e.wMaxPacketSize = 64

       #        with i.EndpointDescriptor() as e:
       #            e.bEndpointAddress = 0x81
       #            e.wMaxPacketSize = 64

       # return descriptors

    def elaborate(self, platform):
        m = Module()

        # The "stock" Luna example asks for some things we don't have,
        # like clock_domain_generator() and a USB macrocell.
        # We have to take the longer path -- making the clocks manually
        # and wiring directly to I/O:
        # https://luna.readthedocs.io/en/latest/custom_hardware.html#full-speed-using-fpga-i-o

        #   phy_pins = platform.request("usb")

        #   # TODO:  This isn't the right way -- something like "view" may be?
        #   # But I can't figure out how to do it, and this is duck-type-safe.
        #   @dataclass
        #   class USBPhy:
        #       d_p: any
        #       d_n: any
        #       pullup: any

        #   phy_pins = USBPhy(d_p=phy_pins.d_p, d_n=phy_pins.d_n,
        #                     pullup=phy_pins.pullup)
        #   phy = GatewarePHY(io=phy_pins)
        #   m.submodules.phy = phy = DomainRenamer({"usb_io": "sync"})(phy)

        # We need a 12MHz clock too.
        # Based on Luna: gateware/interface/pipe.py
        m.domains.usb = usb = ClockDomain(local=True, async_reset=True)
        # init= is Amaranth 0.5, reset= is amranth 0.4
        decimator = Signal(2, reset=0)
        m.d.comb += usb.clk.eq(decimator == 3)
        m.d.sync += decimator.eq(decimator + 1)
        m.d.comb += self.usb_clk.eq(usb.clk)
        m.d.comb += self.usb_io_clk.eq(ClockSignal("clk48"))

        # Create our USB device interface...
        #   m.submodules.usb = usb = USBDevice(bus=phy)

        # Add our standard control endpoint to the device.
        #   descriptors = self.create_descriptors()
        #   usb.add_standard_control_endpoint(descriptors)

        #   # Connect our device as a high speed device by default.
        #   m.d.comb += [
        #       usb.connect          .eq(1),
        #       usb.full_speed_only  .eq(1 if os.getenv('LUNA_FULL_ONLY') else 0),
        #   ]

        #   # ... and for now, attach our LEDs to our most recent control request.
        #   m.d.comb += [
        #       platform.request_optional(
        #           'led', 0, default=NullPin()).o  .eq(usb.tx_activity_led),
        #       platform.request_optional(
        #           'led', 1, default=NullPin()).o  .eq(usb.rx_activity_led),
        #       platform.request_optional(
        #           'led', 2, default=NullPin()).o  .eq(usb.suspended),
        #   ]

        return m


if __name__ == "__main__":
    FomuPVTPlatform().build(USBDeviceExample(), do_program=True)
