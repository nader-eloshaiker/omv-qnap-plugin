# Prior art

## Dag-Rui/omv-panq-plugin

<https://github.com/Dag-Rui/omv-panq-plugin> — OMV 6 plugin, tested on TS-453D only.

- `panq` C daemon (fork of guedou/TS-453Be "panq") doing **raw EC port I/O**
  from userspace (`iopl(3)`, ports 0x68/0x6C, chip-ID check 0x85/0x28 —
  which would *fail* on a TS-253D's ENE EC). Ships QNAP's proprietary
  `libuLinux_hal.so` (only used by `panq test`) and prebuilt binaries/.deb.
- Fan curve: `rpm = low + (high-low) * max(ratio_cpu, ratio_sys)` where
  `ratio = (T - low)/(high - low)`; defaults 15 s, 500–1600 "RPM",
  CPU 45–90 °C, system 25–50 °C. The "RPM" is really an open-loop PWM
  (`(rpm+17)/7` → u8 → percent, overflows above ~1768).
- Temps: EC sensor 0 + hard-coded `thermal_zone0` (often not the CPU). No
  disk temps.
- UI: System › Qnap control (settings form, test page), dashboard datatable.
- Settings stored by **rewriting the systemd unit's ExecStart** from
  unvalidated RPC params (injection risk); no datamodel/salt.
- Bugs: no hysteresis, no failsafe, busy loop on errors, dashboard and
  daemon race on EC access, unit never enabled, `Architecture: all` with an
  x86 binary.

**Kept:** max-of-normalised-ratios curve, dashboard widget, check interval,
a manual/test mode. **Fixed:** everything else (see PLAN §2, §5).

## Stonyx/QNAP-EC

<https://github.com/Stonyx/QNAP-EC> v1.1.2 (2022) — hwmon driver that calls
QNAP's `libuLinux_hal.so` through a usermode helper for each read/write.
Fans + temps only, no LEDs/buttons; chip check would need disabling on
ENE ECs; library cannot be redistributed. Superseded by qnap8528 for our
purposes.

## edddeduck/QNAP_Fan_Control (FanControl.sh)

<https://github.com/edddeduck/QNAP_Fan_Control> v1.2 (2016) — QTS-only
script (`getsysinfo`, `hal_app --se_sys_set_fan_mode … mode=0-7`).

- CPU temperature only; 7-step table, 15 s loop, no hysteresis, no
  failsafe; mode resent every pass.
- TS-870 table: CPU 43 45 47 49 51 54 58 °C → fan1 modes 1 2 2 3 4 4 7,
  fan2 2 2 3 4 5 6 7. TS-853A: 30 32 34 38 40 42 44 → 1…7.
- Bugs: `#!/bin/sh` with bash arrays; equality at the first threshold sets
  nothing.

Useful only as evidence that QTS itself uses ~7 discrete speed steps.

## OMV forum thread 57619 ("QNAP Temperatures & Fan Control")

<https://forum.openmediavault.org/index.php?thread/57619-qnap-temperatures-fan-control/>
— single guide post (TS-464, OMV 7.4.17, Nov 2025):

- qnap8528 via DKMS with `skip_hw_check=true`.
- `sensors qnap8528-isa-0000`: fan1 1362 RPM, temp1 38 °C (chassis),
  temp6 31 °C (HDD backplane), temp11/12 2 °C (junk).
- Shell script: max of chassis, CPU, HDD, NVMe temps → PWM via thresholds;
  logs only on change (`qnap-fanctrl` tag), e.g. `HOT=52 → PWM=96`.
  Run by a systemd timer (`OnBootSec=15s`, `OnUnitActiveSec=30s`).
- Temperatures shown in OMV via openmediavault-cputemp with
  `OMV_CPU_TEMP_COMMAND` overrides.
- Hwmon index was `hwmon3` → find by name, never hard-code.

## Others (not explored in depth)

- [Stonyx/PanQ](https://github.com/Stonyx/PanQ) — overhauled panq.
- [Unraid TS-253 + PanQ thread](https://forums.unraid.net/topic/114894-qnap-ts-253-fan-control-with-panq/).
- [TrueNAS feature request for qnap8528](https://forums.truenas.com/t/not-accepted-feature-request-include-qnap8528-driver-for-fan-control-on-qnap-devices/29245) (not accepted).
- [0xGiddi/qnap8528-grub-status](https://github.com/0xGiddi/qnap8528-grub-status) companion — boot-time status LED from GRUB.
- In-kernel `qnap-mcu-hwmon` — ARM/MCU QNAP models only, not relevant.
