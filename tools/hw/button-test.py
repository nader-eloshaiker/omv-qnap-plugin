#!/usr/bin/python3
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# button-test.py [seconds]: run on the NAS. Prints every key event from the
# qnap8528 input device (press, release and hold time) for a while, default
# 20 s. Press one button per run. Never press the power button: it is ACPI
# and shuts the NAS down.
# Find the qnap8528 input device and print key events for N seconds.
text = open("/proc/bus/input/devices").read()
block = [b for b in text.split("\n\n") if 'Name="qnap8528"' in b][0]
dev = "/dev/input/" + re.search(r"Handlers=.*?(event\d+)", block).group(1)
print("device", dev, "| keys bitmap:", re.search(r"B: KEY=(\S+)", block).group(1), flush=True)
# Meanings verified on a TS-253D; other models may differ.
NAMES = {256: "BTN_0 (chassis open)", 257: "BTN_1 (Reset on TS-253D)",
         258: "BTN_2 (USB Copy on TS-253D)", 116: "KEY_POWER"}
fmt = "llHHi"; size = struct.calcsize(fmt)
fd = os.open(dev, os.O_RDONLY)
end = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 20)
down = {}
while time.time() < end:
    if not select.select([fd], [], [], 0.5)[0]:
        continue
    sec, usec, etype, code, value = struct.unpack(fmt, os.read(fd, size))
    if etype != 1:  # EV_KEY only
        continue
    t = sec + usec / 1e6
    name = NAMES.get(code, "code %d" % code)
    if value == 1:
        down[code] = t
        print("%s %s pressed" % (time.strftime("%H:%M:%S"), name), flush=True)
    elif value == 0:
        held = t - down.pop(code, t)
        print("%s %s released after %.1f s" % (time.strftime("%H:%M:%S"), name, held), flush=True)
print("done", flush=True)
