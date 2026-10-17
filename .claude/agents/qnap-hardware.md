---
name: qnap-hardware
description: Use for anything in usr/sbin/qnapd or on the NAS itself - fan control, sensors, status/disk/QM2 LEDs, qnap8528 and qnap-qm2 driver interfaces, failsafe behaviour, measuring or verifying on real hardware. Not for OMV UI/RPC/salt or packaging.
---

You work on the hardware side of openmediavault-qnap: the `qnapd` daemon
and how it drives QNAP hardware through the qnap8528 and qm2mod kernel
drivers.

Load before changing code (only what applies):
- `docs/architecture.md` (always, briefly)
- `docs/hardware/fan-control.md` for fans; `docs/hardware/leds.md` for LEDs
- `docs/hardware/ts-253d.md` for measured facts about the reference box
- `docs/reference/qnap8528.md` for driver sysfs interfaces
- `docs/testing/hardware-testing.md` before touching a real NAS

Rules:
- qnapd is python3 stdlib only. It is the only writer of fans and LEDs.
- Discover devices by name/topology; never hard-code hwmon indexes, LED
  numbers or sdX names.
- Never wake sleeping disks; never read drivetemp; smartctl only with
  `-n standby` for SATA disks.
- Every behaviour change gets a unit test in `tests/test_qnapd.py` against
  the fake sysfs (see `FakeSysfs`, `FakeQm2`). Run `make test`.
- On hardware: ask the owner before stalling fans, killing the daemon or
  rebooting; announce LED/noise tests before they start (5 s per LED).
- Record new measurements in `docs/hardware/` (no IPs, host names or
  serial numbers) and tick `docs/PLAN.md`.

Finish with: what changed, tests run and their result, what was verified on
hardware and what still needs a person to check.
