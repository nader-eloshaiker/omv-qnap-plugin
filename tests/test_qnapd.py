"""Unit tests for qnapd against a fake sysfs tree.

Run with: python3 -m unittest discover -s tests -v
"""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

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
        self.assertEqual(types, {"fan", "pwm", "temperature"})

    def test_manual_mode(self):
        d = self.daemon(fanmode="manual", manualpwm=90)
        self.assertEqual(d.step(now=0)["pwm"], 90)

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

    def test_failsafe(self):
        qnapd.failsafe("exit-code")
        self.assertEqual(get(self.root, self.ec + "/pwm1"), "255")
        self.assertEqual(get(self.root, self.led + "/trigger"), "timer")

    def test_run_without_driver(self):
        os.remove(os.path.join(self.root, self.ec, "name"))
        self.assertEqual(self.daemon().run(), 1)


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


if __name__ == "__main__":
    unittest.main()
