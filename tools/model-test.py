#!/usr/bin/python3
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# model-test.py [--interactive] [-o FILE]: run as root on a QNAP NAS to
# report how the plugin sees it, for a "Model test report" issue. See
# docs/testing/model-testing.md.
#
# Without --interactive it only reads: system and driver versions, sensors,
# fans, LEDs, buttons, disk and PCI topology. It never runs smartctl and
# never reads drivetemp, so sleeping disks stay asleep. Serial numbers,
# host names, MAC and IP addresses are removed from the output.
#
# --interactive also runs checks that need a person at the NAS and change
# hardware state for a moment: LED mapping, buttons, a fan PWM sweep (the
# fans slow down and may stop briefly), disk-to-bay activity and one short
# beep. Each step asks first. qnapd is stopped during the checks and
# started again after.

import argparse
import glob
import json
import os
import re
import select
import socket
import struct
import subprocess
import sys
import time

SYS = "/sys"
DRIVER = "qnap8528"
# Abort a fan step when a sensor reaches its limit (as tools/hw/fan-sweep.sh).
TEMP_LIMITS = {"coretemp": 85, "k10temp": 85, "acpitz": 85,
               "nvme": 70, "qm2": 70}
TEMP_LIMIT_OTHER = 50
SWEEP_STEPS = (255, 200, 160, 128, 100, 80, 64, 50, 40, 30, 20, 10, 0)
SWEEP_HOLD = 10
KEY_NAMES = {256: "BTN_0", 257: "BTN_1", 258: "BTN_2", 259: "BTN_3",
             116: "KEY_POWER"}
EV_SND, SND_TONE = 0x12, 0x02


def read(path):
    try:
        with open(path) as f:
            return f.read().replace("\0", "").strip()
    except OSError:
        return None


def write(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def first_line(text):
    return (text or "").strip().splitlines()[0] if (text or "").strip() else None


def hwmons():
    """{name: [hwmon dirs]}"""
    result = {}
    for h in sorted(glob.glob(SYS + "/class/hwmon/hwmon*")):
        result.setdefault(read(h + "/name") or "?", []).append(h)
    return result


def numbered(directory, pattern):
    """Files like fan3_input sorted by their number."""
    files = glob.glob(os.path.join(directory, pattern))
    return sorted(files, key=lambda p: int(re.search(r"(\d+)", os.path.basename(p)).group(1)))


# ---------------------------------------------------------------- redaction

def is_secret(value):
    """QNAP BIOSes fill every DMI field, serials included, with "Default
    string"; redacting that would blank the vendor and product too. Real
    serial numbers have no spaces."""
    return bool(value) and len(value) >= 4 and not re.search(r"\s", value) \
        and value.lower() not in ("none", "default", "n/a", "unknown",
                                  "0123456789", "00:00:00:00:00:00") \
        and not re.fullmatch(r"[0f-]+", value.lower())


def secrets():
    """Values that must never appear in a report."""
    found = set()
    patterns = [SYS + "/class/dmi/id/*serial*", SYS + "/class/dmi/id/product_uuid",
                SYS + "/devices/platform/%s/vpd/*serial*" % DRIVER,
                SYS + "/devices/platform/qm2*/serial",
                SYS + "/block/*/device/serial", SYS + "/block/*/device/wwid",
                SYS + "/class/nvme/*/serial", SYS + "/class/net/*/address"]
    for pattern in patterns:
        for path in glob.glob(pattern):
            if is_secret(read(path)):
                found.add(read(path))
    for name in (socket.gethostname(), socket.getfqdn()):
        if name and name not in ("localhost", "localhost.localdomain"):
            found.add(name)
            found.add(name.split(".")[0])
    return found


def redact(text, values):
    for value in sorted(values, key=len, reverse=True):
        text = re.sub(r"(?<![\w-])%s(?![\w-])" % re.escape(value),
                      "[redacted]", text)
    text = re.sub(r"(?i)\b(serial(?:[ _]?(?:number|no))?)(\s*[=:]\s*)[^\s,;'\"]+",
                  r"\1\2[redacted]", text)
    text = re.sub(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", "[mac]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b(?!\.)", "[ip]", text)
    return text


def drop_serials(value):
    """JSON from qnapd without any serial fields."""
    if isinstance(value, dict):
        return {k: drop_serials(v) for k, v in value.items()
                if "serial" not in k.lower()}
    if isinstance(value, list):
        return [drop_serials(v) for v in value]
    return value


# ------------------------------------------------------------------ report

def transport(block):
    """How a block device is attached, from its sysfs path."""
    path = os.path.realpath(block)
    name = os.path.basename(block)
    if name.startswith("nvme"):
        return "nvme"
    if re.search(r"/usb\d+/", path):
        return "usb"
    match = re.search(r"/ata(\d+)/", path)
    if match:
        return "sata port %s" % match.group(1)
    return "other"


def pci_path(block):
    """PCI addresses from the root complex to the device, e.g.
    0000:00:1c.0 > 0000:01:00.0."""
    return " > ".join(re.findall(r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]",
                                 os.path.realpath(block)))


def disks():
    rows = []
    blocks = glob.glob(SYS + "/block/sd*") + glob.glob(SYS + "/block/nvme*n*")
    for block in sorted(blocks):
        name = os.path.basename(block)
        sectors = read(block + "/size")
        model = read(block + "/device/model") or \
            read(block + "/device/device/model") or "?"
        rows.append({
            "device": name,
            "attached": transport(block),
            "rotational": read(block + "/queue/rotational") == "1",
            "removable": read(block + "/removable") == "1",
            "size_gb": round(int(sectors) * 512 / 1e9) if sectors else None,
            "model": model,
            "pci": pci_path(block),
        })
    return rows


def sensors():
    lines = []
    for name, dirs in hwmons().items():
        for h in dirs:
            if name == "drivetemp":
                lines.append("%s %s: not read (reading it may wake disks)"
                             % (os.path.basename(h), name))
                continue
            for f in numbered(h, "temp*_input") + numbered(h, "fan*_input") + \
                    numbered(h, "pwm[0-9]") + numbered(h, "pwm[0-9]_enable"):
                base = os.path.basename(f)
                label = read(os.path.join(h, base.replace("_input", "_label")))
                lines.append("%s %s %s = %s%s" % (
                    os.path.basename(h), name, base, read(f),
                    " (%s)" % label if label else ""))
    return lines


def leds():
    lines = []
    for led in sorted(glob.glob(SYS + "/class/leds/*")):
        trigger = re.search(r"\[([^]]+)\]", read(led + "/trigger") or "")
        lines.append("%s max=%s brightness=%s trigger=%s" % (
            os.path.basename(led), read(led + "/max_brightness"),
            read(led + "/brightness"), trigger.group(1) if trigger else "?"))
    return lines


def input_device():
    text = read("/proc/bus/input/devices") or ""
    for block in text.split("\n\n"):
        if 'Name="%s"' % DRIVER in block:
            return block.strip()
    return None


def serial_ports():
    """UARTs the kernel found (type 0 = no UART). QNAP front LCDs hang off
    one of them (tools/hw/lcd-probe.py finds which)."""
    lines = []
    for tty in sorted(glob.glob(SYS + "/class/tty/ttyS*"),
                      key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0)):
        kind = read(tty + "/type")
        if kind and kind != "0":
            lines.append("%s type=%s port=%s irq=%s" % (
                os.path.basename(tty), kind, read(tty + "/port"),
                read(tty + "/irq")))
    return lines


def speaker():
    """The pcspkr input device: the buzzer on the TS-253D."""
    found = glob.glob("/dev/input/by-path/*pcspkr*")
    return found[0] if found else None


def kernel_log():
    for cmd in (["dmesg"], ["journalctl", "-k", "-b", "--no-pager", "-o", "cat"]):
        out = run(cmd)
        if out:
            return [l for l in out.splitlines()
                    if re.search(r"qnap8528|qm2|it87|nct6", l, re.I)][-60:]
    return []


def attrs(directory, skip=("serial",)):
    result = {}
    for path in sorted(glob.glob(directory + "/*")):
        base = os.path.basename(path)
        if os.path.isfile(path) and not any(s in base for s in skip) \
                and base not in ("uevent", "modalias", "driver_override"):
            value = read(path)
            if value is not None and len(value) < 200:
                result[base] = value
    return result


def section(title, body, fold=False):
    if isinstance(body, (list, tuple)):
        body = "\n".join(body) if body else "(none)"
    block = "```\n%s\n```" % body
    if fold:
        return "<details><summary>%s</summary>\n\n%s\n\n</details>\n" % (title, block)
    return "### %s\n\n%s\n" % (title, block)


def report():
    dmi = SYS + "/class/dmi/id/"
    cmdline = (read("/proc/cmdline") or "").split()
    system = [
        "plugin:   %s" % (run(["dpkg-query", "-W", "-f", "${Version}",
                                "openmediavault-qnap"]) or "not installed"),
        "omv:      %s" % (run(["dpkg-query", "-W", "-f", "${Version}",
                                "openmediavault"]) or "not installed"),
        "debian:   %s" % read("/etc/debian_version"),
        "kernel:   %s" % os.uname().release,
        "firmware: %s" % ("EFI" if os.path.isdir(SYS + "/firmware/efi") else "BIOS"),
        "reboot=:  %s" % (" ".join(c for c in cmdline if c.startswith("reboot=")) or "-"),
        "dmi:      %s / %s / board %s" % (read(dmi + "sys_vendor"),
                                          read(dmi + "product_name"),
                                          read(dmi + "board_name")),
        "bios:     %s (%s)" % (read(dmi + "bios_version"), read(dmi + "bios_date")),
        "cpu:      %s" % next((l.split(":", 1)[1].strip() for l in
                               (read("/proc/cpuinfo") or "").splitlines()
                               if l.startswith("model name")), "?"),
    ]
    drivers = []
    for module in (DRIVER, "qm2mod"):
        loaded = os.path.isdir(SYS + "/module/" + module)
        drivers.append("%s: %s%s" % (module, "loaded" if loaded else "not loaded",
                                     " (version %s)" % read(SYS + "/module/%s/version" % module)
                                     if read(SYS + "/module/%s/version" % module) else ""))
    platform = SYS + "/devices/platform/" + DRIVER
    for sub in ("ec", "vpd"):
        for k, v in attrs(os.path.join(platform, sub)).items():
            drivers.append("%s/%s: %s" % (sub, k, v))
    qm2 = []
    for card in sorted(glob.glob(SYS + "/devices/platform/qm2*")):
        qm2.append("%s: %s" % (os.path.basename(card),
                               json.dumps(attrs(card))))
    qnapd = ["service: %s" % (run(["systemctl", "is-active", "qnapd"]).strip() or "?")]
    for sub in ("info", "status"):
        out = run(["qnapd", sub, "--json"])
        try:
            qnapd.append("qnapd %s: %s" % (sub, json.dumps(drop_serials(json.loads(out)), indent=1)))
        except ValueError:
            qnapd.append("qnapd %s: not available" % sub)
    disk_rows = ["%-8s %-14s %-4s %-9s %6s GB  %-24s %s" % (
        d["device"], d["attached"], "hdd" if d["rotational"] else "ssd",
        "removable" if d["removable"] else "fixed", d["size_gb"], d["model"],
        d["pci"]) for d in disks()]

    parts = [
        "## Read-only report\n",
        section("System", system),
        section("Drivers", drivers),
        section("Sensors, fans and PWM", sensors()),
        section("LEDs", leds()),
        section("Buttons (input device)", input_device() or "qnap8528 input device not found"),
        section("Disks (no S.M.A.R.T. read)", disk_rows),
        section("QM2 cards", qm2),
        section("Serial ports (front LCD candidates)", serial_ports()),
        section("Speaker (buzzer candidate)", speaker() or "no pcspkr input device"),
        section("qnapd", qnapd, fold=True),
        section("PCI tree (lspci -tv)", run(["lspci", "-tv"]) or "lspci not available", fold=True),
        section("Kernel log (driver lines)", kernel_log(), fold=True),
    ]
    return "\n".join(parts)


# ------------------------------------------------------------- interactive

def ask(question):
    try:
        return input(question + " ").strip()
    except EOFError:
        return ""


def yes(question):
    return ask(question + " [y/N]").lower() in ("y", "yes")


def hottest_over_limit():
    for name, dirs in hwmons().items():
        if name == "drivetemp":
            continue
        limit = TEMP_LIMITS.get(name, TEMP_LIMIT_OTHER)
        for h in dirs:
            for f in glob.glob(h + "/temp*_input"):
                try:
                    t = int(read(f)) / 1000
                except (TypeError, ValueError):
                    continue
                if t >= limit:
                    return "%s %s = %.0f C" % (name, os.path.basename(f), t)
    return None


class Checks:
    def __init__(self):
        self.results = []
        self.qnapd_was_active = run(["systemctl", "is-active", "qnapd"]).strip() == "active"
        self.pwms = []  # (path, value to restore)

    def note(self, line):
        print(line)
        self.results.append(line)

    def stop_qnapd(self):
        if not self.qnapd_was_active:
            self.note("qnapd was not running")
            return
        run(["systemctl", "stop", "qnapd"])
        time.sleep(2)
        values = [read(p) for p in self.chassis_pwms()]
        self.note("failsafe after `systemctl stop qnapd`: pwm = %s (expect 255)"
                  % ", ".join(v or "?" for v in values))

    def restore(self):
        for path, _ in self.pwms:
            try:
                write(path, 255)
            except OSError:
                pass
        if self.qnapd_was_active:
            run(["systemctl", "start", "qnapd"])

    @staticmethod
    def chassis_pwms():
        return [p for h in hwmons().get(DRIVER, []) for p in numbered(h, "pwm[0-9]")]

    def led_mapping(self):
        bays = sorted(glob.glob(SYS + "/class/leds/%s::hdd*" % DRIVER),
                      key=lambda p: int(re.search(r"hdd(\d+)$", p).group(1)))
        others = [p for p in glob.glob(SYS + "/class/leds/%s::*" % DRIVER)
                  if p not in bays and not p.endswith("::status")]
        slots = sorted(glob.glob(SYS + "/class/leds/qm2-*:green:slot*"))
        if not (bays or others or slots):
            self.note("LEDs: none found")
            return
        print("\nEach LED lights for 5 s. Watch the front of the NAS "
              "(QM2 slots: the card's rear bracket).")
        for led in bays + others + slots:
            name = os.path.basename(led)
            old = (read(led + "/brightness"), re.search(r"\[([^]]+)\]", read(led + "/trigger") or ""))
            maximum = int(read(led + "/max_brightness") or 1)
            on = min(2 if "::hdd" in name else 1, maximum)
            try:
                write(led + "/trigger", "none")
                write(led + "/brightness", on)
                time.sleep(5)
            finally:
                write(led + "/trigger", "none")
                write(led + "/brightness", old[0] or 0)
                if old[1] and old[1].group(1) != "none":
                    write(led + "/trigger", old[1].group(1))
            if "::hdd" in name:
                answer = ask("%s lit red: which bay number (as printed on the "
                             "case)? n = nothing lit:" % name)
            elif "slot" in name:
                answer = ask("%s lit green: which slot on the card? n = nothing:" % name)
            else:
                answer = ask("%s: what lit, and in which colour? n = nothing:" % name)
            self.note("LED %s -> %s" % (name, answer or "?"))

    def buttons(self):
        block = input_device()
        match = re.search(r"Handlers=.*?(event\d+)", block or "")
        if not match:
            self.note("buttons: qnap8528 input device not found")
            return
        fd = os.open("/dev/input/" + match.group(1), os.O_RDONLY)
        fmt = "llHHi"
        size = struct.calcsize(fmt)
        print("\nNever press the power button: it shuts the NAS down.")
        try:
            while True:
                button = ask("Name the button you will press (e.g. 'USB Copy', "
                             "'Reset pinhole'), or Enter when done:")
                if not button:
                    break
                print("Press and release it once within 15 s...")
                end, down, seen = time.time() + 15, {}, []
                while time.time() < end:
                    if not select.select([fd], [], [], 0.5)[0]:
                        continue
                    sec, usec, etype, code, value = struct.unpack(fmt, os.read(fd, size))
                    if etype != 1:
                        continue
                    if value == 1:
                        down[code] = sec + usec / 1e6
                    elif value == 0:
                        seen.append("%s held %.1f s" % (
                            KEY_NAMES.get(code, "code %d" % code),
                            sec + usec / 1e6 - down.pop(code, sec + usec / 1e6)))
                        break
                self.note("button %s -> %s" % (button, ", ".join(seen) or "no event"))
        finally:
            os.close(fd)

    def fan_sweep(self, hwmon, label):
        pwms = numbered(hwmon, "pwm[0-9]")
        fans = numbered(hwmon, "fan*_input")
        if not pwms:
            return
        for pwm in pwms:
            self.pwms.append((pwm, read(pwm)))
            for other in pwms:
                write(other, 255)
            time.sleep(SWEEP_HOLD)
            self.note("%s %s sweep (all other PWMs at 255):" % (label, os.path.basename(pwm)))
            for step in SWEEP_STEPS:
                write(pwm, step)
                time.sleep(SWEEP_HOLD)
                over = hottest_over_limit()
                rpms = ", ".join("%s=%s" % (os.path.basename(f)[:-6], read(f)) for f in fans)
                self.note("  pwm %3d (reads %s): %s" % (step, read(pwm), rpms))
                if over:
                    self.note("  ABORT: %s" % over)
                    break
                if any(read(f) == "0" for f in fans):
                    break  # Stall point found; do not go lower.
            write(pwm, 255)
            time.sleep(SWEEP_HOLD)
            restarted = ", ".join("%s=%s" % (os.path.basename(f)[:-6], read(f)) for f in fans)
            self.note("  back to 255: %s" % restarted)
            if any(read(f) == "0" for f in fans):
                self.note("  WARNING: a fan did not restart at 255")

    def fans(self):
        for name, label in ((DRIVER, "chassis"), ("qm2", "QM2")):
            for h in hwmons().get(name, []):
                self.fan_sweep(h, label)

    def disk_activity(self):
        bays = [d for d in disks() if d["attached"].startswith("sata port")]
        if not bays:
            return
        print("\nqnapd is running again. Each disk is read for 5 s; watch "
              "which bay LED blinks. This wakes a sleeping disk.")
        for d in bays:
            if not yes("Read %s (%s, %s GB, %s)?" % (d["device"], d["model"],
                                                     d["size_gb"], d["attached"])):
                continue
            run(["timeout", "5", "dd", "if=/dev/" + d["device"], "of=/dev/null",
                 "bs=1M", "iflag=direct"])
            answer = ask("Which bay blinked? n = none:")
            self.note("activity %s (%s) -> bay %s" % (d["device"], d["attached"], answer or "?"))

    def beep(self):
        dev = speaker()
        if not dev:
            self.note("beep: no pcspkr input device")
            return
        event = lambda hz: struct.pack("llHHi", 0, 0, EV_SND, SND_TONE, hz)
        with open(dev, "wb", buffering=0) as f:
            f.write(event(1000))
            time.sleep(0.2)
            f.write(event(0))
        self.note("beep via %s -> heard: %s" % (
            os.path.basename(dev), "yes" if yes("Did the NAS beep?") else "no"))

    def run_all(self):
        print("Interactive checks. Stand at the NAS; each step asks first.")
        if not yes("Stop qnapd for the LED, button and fan checks? "
                   "(fans go to full speed)"):
            return "## Interactive checks\n\nSkipped.\n"
        try:
            self.stop_qnapd()
            if yes("LED mapping: light each LED for 5 s?"):
                self.led_mapping()
            if yes("Buttons: press each one when asked?"):
                self.buttons()
            if yes("Fan sweep: step each fan down until it stops, %d s per "
                   "step, aborting if anything gets hot. Fans get quiet, may "
                   "stop briefly, then return to full speed. Run it?" % SWEEP_HOLD):
                self.fans()
        finally:
            self.restore()
        if self.qnapd_was_active:
            time.sleep(10)
            state = run(["systemctl", "is-active", "qnapd"]).strip()
            self.note("qnapd after restart: %s" % state)
            if state == "active" and yes("Disk-to-bay activity check?"):
                self.disk_activity()
        if yes("Buzzer: one short beep (0.2 s)?"):
            self.beep()
        notes = ask("\nAnything else you noticed (fan noise, odd LEDs)? One line:")
        if notes:
            self.note("notes: " + notes)
        return "## Interactive checks\n\n```\n%s\n```\n" % "\n".join(self.results)


def main():
    parser = argparse.ArgumentParser(description="Report how openmediavault-qnap "
                                     "sees this NAS (docs/testing/model-testing.md).")
    parser.add_argument("--interactive", action="store_true",
                        help="also run the checks that need a person at the NAS")
    parser.add_argument("-o", "--output", default="qnap-model-report.md",
                        help="file to write (default: %(default)s)")
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("Run as root (sudo), or LEDs, buttons and the kernel log "
              "cannot be read.", file=sys.stderr)
        return 1
    text = "# Model test report\n\n" + report()
    if args.interactive:
        text += "\n" + Checks().run_all()
    text = redact(text, secrets())
    with open(args.output, "w") as f:
        f.write(text)
    print("\nWrote %s. Read it through, then paste it into a 'Model test "
          "report' issue." % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
