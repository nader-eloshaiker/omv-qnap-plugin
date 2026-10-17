# Testing on other QNAP models

The plugin is developed and verified on one box, the reference TS-253D
([../hardware/ts-253d.md](../hardware/ts-253d.md)). Everything is discovered
from sysfs at runtime, so other qnap8528 models should work, but each one
can differ in fan groups, LED names, bay order, buttons and stall points.
This document is the protocol for collecting that evidence from owners of
other models, and for turning it into documentation and releases.

Supported and tested models are listed in
[../hardware/models.md](../hardware/models.md).

## For testers

You need: the NAS running OMV 8 with qnap8528 installed (the plugin is
optional but makes the report more useful), a root shell, and for part 2
about 15 minutes standing at the NAS.

```sh
wget https://raw.githubusercontent.com/nader-eloshaiker/omv-qnap-plugin/main/tools/model-test.py
less model-test.py                         # it is short; read what it does
sudo python3 model-test.py                 # part 1: read-only report
sudo python3 model-test.py --interactive   # part 1 + part 2: checks at the box
```

Both write `qnap-model-report.md`. Read it through, then open a
[**Model test report**](https://github.com/nader-eloshaiker/omv-qnap-plugin/issues/new?template=model_test.yml)
issue and paste it in.

**Part 1, read-only.** Versions, the drivers and their kernel log lines,
every sensor, fan and PWM, every LED, the button input device, how each
disk is attached (SATA port, USB, NVMe and PCI path) and the PCI tree. It
never runs `smartctl` or reads `drivetemp`, so sleeping disks stay asleep.
Serial numbers, host names, MAC and IP addresses are removed; check anyway
before posting.

**Part 2, at the box.** Each step explains itself and asks first:

| Step | What you see or hear | What it tells us |
|-|-|-|
| Stop qnapd | fans go to full speed | the failsafe works on your model |
| LED mapping | each LED lights for 5 s; you type which bay or slot | LED names → physical bays, extra LEDs |
| Buttons | press each button once when asked | key codes for USB Copy, Reset, others |
| Fan sweep | each fan steps down until it stops (10 s per step), then full speed | PWM groups, which fan each one drives, PWM→RPM, stall point |
| qnapd restarted, disk activity | one disk is read for 5 s; you type which bay blinked (wakes that disk) | SATA port → bay order |

The fan sweep aborts to full speed if the CPU reaches 85 °C, an NVMe SSD
or QM2 sensor 70 °C, or anything else 50 °C. Whatever happens, the script
sets every fan it touched back to full speed and restarts qnapd. Never
press the power button during the button step: it shuts the NAS down.

## For maintainers: from report to release

1. **Triage.** The issue gets the `model-support` label. If qnap8528 does
   not load or does not recognise the model, the problem is upstream:
   point to [qnap8528 issues](https://github.com/0xGiddi/qnap8528/issues).
2. **Read the report against this table.**

   | Finding | Change | Where |
   |-|-|-|
   | Implausible EC temperatures (e.g. a constant 2 °C) | plausibility filter | `qnapd` `Hardware.system_temps`, test |
   | More than one PWM group; which fans each drives | per-group curves (Phase 2 option) or a note | [fan-control.md](../hardware/fan-control.md), PLAN §11 |
   | Stall point above `MIN_PWM_*` | raise the floor or make it per model | [fan-control.md](../hardware/fan-control.md) |
   | Bay LED or activity mapping is not bay N = SATA port N | per-model bay map | `DiskLeds`, [leds.md](../hardware/leds.md) |
   | LEDs we don't drive (e.g. `usb`, `10g`) | Phase 2/3 LED work | [leds.md](../hardware/leds.md) |
   | Different button codes | button table | PLAN §7, Phase 3 |
   | Failsafe did not reach 255 | fix before anything else | `qnapd failsafe`, [fan-control.md](../hardware/fan-control.md) |
   | Disks on unexpected transports (USB, SAS HBA) | fan source / LED rules | `DiskTemps`, `DiskLeds` |

3. **Record it.** Add or update `docs/hardware/<model>.md` (copy the
   sections of [ts-253d.md](../hardware/ts-253d.md) that apply; state that
   the facts come from a tester's report, with the date and the issue
   number) and the row in [models.md](../hardware/models.md). No serial
   numbers or host names.
4. **Change and release.** Code changes go in with unit tests built from
   the report's sysfs facts (the fake sysfs in `tests/test_qnapd.py`). The
   changelog entry names the model. Ask the tester to re-run part 2 on the
   release and close the issue when the report matches.

Pull requests that add support for a model follow the same steps: the
pull request template asks for the report and the documentation updates.
