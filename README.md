Fomu build using the Amaranth toolchain.

To set up a Linux machine for easy passthrough:

```shell
# Allow 'plugdev' to access Fomu USB IDs
cat extras/99-fomu.rules | sudo tee /etc/udev/rules.d/99-fomu.rules
# Disable power-saving autosuspend on Fomu IDs
cat extras/fomu-serial.conf | sudo tee /etc/tlp.d/fomu-serial.conf
```

Make sure you're part of the `dialout` group.

Then try:

```
. ./enter.sh
python3 ./fomu_http_accel.py    # Load onto the device
python3 ./serial_server.py      # Run the host-side proxy
```

