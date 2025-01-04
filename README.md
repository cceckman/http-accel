Fomu build using the Amaranth toolchain.

Try:

```
./do venv
source ./venv.dir/bin/activate
python usb_serial.py
```

Puts a program on the Fomu that:

- Acts as a USB-serial loopback device -- echos all input
- Blinks the green LED at 1Hz (so you know it's programmed)


