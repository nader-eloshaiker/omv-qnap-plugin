# Fan control

Code: `FanCurve`, `Zone`, `Daemon.decide/apply/step`, `failsafe()` in
`usr/sbin/qnapd`. Tests: `TestCurve`, `TestDaemon`, `TestQm2` in
`tests/test_qnapd.py`.

## Zones and sources

| Zone | Fans | Inputs | Floor |
|-|-|-|-|
| chassis | every qnap8528 `pwmN` group | CPU, EC system temps, HDD (S.M.A.R.T.), NVMe | `MIN_PWM_CHASSIS` = 40 |
| one per QM2 card | the card's `pwm1` | its slot sensors + NVMe SSDs behind its PCIe switch | `MIN_PWM_QM2` = 64 |

- CPU: coretemp `Package id 0` (or k10temp `Tctl/Tdie`), **median over 60 s**
  (`CPU_SMOOTH_SECONDS`) for the curve; the raw value for the critical check.
- System: every qnap8528 `tempN_input` within 5–110 °C (junk filtered).
- Disk: `smartctl -n standby -A -H -j` per non-removable `sdX`, every
  `diskinterval` s (default 60); standby disks are skipped. USB disks
  (sysfs path through a `usbN` controller) are left out: they sit outside
  the chassis airflow, so the fans cannot cool them. The reference box's
  USB boot SSD reports itself as non-removable, hence the path check.
- NVMe: each `nvme` hwmon `temp1` (Composite). The chassis zone sees every
  NVMe; a QM2 zone sees only the ones under its switch (by sysfs path).
- QM2 slot sensors use the NVMe range and critical limit.

## Algorithm (every `interval` s, default 10)

1. **Critical** (raw readings): CPU 90, system 55, disk 55, NVMe/QM2 75 °C
   → PWM 255, in every mode.
2. **Manual** mode → `manualpwm`.
3. **No sensors** for an enabled zone → 255 and a fault.
4. **Curve**: per source `demand = clamp((T − low)/(high − low), 0, 1)`;
   `pwm = minpwm + max(demand) × (maxpwm − minpwm)`.
5. **Ramp up immediately**, remembering which source raised the fan and its
   temperature then.
6. **Ramp down** only once *that* source has cooled by `hysteresis` °C,
   then by at most 16 PWM per cycle.
7. **Floor**: never below the zone's floor, whatever the mode.
8. Write PWM when changed, at least every 60 s, and at once if the PWM read
   back differs from the last write by more than 3 (qnap8528 rounds to
   percent).
9. **Fan failure**: 0 RPM at PWM ≥ 64 (or 65535) for 3 cycles → fault →
   status LED red.

## Presets

| Mode | CPU °C | System °C | Disk °C | NVMe/QM2 °C | PWM range |
|-|-|-|-|-|-|
| Quiet | 60→90 | 35→50 | 40→50 | 50→70 | 48–200 |
| Normal | 55→85 | 30→45 | 38→48 | 45→65 | 64–255 |
| Performance | 50→80 | 28→40 | 35→45 | 40→60 | 100–255 |

Custom mode uses the datamodel fields (`cpulow`…`nvmehigh`, `minpwm`,
`maxpwm`, `hysteresis`); defaults match Normal.

## Failsafe

| Event | Chassis | QM2 cards (useqm2 on) | Status LED |
|-|-|-|-|
| Clean stop/restart (`SERVICE_RESULT=success`) | 255 | card's own controller (`fan_default`) | unchanged |
| Crash / kill / failure | 255 | 255 | blinking red |
| Exception in a loop iteration | 255 for that cycle | 255 | — |
| `qnapd failsafe` by hand | 255 | 255 | — |
| `useqm2` off | — | handed to the card at start, never written | — |

The unit has **no start limit** (`StartLimitIntervalSec=0`): every Apply
restarts the daemon, and a limit of 5 starts per 5 minutes left it dead
during testing.

## Lessons (each was a real bug or complaint on hardware)

- **Hysteresis must belong to the source that raised the fan.** Adding the
  hysteresis to *every* source pinned the fan at PWM 140 after a CPU burst:
  +3 °C on the 10 °C disk range is ≈57 PWM, and a disk at 39 °C that never
  caused the increase held it up.
- **Smooth the CPU, and use a median.** Raw J4125 readings spike for single
  samples; the fan sawtoothed between PWM 128 and 217. A 30 s mean still let
  frequent spikes through; a 60 s median fixed it.
- **Every fan needs a floor in every mode**, from its measured restart PWM
  plus margin. Quiet at 40 would have stalled the QM2 fan (stall 48).
- **Do not blast a fan on routine restarts.** Full speed on every Apply was
  audible; QM2 fans now return to the card's controller on clean stops.
- **A loaded UI skews measurements.** Close the OMV dashboard before tuning.
- **Verify writes.** In the kill -9 failsafe test the QM2 PIC ignored the
  first PWM write after the restart (the I2C write reported success) and
  stayed at full speed until the 60 s refresh. The daemon now compares the
  read-back PWM every cycle and rewrites on a mismatch.

Measurements behind these numbers: [ts-253d.md](ts-253d.md).
