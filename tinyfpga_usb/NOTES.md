I've been trying to deploy https://github.com/juanmard/tinyfpga_bx_usbserial
onto my Fomu, and not having luck so far.

The device starts up, the LED looks like it's doing the right thing...
But if I try to open /dev/ttyACMn, the device falls off the bus.

I opened up Wireshark's USB monitoring and watched the bus.
It looks like after the DFU sequence, we get:

- Device gets enumerated, reports USB CDC class (good)
- Host polls three times for DEVICE QUALIFIER; returns "broken pipe" each time (??)
- Host asks for CONFIGURATION; device reports SELF-POWERED NO REMOTE-WAKEUP
    - The device is on a self-powered USB hub, but the Fomu itself is absolutely bus-powered. This may be a bug in the bitstream?
- Host asks for more CONFIGURATION, gets the whole CDC interface stuff (good)
- Host does a SET CONFIGURATION with no data (??), acknowledged as a success
- Host provides SET LINE CODING: 9600 baud, 1 stop bit, no parity, 8-bit data.
    Device acknowledges (no error, good)
- After 2 seconds, **host sets PORT_SUSPEND** for the relevant port on the hub.

  I suspect this is where things start going wrong, and I'll need to disable autosuspend for this device in my kernel.
  (My host is a laptop, which I suspect has autosuspend-by-default!)

After this, if I try to open the device, I get a I/O error and the device falls off the bus.
I guess there's nothing to unsuspend the device?
Or maybe I should try unsuspending manually and then opening it.

---

Yes, disabling the power-save with tlp(8) works to get hello_world working. Yay!
