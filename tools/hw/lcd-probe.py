#!/usr/bin/python3
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# lcd-probe.py [--wake] [--buttons SECONDS] [PORT ...]: run as root on a NAS
# with a front LCD (e.g. TS-877). Finds the serial port of QNAP's LCD module
# (ICP A125 protocol, 1200 8N1) by sending only its "board ID" (4D 00) and
# "protocol version" (4D 07) queries and listening for 53 01 / 53 08
# replies. Default ports: every /dev/ttyS* no other process has open.
#   --wake          first send backlight-on 3 times, 0.5 s apart (some
#                   panels need it after power-up); lights the backlight
#   --buttons N     then print Enter/Select presses (53 05) for N seconds
# Never writes anything else: no text, no reset.
import argparse
import glob
import os
import select
import sys
import termios
import time

QUERIES = ((b"\x4d\x00", "board ID"), (b"\x4d\x07", "protocol version"))
BACKLIGHT_ON = b"\x4d\x5e\x01"


def in_use(port):
    """True if another process has the port open (a console, getty...)."""
    target = os.path.realpath(port)
    for fd in glob.glob("/proc/[0-9]*/fd/*"):
        try:
            if os.readlink(fd) == target:
                return True
        except OSError:
            continue
    return False


def open_raw(port):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    old = termios.tcgetattr(fd)
    new = list(old)
    new[0] = 0                                    # iflag: raw
    new[1] = 0                                    # oflag
    new[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    new[3] = 0                                    # lflag: no echo/canon
    new[4] = new[5] = termios.B1200
    new[6][termios.VMIN] = 0
    new[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, new)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd, old


def read_for(fd, seconds):
    data, end = b"", time.time() + seconds
    while time.time() < end:
        if select.select([fd], [], [], 0.1)[0]:
            try:
                data += os.read(fd, 64)
            except BlockingIOError:
                pass
    return data


def probe(port, wake, buttons):
    try:
        fd, old = open_raw(port)
    except (OSError, termios.error) as e:
        # Ports without a UART behind them fail here (EIO).
        print("%s: cannot open (%s)" % (port, e))
        return False
    found = False
    try:
        if wake:
            for _ in range(3):
                os.write(fd, BACKLIGHT_ON)
                time.sleep(0.5)
            read_for(fd, 0.3)
        for query, name in QUERIES:
            os.write(fd, query)
            reply = read_for(fd, 1.0)
            ok = reply[:1] in (b"\x53", b"\x83")
            found |= ok
            print("%s: %-16s -> %s%s" % (port, name, reply.hex(" ") or "no reply",
                                         "  (LCD module)" if ok else ""))
        if found and buttons:
            print("%s: press Enter / Select for %d s" % (port, buttons))
            end = time.time() + buttons
            while time.time() < end:
                reply = read_for(fd, 0.5)
                i = reply.find(b"\x53\x05")
                while i != -1 and i + 3 < len(reply):
                    mask = reply[i + 3]
                    print("  buttons: %s" % (", ".join(n for b, n in ((1, "ENTER"), (2, "SELECT"))
                                                       if mask & b) or "released"))
                    i = reply.find(b"\x53\x05", i + 4)
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)
        os.close(fd)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wake", action="store_true")
    parser.add_argument("--buttons", type=int, default=0, metavar="SECONDS")
    parser.add_argument("ports", nargs="*")
    args = parser.parse_args()
    ports = args.ports or sorted(glob.glob("/dev/ttyS*"),
                                 key=lambda p: int(p[9:]) if p[9:].isdigit() else 99)
    found = []
    for port in ports:
        if not args.ports and in_use(port):
            print("%s: skipped, in use by another process" % port)
            continue
        if probe(port, args.wake, args.buttons):
            found.append(port)
    print("LCD module found on: %s" % (", ".join(found) or "none"))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
