"""Unit tests for qnapd against a fake sysfs tree.

Run with: python3 -m unittest discover -s tests -v
"""

import glob
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
QNAPD = os.path.join(HERE, os.pardir, "usr", "sbin", "qnapd")

# Do not drop a __pycache__ into usr/sbin (it would end up in the .deb).
sys.dont_write_bytecode = True
_loader = importlib.machinery.SourceFileLoader("qnapd", QNAPD)
_spec = importlib.util.spec_from_loader("qnapd", _loader)
qnapd = importlib.util.module_from_spec(_spec)
_loader.exec_module(qnapd)


def put(root, rel, value):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(value))


def get(root, rel):
    with open(os.path.join(root, rel)) as f:
        return f.read().strip()


class FakeSysfs(unittest.TestCase):
    """Emulates a TS-253D: one fan, one PWM, status LED, coretemp."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        qnapd.SYSFS = self.root
        qnapd.STATUS_FILE = os.path.join(self.root, "run", "status.json")
        qnapd.IDENTITY_FILE = os.path.join(self.root, "identity.json")
        qnapd.KERNEL_LOG_COMMANDS = ()  # Never read the real dmesg.
        qnapd.LOCATE_FILE = os.path.join(self.root, "run", "locate.json")
        qnapd.MOUNTS_FILE = os.path.join(self.root, "mounts")  # None.
        qnapd.INPUT_DIR = os.path.join(self.root, "input")  # No devices.
        ec = "class/hwmon/hwmon3"
        put(self.root, ec + "/name", "qnap8528")
        put(self.root, ec + "/fan1_input", "1300\n")
        put(self.root, ec + "/pwm1", "128\n")
        put(self.root, ec + "/temp1_input", "38000\n")
        put(self.root, ec + "/temp6_input", "31000\n")
        put(self.root, ec + "/temp11_input", "2000\n")  # junk sensor
        cpu = "class/hwmon/hwmon1"
        put(self.root, cpu + "/name", "coretemp")
        put(self.root, cpu + "/temp1_input", "50000")
        put(self.root, cpu + "/temp1_label", "Package id 0")
        put(self.root, cpu + "/temp2_input", "48000")
        put(self.root, cpu + "/temp2_label", "Core 0")
        led = "class/leds/qnap8528::status"
        put(self.root, led + "/brightness", "0")
        put(self.root, led + "/trigger", "none")
        self.ec = ec
        self.led = led

    def tearDown(self):
        shutil.rmtree(self.root)


class TestHardware(FakeSysfs):
    def test_discovery_by_name(self):
        hw = qnapd.Hardware()
        self.assertTrue(hw.present())
        self.assertEqual(hw.fans(), [{"name": "fan1", "rpm": 1300}])
        self.assertEqual(hw.read_pwm(), 128)

    def test_implausible_ec_temps_dropped(self):
        temps = [t for _, _, t in qnapd.Hardware().system_temps()]
        self.assertEqual(temps, [38.0, 31.0])

    def test_cpu_prefers_package(self):
        self.assertEqual(qnapd.Hardware().cpu_temps(),
                         [("cpu", "Package id 0", 50.0)])

    def test_read_strips_nul_padding(self):
        put(self.root, "vpd", "70-0Q05H0201" + "\0" * 21)
        self.assertEqual(qnapd.read(os.path.join(self.root, "vpd")),
                         "70-0Q05H0201")

    def test_junk_rpm(self):
        put(self.root, self.ec + "/fan1_input", "65535")
        self.assertEqual(qnapd.Hardware().fans()[0]["rpm"], None)

    def test_set_pwm_clamps(self):
        qnapd.Hardware().set_pwm(400)
        self.assertEqual(get(self.root, self.ec + "/pwm1"), "255")


class TestCurve(unittest.TestCase):
    def curve(self, **raw):
        raw.setdefault("fanmode", "custom")
        raw.update({"usedisk": False, "usenvme": False})
        return qnapd.FanCurve(qnapd.Settings(raw))

    def test_linear_and_clamped(self):
        c = self.curve(cpulow=40, cpuhigh=80, syslow=30, syshigh=50,
                       minpwm=50, maxpwm=250)
        self.assertEqual(c.target({"cpu": [30], "system": [20]}), 50)
        self.assertEqual(c.target({"cpu": [60], "system": [20]}), 150)
        self.assertEqual(c.target({"cpu": [85], "system": [20]}), 250)

    def test_hottest_source_wins(self):
        c = self.curve(cpulow=40, cpuhigh=80, syslow=30, syshigh=50,
                       minpwm=0, maxpwm=200)
        # cpu at 25% demand, system at 75% demand.
        self.assertEqual(c.target({"cpu": [50], "system": [45]}), 150)

    def test_disabled_source_ignored(self):
        c = self.curve(usesystem=False, cpulow=40, cpuhigh=80,
                       minpwm=0, maxpwm=200)
        self.assertEqual(c.target({"cpu": [40], "system": [99]}), 0)

    def test_critical(self):
        c = self.curve()
        self.assertEqual(c.next_pwm(64, {"cpu": [95], "system": [30]}),
                         (255, "critical cpu temperature"))

    def test_ramp_down_hysteresis_and_rate_limit(self):
        c = self.curve(cpulow=40, cpuhigh=80, syslow=30, syshigh=50,
                       minpwm=0, maxpwm=200, hysteresis=4)
        r = {"cpu": [60], "system": [20]}
        self.assertEqual(c.next_pwm(None, r)[0], 100)
        # Small dip: hysteresis keeps the fan where it is.
        self.assertEqual(c.next_pwm(100, {"cpu": [58], "system": [20]})[0],
                         100)
        # Large drop: limited to PWM_MAX_STEP_DOWN per cycle.
        self.assertEqual(c.next_pwm(100, {"cpu": [40], "system": [20]})[0],
                         100 - qnapd.PWM_MAX_STEP_DOWN)

    def test_other_source_does_not_pin_fan_after_burst(self):
        c = self.curve(cpulow=40, cpuhigh=80, syslow=30, syshigh=40,
                       minpwm=0, maxpwm=200, hysteresis=3)
        # A CPU burst raises the fan; the system sensor sits just inside
        # its narrow range the whole time.
        self.assertEqual(c.next_pwm(None, {"cpu": [70], "system": [31]})[0],
                         150)
        # CPU back to idle: the fan steps down although system +3 C would
        # be 80 PWM.
        self.assertEqual(c.next_pwm(150, {"cpu": [40], "system": [31]})[0],
                         150 - qnapd.PWM_MAX_STEP_DOWN)

    def test_preset_overrides_custom_values(self):
        s = qnapd.Settings({"fanmode": "quiet", "cpulow": 1, "minpwm": 0})
        self.assertEqual(s.ranges["cpu"], qnapd.PRESETS["quiet"]["cpu"])
        self.assertEqual(s.pwm_range, qnapd.PRESETS["quiet"]["pwm"])


class TestDaemon(FakeSysfs):
    def daemon(self, **raw):
        raw.update({"usedisk": False, "usenvme": False})
        return qnapd.Daemon(qnapd.Settings(raw))

    def test_step_writes_pwm_status_and_led(self):
        d = self.daemon(fanmode="normal")
        status = d.step(now=0)
        self.assertEqual(int(get(self.root, self.ec + "/pwm1")), status["pwm"])
        self.assertEqual(get(self.root, self.led + "/brightness"), "1")
        with open(qnapd.STATUS_FILE) as f:
            self.assertEqual(json.load(f)["pwm"], status["pwm"])
        types = {r["type"] for r in status["rows"]}
        self.assertEqual(types, {"fan", "pwm", "temperature", "storage"})
        self.assertEqual(status["storage"], {"state": "ok", "reasons": []})

    def test_manual_mode(self):
        d = self.daemon(fanmode="manual", manualpwm=90)
        self.assertEqual(d.step(now=0)["pwm"], 90)

    def test_cpu_burst_is_smoothed(self):
        d = self.daemon(fanmode="normal", usesystem=False)
        d.step(now=0)  # CPU 50
        put(self.root, "class/hwmon/hwmon1/temp1_input", "70000")
        # Average of 50 and 70 is 60: (60-55)/(85-55) of 64..255 -> 96,
        # where the raw 70 would give 160.
        self.assertEqual(d.step(now=10)["pwm"], 96)

    def test_cpu_spikes_ignored_sustained_load_not(self):
        d = self.daemon(fanmode="normal", usesystem=False)
        cpu = "class/hwmon/hwmon1/temp1_input"
        for i, t in enumerate((50, 50, 50, 75, 50)):
            put(self.root, cpu, t * 1000)
            status = d.step(now=i * 10)
        self.assertEqual(status["pwm"], 64)  # a single spike is ignored
        for i in range(5, 10):
            put(self.root, cpu, "75000")
            status = d.step(now=i * 10)
        # Sustained 75 C: (75-55)/(85-55) of 64..255 -> 191.
        self.assertEqual(status["pwm"], 191)

    def test_cpu_critical_uses_raw_reading(self):
        d = self.daemon(fanmode="normal", usesystem=False)
        d.step(now=0)
        put(self.root, "class/hwmon/hwmon1/temp1_input", "95000")
        status = d.step(now=10)
        self.assertEqual(status["pwm"], 255)
        self.assertEqual(status["reason"], "critical cpu temperature")

    def test_manual_pwm_never_below_floor(self):
        d = self.daemon(fanmode="manual", manualpwm=10)
        self.assertEqual(d.step(now=0)["pwm"], qnapd.MIN_PWM_CHASSIS)

    def test_no_sensors_failsafe(self):
        d = self.daemon(usecpu=False, usesystem=False)
        status = d.step(now=0)
        self.assertEqual(status["pwm"], 255)
        self.assertIn("no temperature sensors", status["faults"])

    def test_fan_failure_turns_led_red(self):
        put(self.root, self.ec + "/fan1_input", "0")
        d = self.daemon(fanmode="performance")
        for i in range(qnapd.FAN_FAULT_CYCLES):
            status = d.step(now=i)
        self.assertIn("fan1 not spinning", status["faults"])
        self.assertEqual(get(self.root, self.led + "/brightness"), "2")

    def test_led_without_timer_trigger_stays_solid(self):
        real_write = qnapd.write

        def write(path, value):
            if value == "timer":
                raise OSError(22, "Invalid argument")
            real_write(path, value)

        qnapd.write = write
        try:
            led = qnapd.StatusLed()
            led.set("warning")
        finally:
            qnapd.write = real_write
        self.assertEqual(get(self.root, self.led + "/brightness"), "2")
        self.assertEqual(led.state, "warning")

    def test_failsafe(self):
        qnapd.failsafe("exit-code")
        self.assertEqual(get(self.root, self.ec + "/pwm1"), "255")
        self.assertEqual(get(self.root, self.led + "/trigger"), "timer")

    def test_run_without_driver(self):
        os.remove(os.path.join(self.root, self.ec, "name"))
        self.assertEqual(self.daemon().run(), 1)


def link(root, rel, target):
    """Create root/rel as a symlink to root/target (a directory)."""
    os.makedirs(os.path.join(root, target), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
    os.symlink(os.path.join(root, target), os.path.join(root, rel))


class FakeQm2(FakeSysfs):
    """TS-253D plus a QM2-2P10G1TB with one NVMe SSD; a second NVMe SSD
    sits elsewhere on the PCI bus."""

    SWITCH = "devices/pci0000:00/0000:00:13.0/0000:01:00.0"

    def setUp(self):
        super().setUp()
        card = "devices/platform/qm2.0"
        put(self.root, card + "/model", "QM2-2P10G1TB\n")
        put(self.root, card + "/pic_version", "0.10\n")
        self.qm2 = card + "/hwmon/hwmon5"
        put(self.root, self.qm2 + "/name", "qm2")
        put(self.root, self.qm2 + "/temp1_input", "45000")
        put(self.root, self.qm2 + "/temp2_input", "0")  # empty slot
        put(self.root, self.qm2 + "/fan1_input", "1800")
        put(self.root, self.qm2 + "/pwm1", "100")
        link(self.root, self.qm2 + "/device", card)
        link(self.root, "class/hwmon/hwmon5", self.qm2)
        for led in ("qm2-7:red:slot1", "qm2-7:green:slot1"):
            led_dir = card + "/leds/" + led
            put(self.root, led_dir + "/brightness", "0")
            link(self.root, led_dir + "/device", card)
            link(self.root, "class/leds/" + led, led_dir)
        link(self.root, "bus/i2c/devices/i2c-7", self.SWITCH + "/i2c-7")
        for n, parent, temp in (
                (6, self.SWITCH + "/0000:02:01.0/0000:03:00.0", 50000),
                (7, "devices/pci0000:00/0000:00:17.0", 70000)):
            hwmon = "%s/nvme/nvme%d/hwmon%d" % (parent, n - 6, n)
            put(self.root, hwmon + "/name", "nvme")
            put(self.root, hwmon + "/temp1_input", temp)
            link(self.root, "class/hwmon/hwmon%d" % n, hwmon)


class TestQm2(FakeQm2):
    def daemon(self, **raw):
        raw.setdefault("fanmode", "normal")
        raw["usedisk"] = False
        return qnapd.Daemon(qnapd.Settings(raw))

    def test_discovery(self):
        card, = qnapd.Hardware.qm2_cards()
        self.assertEqual(card.name, "qm2.0")
        self.assertEqual(card.label, "QM2")
        self.assertEqual(card.attr("model"), "QM2-2P10G1TB")
        self.assertEqual([t for _, _, t in card.temps()], [45.0])
        self.assertEqual(card.pci_path(),
                         os.path.realpath(os.path.join(self.root,
                                                       self.SWITCH)))

    def test_card_fan_follows_its_own_sensors(self):
        status = self.daemon().step(now=0)
        # Slot 45 / NVMe-on-card 50 on the normal NVMe curve (45-65,
        # 64-255); the off-card SSD at 70 must not count.
        self.assertEqual(get(self.root, self.qm2 + "/pwm1"), "112")
        self.assertEqual(status["qm2"], {"qm2.0": 112})
        labels = {r["label"] for r in status["rows"]}
        self.assertIn("QM2 fan", labels)
        self.assertIn("QM2 duty", labels)
        self.assertIn("QM2 slot 1", labels)
        # The chassis zone still sees every NVMe SSD (70 >= 65).
        self.assertEqual(status["pwm"], 255)

    def test_card_fan_never_below_its_floor(self):
        status = self.daemon(fanmode="manual", manualpwm=50).step(now=0)
        self.assertEqual(status["pwm"], 50)
        self.assertEqual(status["qm2"], {"qm2.0": qnapd.MIN_PWM_QM2})

    def test_ignored_write_is_rewritten(self):
        d = self.daemon()
        d.step(now=0)
        self.assertEqual(get(self.root, self.qm2 + "/pwm1"), "112")
        # The card silently kept its old (failsafe) speed.
        put(self.root, self.qm2 + "/pwm1", "255")
        d.step(now=10)
        self.assertEqual(get(self.root, self.qm2 + "/pwm1"), "112")

    def test_readback_rounding_tolerated(self):
        d = self.daemon()
        status = d.step(now=0)
        chassis = int(get(self.root, self.ec + "/pwm1"))
        put(self.root, self.ec + "/pwm1", str(chassis - 1))  # percent drift
        d.step(now=10)
        self.assertEqual(get(self.root, self.ec + "/pwm1"), str(chassis - 1))

    def test_card_left_alone_when_disabled(self):
        status = self.daemon(useqm2=False).step(now=0)
        self.assertEqual(get(self.root, self.qm2 + "/pwm1"), "100")
        self.assertEqual(status["qm2"], {"qm2.0": 100})

    def test_card_fan_failure(self):
        put(self.root, self.qm2 + "/fan1_input", "0")
        d = self.daemon()
        for i in range(qnapd.FAN_FAULT_CYCLES):
            status = d.step(now=i)
        self.assertIn("qm2.0-fan1 not spinning", status["faults"])

    def test_failsafe_includes_card(self):
        qnapd.failsafe("signal", qm2=True)
        self.assertEqual(get(self.root, self.qm2 + "/pwm1"), "255")

    def test_clean_stop_hands_card_back(self):
        qnapd.failsafe("success", qm2=True)
        self.assertEqual(get(self.root, self.qm2 + "/pwm1"), "100")
        self.assertEqual(get(self.root, "devices/platform/qm2.0/fan_default"),
                         "1")
        self.assertEqual(get(self.root, self.ec + "/pwm1"), "255")

    def test_disabled_hands_card_back_on_start(self):
        d = self.daemon(useqm2=False)
        d.stop.set()
        d.run()
        self.assertEqual(get(self.root, "devices/platform/qm2.0/fan_default"),
                         "1")

    def test_slot_leds_follow_switch_ports(self):
        ssd = self.SWITCH + "/0000:02:01.0/0000:03:00.0"
        put(self.root, ssd + "/class", "0x010802")
        put(self.root, ssd + "/nvme/nvme0/nvme0n1/stat",
            "10 0 0 0 5 0 0 0 0 0 0")
        link(self.root, "block/nvme0n1", ssd + "/nvme/nvme0/nvme0n1")
        os.makedirs(os.path.join(self.root, self.SWITCH, "0000:02:02.0"))
        card = "devices/platform/qm2.0/leds/"
        for led in ("qm2-7:red:slot2", "qm2-7:green:slot2"):
            put(self.root, card + led + "/brightness", "0")
            link(self.root, card + led + "/device", "devices/platform/qm2.0")
            link(self.root, "class/leds/" + led, card + led)
        for led in ("qm2-7:red:slot1", "qm2-7:green:slot1"):
            put(self.root, card + led + "/trigger", "none")
        leds = qnapd.DiskLeds()
        self.assertEqual([(dev, slot) for kind, _, dev, slot in leds.slots
                          if kind == "qm2"],
                         [("nvme0n1", "qm2.0-slot1"), (None, "qm2.0-slot2")])
        green = card + "qm2-7:green:slot1/"
        red = card + "qm2-7:red:slot1/"
        leds.poll(now=0)
        self.assertEqual((get(self.root, green + "brightness"),
                          get(self.root, red + "brightness"),
                          get(self.root, card + "qm2-7:green:slot2/brightness")),
                         ("1", "0", "0"))
        put(self.root, ssd + "/nvme/nvme0/nvme0n1/stat",
            "12 0 0 0 5 0 0 0 0 0 0")
        leds.poll(now=0.25)
        self.assertEqual(get(self.root, green + "trigger"), "timer")
        leds.update({"nvme0n1"})
        leds.poll(now=3)
        self.assertEqual((get(self.root, green + "brightness"),
                          get(self.root, red + "brightness")), ("0", "1"))
        # Locate: red 1 blinked by the timer (red 2, PIC blink, stays dark).
        put(self.root, "run/locate.json",
            json.dumps({"qm2.0-slot1": qnapd.time.time() + 600}))
        leds.poll(now=4)
        self.assertEqual((get(self.root, green + "brightness"),
                          get(self.root, red + "brightness"),
                          get(self.root, red + "trigger")), ("0", "1", "timer"))

    def test_swapped_generic_card(self):
        card, = qnapd.Hardware.qm2_cards()
        ssd = self.SWITCH + "/0000:02:01.0/0000:03:00.0"
        put(self.root, ssd + "/class", "0x010802")
        put(self.root, ssd + "/nvme/nvme0/nvme0n1/stat", "0")
        link(self.root, "block/nvme0n1", ssd + "/nvme/nvme0/nvme0n1")
        os.makedirs(os.path.join(self.root, self.SWITCH, "0000:02:02.0"))
        self.assertEqual(qnapd.qm2_slot_disks(card, swapped=True),
                         [None, "nvme0n1"])

    def test_failsafe_skips_card_when_disabled(self):
        qnapd.failsafe("signal", qm2=False)
        self.assertEqual(get(self.root, self.qm2 + "/pwm1"), "100")


class TestCollectd(FakeQm2):
    def test_values_from_status(self):
        d = qnapd.Daemon(qnapd.Settings({"usedisk": False}))
        values = dict(qnapd.collectd_values(d.step(now=0)))
        self.assertEqual(values["temperature-cpu"], 50.0)
        self.assertEqual(values["temperature-system"], 38.0)
        self.assertEqual(values["temperature-nvme"], 70.0)
        self.assertEqual(values["temperature-qm2"], 45.0)
        self.assertEqual(values["fanspeed-fan1"], 1300)
        self.assertEqual(values["fanspeed-qm2_0_fan1"], 1800)
        self.assertIn("percent-pwm", values)
        self.assertIn("percent-qm2_0_pwm", values)

    def test_gauges_from_status(self):
        d = qnapd.Daemon(qnapd.Settings({"usedisk": False}))
        g = d.step(now=0)["gauges"]
        self.assertEqual((g["cpu"], g["system"], g["nvme"], g["qm2"]),
                         (50.0, 38.0, 70.0, 45.0))
        self.assertIsNone(g["disk"])  # usedisk off: no disk rows
        self.assertIsInstance(g["fanduty"], int)
        self.assertIsInstance(g["qm2duty"], int)

    def test_stale_status_ignored(self):
        qnapd.write_status({"timestamp": 0, "rows": []})
        self.assertIsNone(qnapd.read_status(60))


class TestDiskLeds(FakeSysfs):
    def setUp(self):
        super().setUp()
        for port, dev in ((1, "sda"), (2, "sdb")):
            disk = "devices/pci0000:00/0000:00:12.0/ata%d/host%d/target%d:0:0/" \
                "%d:0:0:0/block/%s" % (port, port - 1, port - 1, port - 1, dev)
            put(self.root, disk + "/stat", "10 0 0 0 5 0 0 0 0 0 0")
            link(self.root, "block/" + dev, disk)
        for n in (1, 2):
            led = "class/leds/qnap8528::hdd%d" % n
            put(self.root, led + "/brightness", "0")
            put(self.root, led + "/trigger", "none")
        # Bay 2 is empty after all: sdb is on port 3.
        os.remove(os.path.join(self.root, "block/sdb"))
        disk = "devices/pci0000:00/0000:00:12.0/ata3/host2/target2:0:0/" \
            "2:0:0:0/block/sdb"
        put(self.root, disk + "/stat", "1 0 0 0 1 0 0 0 0 0 0")
        link(self.root, "block/sdb", disk)

    def hdd(self, n, attr):
        return get(self.root, "class/leds/qnap8528::hdd%d/%s" % (n, attr))

    def test_bays_follow_sata_ports(self):
        leds = qnapd.DiskLeds()
        self.assertEqual([(dev, slot) for _, _, dev, slot in leds.slots],
                         [("sda", "bay1"), (None, "bay2")])

    def test_locate_blinks_red_then_expires(self):
        leds = qnapd.DiskLeds()
        put(self.root, "run/locate.json",
            json.dumps({"bay2": qnapd.time.time() + 600}))
        leds.poll(now=0)
        self.assertEqual((self.hdd(2, "brightness"), self.hdd(2, "trigger")),
                         ("2", "timer"))
        self.assertEqual([s["locate"] for s in leds.snapshot()], [False, True])
        # Expired requests are ignored: the empty bay goes dark again.
        put(self.root, "run/locate.json",
            json.dumps({"bay2": qnapd.time.time() - 1}))
        os.utime(qnapd.LOCATE_FILE, (1, 1))
        leds.poll(now=1)
        self.assertEqual((self.hdd(2, "brightness"), self.hdd(2, "trigger")),
                         ("0", "none"))

    def test_locate_file_garbage_ignored(self):
        put(self.root, "run/locate.json", "[1, 2")
        self.assertEqual(qnapd.DiskLeds().locating(), {})

    def test_present_activity_error(self):
        leds = qnapd.DiskLeds(bay_activity=True)
        leds.poll(now=0)
        self.assertEqual((self.hdd(1, "brightness"), self.hdd(2, "brightness")),
                         ("1", "0"))
        put(self.root, "devices/pci0000:00/0000:00:12.0/ata1/host0/"
            "target0:0:0/0:0:0:0/block/sda/stat", "11 0 0 0 5 0 0 0 0 0 0")
        leds.poll(now=0.25)
        self.assertEqual(self.hdd(1, "trigger"), "timer")
        leds.poll(now=2)  # Idle for longer than the hold time.
        self.assertEqual((self.hdd(1, "trigger"), self.hdd(1, "brightness")),
                         ("none", "1"))
        leds.update({"sda"})
        leds.poll(now=3)
        self.assertEqual(self.hdd(1, "brightness"), "2")

    def test_usb_disks_not_a_fan_source(self):
        disk = "devices/pci0000:00/0000:00:15.0/usb2/2-1/2-1:1.0/host3/" \
            "target3:0:0/3:0:0:0/block/sdc"
        put(self.root, disk + "/removable", "0")
        link(self.root, "block/sdc", disk)
        self.assertEqual(qnapd.DiskTemps.devices(), ["sda", "sdb"])

    def test_idle_disks_not_queried(self):
        """A S.M.A.R.T. read restarts a drive's standby timer, so awake disks
        without I/O keep their last reading until IDLE_REFRESH_SECONDS."""
        queried = []

        def smartctl(cmd, **kwargs):
            queried.append(os.path.basename(cmd[-1]))
            return unittest.mock.Mock(stdout=json.dumps(
                {"temperature": {"current": 40}, "smart_status": {"passed": True}}))

        disks = qnapd.DiskTemps(60)
        with unittest.mock.patch.object(qnapd.subprocess, "run", smartctl):
            self.assertEqual(disks.get(0), [("sda", "sda", 40.0), ("sdb", "sdb", 40.0)])
            put(self.root, "devices/pci0000:00/0000:00:12.0/ata1/host0/"
                "target0:0:0/0:0:0:0/block/sda/stat", "12 0 0 0 5 0 0 0 0 0 0")
            self.assertEqual(disks.get(60), [("sda", "sda", 40.0), ("sdb", "sdb", 40.0)])
            disks.get(120)  # No I/O since: nothing queried.
            disks.get(60 + qnapd.DiskTemps.IDLE_REFRESH_SECONDS)
        # sda again after its I/O, then both on the slow refresh.
        self.assertEqual(queried, ["sda", "sdb", "sda", "sda", "sdb"])

    def test_standby_disk_reading_dropped(self):
        disks = qnapd.DiskTemps(60)
        replies = iter([{"temperature": {"current": 40}}, {}])
        with unittest.mock.patch.object(
                qnapd.subprocess, "run", lambda cmd, **kw: unittest.mock.Mock(
                    stdout=json.dumps(next(replies) if cmd[-1].endswith("sda") else {}))):
            self.assertEqual(disks.get(0), [("sda", "sda", 40.0)])
            # Idle past the refresh time and now in standby: no stale reading.
            self.assertEqual(disks.get(qnapd.DiskTemps.IDLE_REFRESH_SECONDS), [])

    def test_disk_waking_without_io_read_again(self):
        """A disk asleep at its last query is asked again next poll even
        without I/O; it may have woken through ATA pass-through commands."""
        replies = iter([(2, {}), (0, {"temperature": {"current": 40}})])

        def smartctl(cmd, **kwargs):
            code, data = next(replies) if cmd[-1].endswith("sda") else (2, {})
            return unittest.mock.Mock(returncode=code, stdout=json.dumps(data))

        disks = qnapd.DiskTemps(60)
        with unittest.mock.patch.object(qnapd.subprocess, "run", smartctl):
            self.assertEqual(disks.get(0), [])
            self.assertEqual(disks.get(60), [("sda", "sda", 40.0)])

    def test_no_software_blink_on_unverified_models(self):
        """Bays without EC hardware blink would make the kernel blink them
        in software through the EC; stay solid green instead."""
        leds = qnapd.DiskLeds()  # bay_activity off by default.
        leds.poll(now=0)
        put(self.root, "devices/pci0000:00/0000:00:12.0/ata1/host0/"
            "target0:0:0/0:0:0:0/block/sda/stat", "11 0 0 0 5 0 0 0 0 0 0")
        leds.poll(now=0.25)
        self.assertEqual((self.hdd(1, "brightness"), self.hdd(1, "trigger")),
                         ("1", "none"))
        put(self.root, "run/locate.json",
            json.dumps({"bay1": qnapd.time.time() + 600}))
        leds.poll(now=0.5)  # Locate blinks in hardware on every model.
        self.assertEqual(self.hdd(1, "trigger"), "timer")

    def test_failsafe_stops_blinking(self):
        put(self.root, "class/leds/qnap8528::hdd1/trigger", "[timer]")
        qnapd.failsafe("signal", qm2=False)
        self.assertEqual(self.hdd(1, "trigger"), "none")


class TestDiskHealth(unittest.TestCase):
    ZPOOL = """  pool: backup-store
 state: DEGRADED
config:

\tNAME           STATE     READ WRITE CKSUM
\tbackup-store   DEGRADED     0     0     0
\t  mirror-0     DEGRADED     0     0     0
\t    /dev/sda1  FAULTED      3     0     0
\t    /dev/sdb1  ONLINE       0     0     2
\t    /dev/sdc1  ONLINE       0     0     0
\t    /dev/nvme0n1p1  UNAVAIL  0     0     0
"""

    def test_zfs_faulted(self):
        self.assertEqual(qnapd.zfs_faulted(self.ZPOOL),
                         {"sda", "sdb", "nvme0n1"})

    def test_md_faulty(self):
        self.assertEqual(qnapd.md_faulty(
            "md0 : active raid1 sdb1[1](F) sda1[0]\n"), {"sdb"})

    def test_parse_smart(self):
        self.assertEqual(qnapd.parse_smart(
            {"temperature": {"current": 33}, "smart_status": {"passed": True}}),
            (33.0, True))
        # Standby: smartctl returns no data, health unknown.
        self.assertEqual(qnapd.parse_smart({"power_mode": {}}), (None, None))


class TestStorageHealth(FakeSysfs):
    ZLIST = "app-store\tONLINE\t12%\nbackup-store\tDEGRADED\t40%\n"
    ZSTATUS = """  pool: app-store
 state: ONLINE
  scan: scrub in progress since Sun Oct 18 00:24:01 2026
  pool: backup-store
 state: DEGRADED
  scan: resilver in progress since Sun Oct 18 01:00:00 2026
"""

    def test_zfs_resilver_counts_scrub_does_not(self):
        self.assertEqual(qnapd.zfs_pools(self.ZLIST, self.ZSTATUS), {
            "app-store": ("ONLINE", 12, False),
            "backup-store": ("DEGRADED", 40, True)})

    def test_md_arrays(self):
        self.assertEqual(qnapd.md_arrays(
            "Personalities : [raid1]\n"
            "md0 : active raid1 sdb1[1] sda1[0]\n"
            "      976630464 blocks super 1.2 [2/1] [U_]\n"
            "md1 : active raid1 sdd1[1] sdc1[0]\n"
            "      976630464 blocks super 1.2 [2/1] [U_]\n"
            "      [==>..................]  recovery = 12.6% (123/976)\n"
            "md2 : active raid1 sdf1[1] sde1[0]\n"
            "      976630464 blocks super 1.2 [2/2] [UU]\n"
            "      [==>..................]  check = 12.6% (123/976)\n"),
            {"md0": (True, False), "md1": (True, True), "md2": (False, False)})

    def test_state_priority(self):
        ok = {"p": ("ONLINE", 10, False)}
        self.assertEqual(qnapd.storage_state(ok, {}, {}, 95), ("ok", []))
        self.assertEqual(qnapd.storage_state(
            {"p": ("DEGRADED", 10, True)}, {}, {}, 95),
            ("rebuilding", ["p resilvering"]))
        self.assertEqual(qnapd.storage_state(
            {"p": ("DEGRADED", 10, False)}, {"md0": (False, True)}, {}, 95),
            ("degraded", ["p DEGRADED", "md0 rebuilding"]))
        self.assertEqual(qnapd.storage_state(
            ok, {"md0": (True, False)}, {"/srv/data": 97}, 95),
            ("fault", ["/srv/data 97% full", "md0 degraded"]))
        self.assertEqual(qnapd.storage_state(
            {"p": ("FAULTED", 96, False)}, {}, {}, 95),
            ("fault", ["p FAULTED", "p 96% full"]))

    def test_volume_usage_local_block_filesystems_once(self):
        usage = qnapd.volume_usage(
            "/dev/sda1 / ext4 rw 0 0\n"
            "/dev/sda1 /export/x ext4 rw 0 0\n"
            "tmpfs /run tmpfs rw 0 0\n"
            "app-store /app-store zfs rw 0 0\n")
        self.assertEqual(list(usage), ["/"])
        self.assertTrue(0 <= usage["/"] <= 100)

    def test_led_state(self):
        self.assertEqual(qnapd.status_led_state(["fan1 stalled"], "ok"), "fault")
        self.assertEqual(qnapd.status_led_state([], "fault"), "fault")
        self.assertEqual(qnapd.status_led_state([], "degraded"), "warning")
        self.assertEqual(qnapd.status_led_state([], "rebuilding"),
                         "rebuilding")
        self.assertEqual(qnapd.status_led_state([], "ok"), "ok")

    def test_rebuilding_uses_bicolour_blink(self):
        led = qnapd.StatusLed()
        led.set("rebuilding")
        self.assertEqual(get(self.root, self.led + "/blink_bicolor"), "1")
        self.assertEqual(get(self.root, self.led + "/trigger"), "none")

    def test_rebuilding_falls_back_to_red_blink(self):
        os.makedirs(os.path.join(self.root, self.led, "blink_bicolor"))
        qnapd.StatusLed().set("rebuilding")
        self.assertEqual((get(self.root, self.led + "/brightness"),
                          get(self.root, self.led + "/trigger")), ("2", "timer"))

    def test_volumefull_setting(self):
        self.assertEqual(qnapd.Settings({}).volumefull, 95)
        self.assertEqual(qnapd.Settings({"volumefull": 20}).volumefull, 50)


class TestNightBrightness(FakeSysfs):
    def settings(self, **raw):
        raw.setdefault("lednight", True)
        return qnapd.Settings(dict(ledbrightness=80, lednightbrightness=5,
                                   **raw))

    def test_hhmm(self):
        self.assertEqual(qnapd.hhmm("22:30", "00:00"), 22 * 60 + 30)
        self.assertEqual(qnapd.hhmm("7:05", "00:00"), 7 * 60 + 5)
        self.assertEqual(qnapd.hhmm("25:00", "07:00"), 7 * 60)
        self.assertEqual(qnapd.hhmm(None, "07:00"), 7 * 60)

    def test_window_across_midnight(self):
        s = self.settings()  # 22:00-07:00 by default.
        at = lambda h, m=0: qnapd.panel_brightness(s, h * 60 + m)
        self.assertEqual([at(21, 59), at(22), at(3), at(6, 59), at(7), at(12)],
                         [80, 5, 5, 5, 80, 80])

    def test_window_within_a_day_and_off(self):
        s = self.settings(lednightstart="01:00", lednightend="05:00")
        self.assertEqual([qnapd.panel_brightness(s, m) for m in (0, 60, 299, 300)],
                         [80, 5, 5, 80])
        off = self.settings(lednight=False)
        self.assertEqual(qnapd.panel_brightness(off, 23 * 60), 80)
        same = self.settings(lednightstart="22:00", lednightend="22:00")
        self.assertEqual(qnapd.panel_brightness(same, 23 * 60), 80)

    def test_daemon_writes_brightness_on_change_only(self):
        led = "class/leds/qnap8528::panel_brightness"
        put(self.root, led + "/brightness", "100")
        d = qnapd.Daemon(qnapd.Settings({"enable": True, "ledbrightness": 60}))
        d.step(now=0)
        self.assertEqual(get(self.root, led + "/brightness"), "60")
        put(self.root, led + "/brightness", "33")  # Someone else wrote it.
        d.step(now=10)
        self.assertEqual(get(self.root, led + "/brightness"), "33")


class TestNotifications(FakeSysfs):
    def setUp(self):
        super().setUp()
        self.sent = []
        patcher = unittest.mock.patch.object(
            qnapd, "send_mail", lambda subject, body: self.sent.append(subject))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_hold_then_one_mail_then_cleared(self):
        n = qnapd.Notifier(True)
        n.update({"fan1 stalled"}, now=0)
        n.update({"fan1 stalled"}, now=30)
        self.assertEqual(self.sent, [])  # Not for a 30 s glitch.
        n.update({"fan1 stalled"}, now=60)
        n.update({"fan1 stalled"}, now=120)  # No repeat.
        n.update(set(), now=130)
        self.assertEqual(len(self.sent), 2)
        self.assertIn("fan1 stalled", self.sent[0])
        self.assertIn("back to normal", self.sent[1])

    def test_glitch_that_clears_sends_nothing(self):
        n = qnapd.Notifier(True)
        n.update({"backup-store DEGRADED"}, now=0)
        n.update(set(), now=30)
        n.update(set(), now=200)
        self.assertEqual(self.sent, [])

    def test_disabled(self):
        n = qnapd.Notifier(False)
        self.assertEqual(n.update({"x"}, now=0), (set(), set()))
        self.assertEqual(n.update({"x"}, now=60), ({"x"}, set()))
        self.assertEqual(self.sent, [])

    def test_problems(self):
        self.assertEqual(qnapd.hardware_problems(
            ["fan1 stalled"], "critical cpu temperature", {"sdb"},
            ("degraded", ["backup-store DEGRADED"])),
            {"fan1 stalled", "critical cpu temperature", "disk sdb failed",
             "backup-store DEGRADED"})
        self.assertEqual(qnapd.hardware_problems([], "curve", set(),
                                                 ("ok", [])), set())

    def test_failsafe_mails_on_crash_only(self):
        self.addCleanup(setattr, qnapd, "CONFIG_FILE", qnapd.CONFIG_FILE)
        qnapd.CONFIG_FILE = os.path.join(self.root, "qnapd.json")
        put(self.root, "qnapd.json", json.dumps({"notify": True}))
        qnapd.failsafe("success", qm2=False)
        self.assertEqual(self.sent, [])
        qnapd.failsafe("signal", qm2=False)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("stopped unexpectedly", self.sent[0])


class FakeBeeper:
    def __init__(self):
        self.beeps = []

    def beep(self, event, wait=False):
        self.beeps.append(event)


TASK = "/var/lib/openmediavault/cron.d/" \
    "userdefined-32664b22-5a9d-11ec-8834-6f00f75b23ee"


class TestButtons(FakeSysfs):
    def setUp(self):
        super().setUp()
        self.ran = []
        self.result = True
        self.real_run_task = qnapd.run_task
        patcher = unittest.mock.patch.object(
            qnapd, "run_task",
            lambda task: self.ran.append(task["script"]) or self.result)
        patcher.start()
        self.addCleanup(patcher.stop)
        led = "class/leds/qnap8528::usb"
        put(self.root, led + "/brightness", "0")
        put(self.root, led + "/trigger", "none")
        self.usb = led
        self.beeper = FakeBeeper()

    def buttons(self, **raw):
        b = qnapd.Buttons(qnapd.Settings(raw), self.beeper)
        b.DONE_SECONDS = 0
        return b

    def press(self, b, code, held, start=100.0):
        b.handle(code, 1, start)
        action = b.handle(code, 0, start + held)
        for t in threading.enumerate():
            if t.name in ("usbcopy", "reset"):
                t.join(2)
        return action

    def test_usb_copy_runs_its_task(self):
        b = self.buttons(usbcopy={"script": TASK, "user": "root"})
        self.assertEqual(self.press(b, qnapd.BTN_USBCOPY, 0.2), "usbcopy")
        self.assertEqual(self.ran, [TASK])
        self.assertEqual(get(self.root, self.usb + "/brightness"), "0")
        self.assertEqual(self.beeper.beeps, [])

    def test_usb_copy_failure_beeps_three_short(self):
        self.result = False
        b = self.buttons(usbcopy={"script": TASK})
        self.press(b, qnapd.BTN_USBCOPY, 0.2)
        self.assertEqual(self.beeper.beeps, ["usbcopy-failed"])

    def test_no_task_does_nothing(self):
        b = self.buttons()
        self.assertIsNone(self.press(b, qnapd.BTN_USBCOPY, 0.2))
        self.assertIsNone(self.press(b, qnapd.BTN_RESET, 5))
        self.assertEqual(self.ran, [])

    def test_reset_needs_a_three_second_hold(self):
        b = self.buttons(reset={"script": TASK})
        self.assertIsNone(self.press(b, qnapd.BTN_RESET, 1))
        self.assertIsNone(self.press(b, qnapd.BTN_RESET, 12))  # reserved
        self.assertEqual(self.ran, [])
        self.assertEqual(self.press(b, qnapd.BTN_RESET, 4), "reset")
        self.assertEqual(self.ran, [TASK])
        self.assertEqual(self.beeper.beeps, ["reset"])

    def test_chassis_open_mails(self):
        sent = []
        with unittest.mock.patch.object(
                qnapd, "send_mail", lambda s, b: sent.append(s)):
            b = self.buttons(notify=True)
            self.assertEqual(b.handle(qnapd.BTN_CHASSIS, 1, 0), "chassis")
        self.assertIn("chassis opened", sent[0])

    def test_task_settings_validated(self):
        s = qnapd.Settings({"usbcopy": {"script": TASK, "user": "nas"},
                            "reset": "rm -rf /"})
        self.assertEqual(s.usbcopy, {"script": TASK, "user": "nas"})
        self.assertIsNone(s.reset)
        self.assertFalse(s.beep)

    def test_run_task_rejects_other_paths(self):
        self.assertFalse(self.real_run_task({"script": "/bin/true"}))
        self.assertFalse(self.real_run_task({"script": TASK + "/../x"}))


class TestBeeps(FakeSysfs):
    def test_beeper_writes_pattern_to_pcspkr(self):
        device = os.path.join(self.root, "input",
                              "platform-pcspkr-event-spkr")
        put(self.root, "input/platform-pcspkr-event-spkr", "")
        b = qnapd.Beeper(True)
        b.SHORT = b.LONG = b.GAP = 0
        b.beep("usbcopy-failed", wait=True)
        with open(device, "rb") as f:
            data = f.read()
        events = [qnapd.INPUT_EVENT.unpack_from(data, i)[2:]
                  for i in range(0, len(data), qnapd.INPUT_EVENT.size)]
        self.assertEqual(events, [(qnapd.EV_SND, qnapd.SND_TONE, 1000),
                                  (qnapd.EV_SND, qnapd.SND_TONE, 0)] * 3)

    def test_beeper_off_or_missing_is_silent(self):
        qnapd.Beeper(False).beep("startup", wait=True)
        qnapd.Beeper(True).beep("startup", wait=True)  # no pcspkr device

    def test_fan_alarm_repeats_every_five_minutes(self):
        d = qnapd.Daemon(qnapd.Settings({"beep": True}))
        d.beeper = FakeBeeper()
        for now in (0, 10, 290, 300, 310):
            d.alarms(["fan1 not spinning"], "ok", now)
        self.assertEqual(d.beeper.beeps, ["fan-failure"] * 2)
        d.alarms([], "ok", 320)
        d.alarms(["fan1 not spinning"], "ok", 330)
        self.assertEqual(len(d.beeper.beeps), 3)

    def test_storage_beeps_on_change_not_at_start(self):
        d = qnapd.Daemon(qnapd.Settings({"beep": True}))
        d.beeper = FakeBeeper()
        d.alarms([], "degraded", 0)  # already degraded when qnapd starts
        d.alarms([], "degraded", 10)
        self.assertEqual(d.beeper.beeps, [])
        d.alarms([], "rebuilding", 20)
        d.alarms([], "ok", 30)
        d.alarms([], "fault", 40)
        self.assertEqual(d.beeper.beeps, ["storage", "storage"])


class TestHeaders(unittest.TestCase):
    def test_proxmox_kernel(self):
        self.assertEqual(qnapd.header_packages("7.0.14-24-pve"),
                         ["proxmox-headers-7.0.14-24-pve",
                          "proxmox-headers-7.0"])

    def test_debian_kernels(self):
        self.assertEqual(qnapd.header_packages("6.12.48+deb13-amd64"),
                         ["linux-headers-6.12.48+deb13-amd64",
                          "linux-headers-amd64"])
        self.assertEqual(qnapd.header_packages("6.1.0-18-cloud-amd64")[1],
                         "linux-headers-cloud-amd64")


class TestPackaging(unittest.TestCase):
    """omv-confdbadm migrate parses versions with packaging.version."""

    def test_form_defaults_match_datamodel(self):
        omv = os.path.join(HERE, os.pardir, "usr", "share", "openmediavault")
        with open(os.path.join(omv, "datamodels",
                               "conf.service.qnap.json")) as f:
            defaults = {k: v["default"] for k, v in
                        json.load(f)["properties"].items()}
        checked = 0
        pattern = os.path.join(omv, "workbench", "component.d",
                               "omv-system-qnap-*-form-page.yaml")
        for page in glob.glob(pattern):
            name = None
            for line in open(page):
                line = line.strip()
                if line.startswith("- type:"):
                    name = None
                elif line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("value:") and name in defaults:
                    value = line.split(":", 1)[1].strip().strip('"')
                    expected = defaults[name]
                    if isinstance(expected, bool):
                        expected = "true" if expected else "false"
                    self.assertEqual(value, str(expected),
                                     "%s in %s" % (name, page))
                    checked += 1
        self.assertGreater(checked, 20)

    PEP440ISH = re.compile(r"^\d+(\.\d+)*$")

    def test_changelog_version(self):
        with open(os.path.join(HERE, os.pardir, "debian", "changelog")) as f:
            version = re.match(r"\S+ \(([^)]+)\)", f.readline()).group(1)
        self.assertRegex(version, self.PEP440ISH)

    def test_migration_versions(self):
        d = os.path.join(HERE, os.pardir, "usr", "share", "openmediavault",
                         "confdb", "migrations.d")
        for name in os.listdir(d):
            version = name.rsplit("_", 1)[1][:-len(".sh")]
            self.assertRegex(version, self.PEP440ISH, name)


class TestInfo(FakeSysfs):
    def info(self, cmdline):
        import contextlib, io
        put(self.root, "proc/cmdline", cmdline)
        os.environ["QNAPD_CMDLINE"] = os.path.join(self.root, "proc/cmdline")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            qnapd.main(["info", "--json"])
        del os.environ["QNAPD_CMDLINE"]
        return json.loads(out.getvalue())

    def test_reboot_efi_detection(self):
        self.assertTrue(self.info("BOOT_IMAGE=/vmlinuz quiet reboot=efi")
                        ["reboot_efi"])
        self.assertFalse(self.info("BOOT_IMAGE=/vmlinuz quiet")["reboot_efi"])

    def test_leds_listed(self):
        self.assertEqual(self.info("")["leds"], ["status"])

    def test_bundled_driver_packages(self):
        self.addCleanup(setattr, qnapd, "DRIVERS_DIR", qnapd.DRIVERS_DIR)
        qnapd.DRIVERS_DIR = os.path.join(self.root, "drivers")
        put(self.root, "drivers/qnap8528-dkms_1.27-1_all.deb", "")
        installed = {"qnap8528-dkms": "ii 1.24-1"}
        with unittest.mock.patch.object(
                qnapd, "command_output",
                lambda cmd: installed.get(cmd[-1], "")):
            packages = self.info("")["driver_packages"]
        self.assertEqual([(p["package"], p["bundled"], p["installed"])
                          for p in packages],
                         [("qnap8528-dkms", "1.27-1", "1.24-1")])

    def test_headers_for_the_running_kernel(self):
        self.addCleanup(setattr, qnapd, "MODULES_DIR", qnapd.MODULES_DIR)
        qnapd.MODULES_DIR = os.path.join(self.root, "modules")
        self.assertFalse(self.info("")["headers"])
        os.makedirs(os.path.join(qnapd.MODULES_DIR, os.uname().release,
                                 "build"))
        info = self.info("")
        self.assertTrue(info["headers"])
        self.assertEqual(info["kernel"], os.uname().release)
        self.assertEqual(len(info["header_packages"]), 2)

    def test_identity_cached_for_the_boot(self):
        vpd = "devices/platform/qnap8528/vpd/"
        put(self.root, vpd + "enclosure_serial", "Q000X000000")
        put(self.root, vpd + "mainboard_date", "2021-08-13 08:49:00")
        put(self.root, vpd + "mainboard_model", "70-0Q05H0201" + "\0" * 20)
        put(self.root, "class/dmi/id/bios_version", "Q04WAR09\n")
        put(self.root, "kmsg", "[ 7.6] qnap8528 @ qnap8528_find_config: "
            "Model BP code match found, device model is TS-253D\n")
        qnapd.IDENTITY_FILE = os.path.join(self.root, "identity.json")
        qnapd.KERNEL_LOG_COMMANDS = (["cat", os.path.join(self.root,
                                                          "kmsg")],)
        info = self.info("")
        self.assertEqual(info["model"], "TS-253D")
        self.assertEqual(info["serial"], "Q000X000000")
        self.assertEqual(info["manufactured"], "2021-08-13")
        self.assertEqual(info["mainboard_model"], "70-0Q05H0201")
        self.assertEqual(info["bios_version"], "Q04WAR09")
        # Second call comes from the cache, not the (slow) VPD.
        os.remove(os.path.join(self.root, vpd + "enclosure_serial"))
        self.assertEqual(self.info("")["serial"], "Q000X000000")


_loader = importlib.machinery.SourceFileLoader(
    "model_test", os.path.join(HERE, os.pardir, "tools", "model-test.py"))
_spec = importlib.util.spec_from_loader("model_test", _loader)
model_test = importlib.util.module_from_spec(_spec)
_loader.exec_module(model_test)


class TestModelReport(unittest.TestCase):
    """tools/model-test.py: what reaches a public issue."""

    def test_redact(self):
        text = model_test.redact(
            "host cogs, cogs-backup, serial=Q000X000000, Serial Number: ABC1\n"
            "mac 24:5e:be:00:11:22, ip 192.0.2.7, kernel 6.17.2-1-pve, "
            "board QY47A", {"cogs", "QY47-SECRET"})
        self.assertEqual(text,
            "host [redacted], cogs-backup, serial=[redacted], Serial Number: "
            "[redacted]\nmac [mac], ip [ip], kernel 6.17.2-1-pve, board QY47A")

    def test_placeholder_serials_not_secret(self):
        # Seen on a TS-253D: every DMI serial reads "Default string".
        self.assertEqual([v for v in ("Default string", "None", "0000-0000",
                                      "Q000X000000", "S4EUNX0N000000Z")
                          if model_test.is_secret(v)],
                         ["Q000X000000", "S4EUNX0N000000Z"])

    def test_drop_serials(self):
        self.assertEqual(model_test.drop_serials(
            {"model": "TS-253D", "serial": "Q0", "qm2": [{"serial": "x", "pci": "p"}]}),
            {"model": "TS-253D", "qm2": [{"pci": "p"}]})

    def test_disk_attachment(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        model_test.SYS = root
        for dev, path in (
                ("sda", "pci0000:00/0000:00:12.0/ata1/host0/target0:0:0/0:0:0:0"),
                ("sdc", "pci0000:00/0000:00:15.0/usb2/2-1/2-1:1.0/host3/"
                        "target3:0:0/3:0:0:0"),
                ("nvme0n1", "pci0000:00/0000:00:1c.0/0000:01:00.0/0000:02:01.0/"
                            "0000:03:00.0/nvme/nvme0")):
            disk = "devices/%s/block/%s" % (path, dev)
            put(root, disk + "/size", "1953525168")
            link(root, "block/" + dev, disk)
        rows = {d["device"]: d for d in model_test.disks()}
        self.assertEqual({k: v["attached"] for k, v in rows.items()},
                         {"sda": "sata port 1", "sdc": "usb", "nvme0n1": "nvme"})
        self.assertEqual(rows["nvme0n1"]["pci"],
                         "0000:00:1c.0 > 0000:01:00.0 > 0000:02:01.0 > 0000:03:00.0")
        self.assertEqual(rows["sda"]["size_gb"], 1000)


if __name__ == "__main__":
    unittest.main()
