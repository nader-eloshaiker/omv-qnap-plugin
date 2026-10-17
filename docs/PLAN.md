# openmediavault-qnap — Implementation Plan

Status: **Phase 1 validated on the reference TS-253D; Phase 2 LEDs and
graphs in progress** (2026-10-17). This document is the roadmap and design
of record; topic documents in [`docs/`](README.md) hold the details.

## 1. Goal

Give QNAP NAS hardware running OpenMediaVault the hardware experience QTS
provides, without QNAP's proprietary code:

- QTS-style **Smart Fan** control (Quiet / Normal / Performance / Custom /
  Manual), driven by CPU, system (EC), disk and NVMe temperatures.
- **Front-panel LEDs** that mean what they mean on QTS (status, disk, USB).
- **Buttons** (USB One Touch Copy, Reset) that do something useful.
- **EC settings**: power recovery, EuP mode, LED brightness.
- Live **fan/temperature status** in the OMV UI and dashboard.
- **QM2 expansion cards** (via qnap-qm2): card fan control from the
  card's own sensors (Phase 1) and per-slot LEDs (Phase 2).

Primary target: **TS-253D** on OMV 8 (the reference box runs OMV 8.5 on
Debian 13 with the Proxmox kernel), with and without a QM2 card. Secondary:
anything supported by [qnap8528](https://github.com/0xGiddi/qnap8528)
(≈120 models). QM2 cards via [qnap-qm2](https://github.com/0xGiddi/qnap-qm2)
are a first-class target, not an add-on.

### Non-goals

- Shipping or calling QNAP binaries (`hal_app`, `libuLinux_hal.so`) — this
  is what [omv-panq-plugin](https://github.com/Dag-Rui/omv-panq-plugin) and
  [Stonyx/QNAP-EC](https://github.com/Stonyx/QNAP-EC) do; it is legally
  murky and model-fragile.
- Talking to the EC directly from userspace (`iopl`/`ioperm`). The kernel
  driver serialises EC access; userspace port I/O races with it.
- Reproducing QTS features unrelated to hardware (One Touch Copy's full
  backup-job UI, QTS factory reset semantics).
- (Initially) building/installing the kernel drivers — see Phase 4.

## 2. Key research findings

Full notes are in [`docs/reference/`](reference/). The decisions below rest
on these facts:

| Finding | Consequence |
|-|-|
| qnap8528 exposes **only manual PWM** (`pwmN`, 0–255, no `pwmN_enable`), no way to return the fan to EC auto mode | The plugin **must** run a control loop and must fail safe to full speed |
| TS-253D: 1 fan (`fan1_input`, `pwm1`), LEDs `status`, `usb`, `panel_brightness`, `hdd1`, `hdd2`, EC temps `temp1`/`temp6` only. The reference unit (qnap8528 1.24) **passes the IT8528 chip check without `skip_hw_check`** | Keep `skip_hw_check` in the UI as an escape hatch, not a TS-253D requirement |
| hwmon index is not stable (`hwmon3` on one box, `hwmonN` on another) | Always discover devices by `name` |
| EC temps include junk channels (e.g. `temp11=2°C` on TS-464); "CPU" EC temps may be bogus on x86 | Filter implausible values; use coretemp/k10temp for CPU |
| Button codes, **verified on the TS-253D**: `BTN_1` = Reset, `BTN_2` = USB Copy (the README is right, a source comment says the opposite); `BTN_0` = chassis open; power button is ACPI | Phase 3 uses the verified mapping; press and release are separate events, so hold time is measured in userspace |
| qnap8528 sysfs attrs under `ec/` and `vpd/` have no trailing newline | Strip on read |
| EC access may block up to ~5 s; all consumers share it | One daemon owns polling; UI reads the daemon's status file |
| `smartctl` without `-n standby` wakes sleeping disks | Disk temps via `smartctl -n standby -A -j`, own (slower) interval |
| QTS publishes **no numeric fan thresholds** | Presets are our own, tuned on TS-253D (see §5.2) |
| omv-panq / FanControl.sh have no hysteresis, no failsafe, config outside OMV's DB | Do all three properly |
| qm2mod: hwmon `qm2` per card (child of `platform/qm2.N`), `temp1..N` = one sensor per M.2 slot, `fan1_input` (60 RPM steps), `pwm1` 0–255; `fan_default` returns the fan to the PIC but nobody knows whether that is temperature controlled | Each card is its own fan zone; failsafe stays at PWM 255 |
| qm2mod's I2C adapter is a child of the card's PCIe switch, and its number is in every LED name (`qm2-<adapter>:{red,green}:slotN`) | NVMe SSDs on a card are found by PCI path (switch → downstream port → nvme) |
| `reboot=efi` on the kernel command line fixes reboot hangs on QNAP x86 boxes (user-reported on TS-253D) | Offer it as a Hardware option via a `/etc/default/grub.d` drop-in |

## 3. Architecture

```
┌──────────────── OMV workbench (Angular, YAML-defined) ────────────────┐
│ System › QNAP › Status (datatable, 5 s)   Fan control (form)          │
│   Front panel · Power · Drivers (forms) · System (device info)        │
└───────────────┬───────────────────────────────────────────────────────┘
                │ JSON-RPC  (service "Qnap")
┌───────────────▼──────────────┐   Save → confdb → module "qnap" dirty
│ engined/rpc/qnap.inc         │   Apply → omv-salt deploy run qnap
│  getSettings / setFan…       │
│  getHardwareSettings / set…  │──── qnapd status|info --json (read only)
│  getStatus                   │
└───────────────┬──────────────┘
                │ config.xml  (conf.service.qnap)
┌───────────────▼──────────────────────────────────────────────────────┐
│ srv/salt/omv/deploy/qnap                                              │
│  /etc/qnapd/qnapd.json                 (daemon config)                │
│  /etc/modules-load.d|modprobe.d/openmediavault-qnap.conf (optional)   │
│  /etc/default/grub.d/openmediavault-qnap.cfg + update-grub (optional) │
│  EC power_recovery / eup_mode (one-shot sysfs writes)                 │
│  qnapd.service running|dead                                           │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────┐    /run/qnapd/status.json
│ /usr/sbin/qnapd (python3)    │──► (read by qnapd status → RPC)
│  fan loop · status LED ·     │
│  [P2] disk LEDs/RAID ·       │
│  [P3] buttons/USB LED/beeper │
└───────────────┬──────────────┘
                │ sysfs / evdev only
┌───────────────▼──────────────────────────────────────────────────────┐
│ qnap8528.ko (hwmon "qnap8528", leds qnap8528::*, input "qnap8528",    │
│              /sys/devices/platform/qnap8528/{ec,vpd})                 │
│ qm2mod.ko   (hwmon "qm2", leds qm2-N:{red,green}:slotM)  [fan P1/LED P2]│
│ coretemp / k10temp / nvme hwmon · smartctl                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Why a single Python daemon

- One owner of hardware state → no EC races, one place for failsafe logic.
- `python3` is already a dependency of openmediavault; stdlib only, so the
  package stays `Architecture: all` with no compiled code.
- Fan, LED and button logic all need the same health picture (fan failed →
  status LED red → beep), so they belong in one process.
- The OMV UI never pokes hardware for writes; for reads it uses the
  daemon's status file (or a one-shot live read when the daemon is off).

### Why not `fancontrol` (lm-sensors)

It can drive `pwm1` from hwmon temps, but it cannot use disk temperatures
without waking disks, has no notion of LEDs/buttons, and its config format
is awkward to generate and validate from the OMV UI.

## 4. Configuration model

One singleton datamodel, `conf.service.qnap` (xpath `//services/qnap`),
defaults defined only in
[`conf.service.qnap.json`](../usr/share/openmediavault/datamodels/conf.service.qnap.json).
One RPC write method per form page (`setFanSettings`,
`setFrontPanelSettings`, `setPowerSettings`, `setDriverSettings`) each owns
a subset, so each page posts only its own fields; the last three share
`getHardwareSettings`.

| Field | Type / default | Page | Phase |
|-|-|-|-|
| `enable` | bool / false | Fan | 1 |
| `interval` | 2–120 s / 10 | Fan | 1 |
| `fanmode` | quiet\|normal\|performance\|custom\|manual / normal | Fan | 1 |
| `manualpwm` | 0–255 / 160 | Fan | 1 |
| `minpwm`, `maxpwm`, `hysteresis` | 64, 255, 3 °C | Fan (custom) | 1 |
| `use{cpu,system,disk,nvme}` | bool / true | Fan | 1 |
| `{cpu,sys,disk,nvme}{low,high}` | °C | Fan (custom) | 1 |
| `diskinterval` | 10–3600 s / 60 | Fan | 1 |
| `useqm2` | bool / true — drive QM2 card fans | Fan | 1 |
| `ledstatus` | bool / true | Front panel | 1 |
| `ledbrightness` | 0–100 / 100 | Front panel | 1 |
| `powerrecovery` | unchanged\|off\|on\|last | Power | 1 |
| `eupmode` | unchanged\|off\|on | Power | 1 |
| `loadmodule`, `skiphwcheck` | bool / false | Drivers | 1 |
| `loadqm2` | bool / false — load `qm2mod` at boot | Drivers | 1 |
| `rebootefi` | bool / **true** (fixes reboot hangs; on for new installs) | Power | 1 |
| `leddisk` (activity/error/locate) | bool | Front panel | 2 |
| `ledschedule` (night brightness + times) | | Front panel | 2 |
| `copyaction`, `copycommand` | none\|command | Buttons | 3 |
| `resetaction`, `resetcommand`, `resethold` | none\|command, 3 s | Buttons | 3 |
| `beeper` (events) | bool | Buttons | 3 |

New fields → bump the package version and add
`confdb/migrations.d/conf.service.qnap_<version>.sh` that adds the keys
(`omv_config_add_key`), per OMV convention.

## 5. Fan control design (Phase 1 — implemented)

### 5.1 Algorithm

Every `interval` seconds:

1. Read sources (each optional):
   - **cpu**: coretemp `Package id 0` / k10temp `Tctl|Tdie` (hottest).
   - **system**: all qnap8528 `tempN_input` within 5–110 °C.
   - **nvme**: each `nvme` hwmon `temp1` (Composite).
   - **disk**: `smartctl -n standby -A -j /dev/sdX` for non-removable
     disks, cached for `diskinterval`; standby disks are skipped.
2. **Critical override**: any enabled source at/above its critical limit
   (cpu 90, system 55, disk 55, nvme 75 °C) → PWM 255.
3. **Curve**: for each source `demand = clamp((T − low)/(high − low), 0, 1)`;
   `pwm = minpwm + max(demand) × (maxpwm − minpwm)` (the "max of normalised
   ratios" idea from omv-panq, generalised to N sources).
4. **Hysteresis**: ramp **up** immediately and remember which source
   raised the fan and its temperature. Ramp **down** only once that source
   has cooled by `hysteresis` °C, then by at most 16 PWM per cycle. (The
   first version inflated *every* source by the hysteresis; on hardware a
   disk at 39 °C, never the cause, then held the fan at PWM 140 after a CPU
   burst.)
5. Write `pwmN` for every PWM group when changed, and at least every 60 s
   (guards against EC resets).
6. **Fan failure**: `fanN_input` = 0 RPM at PWM ≥ 64 (or invalid 65535) for
   3 consecutive cycles → fault.
7. **No sensors at all** (every enabled source empty) → PWM 255 + fault.
8. Status LED: green when healthy, red on any fault.
9. Write `/run/qnapd/status.json` atomically.

### 5.2 Presets (tuned on a TS-253D, 2026-10-17)

| Mode | CPU °C | System °C | Disk °C | NVMe °C | PWM range |
|-|-|-|-|-|-|
| Quiet | 60→90 | 35→50 | 40→50 | 50→70 | 48–200 |
| Normal | 55→85 | 30→45 | 38→48 | 45→65 | 64–255 |
| Performance | 50→80 | 28→40 | 35→45 | 40→60 | 100–255 |

CPU ranges were raised 10 °C after testing, and the curve uses the
**median** CPU temperature over 60 s (`CPU_SMOOTH_SECONDS`); a 30 s mean
was tried first and still let frequent spikes drag the fan up. With 45→80 and raw
readings, bursty background load (J4125 package spiking to 60–68 °C for a
sample, idle 45–52 °C) sawtoothed the chassis fan between PWM 128 and 217,
which the user could hear. Intel's only thermal spec for the J4125 is
T<sub>junction</sub> 105 °C. The critical check (90 °C) still uses the raw
reading.

Notes: the TS-253D has a J4125 (Tjmax 105 °C) and one 70 mm fan, rated
for 0–40 °C ambient. Disks are the thermally sensitive part of a NAS
(manufacturers spec ≤ 55–60 °C), hence the low disk ranges.
Measured PWM → RPM (15 s per step, `fan-sweep`, OMV idle):

| PWM | 255 | 192 | 128 | 96 | 80 | 64 | 56 | 48 | 40 | 32 | 16 | 8 |
|-|-|-|-|-|-|-|-|-|-|-|-|-|
| TS-253D chassis (70 mm) | 3631 | 2804 | 1905 | 1407 | 1191 | 944 | 786 | 663 | 546 | 397 | 342 | stall |
| QM2-2P-244A-A1 | 5860 | 4740 | 3320 | 2440 | 1840 | 1260 | 880 | stall | 0 | 0 | 0 | 0 |

- Chassis fan: stalls between 16 and 8, restarts from standstill only at
  32. QM2 fan: stalls at 48, barely restarts at 48 (160 RPM); its PIC
  default is 64.
- Every zone has a floor in all modes (`MIN_PWM_CHASSIS` 40,
  `MIN_PWM_QM2` 64), so a low Quiet/Custom/Manual value cannot stall a fan.
- qnap8528 read-back drifts (128 → 127, 56 → 53); the daemon compares
  against what it wrote, not the read-back.
- Load note: an open OMV dashboard with many widgets kept two php-fpm
  workers at ~80% of a core (tempmon re-runs every sensor script per
  refresh), enough to spike J4125 core temps to 60 °C.
- **Open:** noise at each PWM (needs a listener), and per-zone `minpwm` for
  Custom mode if the floors turn out too conservative.

### 5.3 Failure handling

| Event | Behaviour |
|-|-|
| Daemon stops cleanly | `ExecStopPost=qnapd failsafe` → PWM 255 |
| Daemon crashes / killed | same `ExecStopPost`, and status LED → blinking red |
| Exception in a loop iteration | PWM 255 for that cycle, logged, loop continues |
| Driver not loaded | daemon exits 1; systemd retries every 10 s, without a start limit (every Apply restarts the daemon, so a limit of 5 per 5 min was hit during testing) |
| Sensor source missing | ignored if others work; all missing → 255 |
| QM2 card: no slot/NVMe sensor | that card's fan → 255 + fault |

QM2 card fans (when `useqm2` is on) return to the card's own controller
(qm2mod `fan_default`, ≈1200 RPM idle on a QM2-2P-244A-A1) after a **clean**
stop or restart, and go to PWM 255 after a failure or when `qnapd failsafe`
is run by hand. With `useqm2` off the daemon hands each card back at start
and never writes to it again. (Full speed on every restart was a ~5900 RPM
blast the user could hear on each Apply/upgrade; they chose to trust the
card's controller.)

Trade-off: disabling the plugin leaves the fan at full speed (loud) until
reboot. That's deliberate — qnap8528 offers no way to give control back to
the EC, and loud is better than cooked. The UI hint states this.
*Open question:* add a user-chosen "speed when stopped" (default 255)?

### 5.4 QM2 expansion cards (Phase 1)

- Discovery: every hwmon named `qm2`, re-scanned each cycle, because
  `qm2mod` may load after `qnapd`. Card identity is in `hwmonX/device/` (`qm2.N`: `model`, `serial`, `pic_version`).
- Each card is a **separate fan zone** with its own PWM state, hysteresis
  and rate limit. Its inputs are the card's slot sensors plus the NVMe SSDs
  whose sysfs path is below the card's PCIe switch (found via the I2C
  adapter number in the slot LED names). If the switch can't be found, all
  NVMe SSDs count, which can only make the fan run faster.
- Curve and critical limit: the NVMe ones (`nvmelow/high`, 75 °C), on the
  active preset's PWM range. **To tune on hardware:** the stall PWM of the
  card fan (it is a different, smaller fan from the chassis one).
- The chassis zone still includes every NVMe SSD, since the chassis fan
  exhausts the whole case.
- Manual mode applies `manualpwm` to the cards as well.
- Card fan at 0 RPM for 3 cycles at PWM ≥ 64 → fault → status LED red.
- `useqm2` (default on) is also the fallback switch: off hands the fan to
  the card's controller, for users who prefer that or hit compatibility
  issues. Clean stops hand back too (see §5.3).

## 6. LED design

### 6.1 QTS semantics → qnap8528 (from the TS-x53D user guide)

| QTS meaning | QTS LED | qnap8528 write | Phase |
|-|-|-|-|
| Ready | status solid green | `status/brightness=1` | 1 ✅ |
| Booting / not ready | status blinking green | brightness 1 + trigger `timer` | 1 ✅ (daemon start) |
| Fan failure, hardware error, volume full | status solid red | brightness 2 | 1 ✅ (fan/sensor) |
| Service failed (ours) | status blinking red | brightness 2 + `timer` | 1 ✅ |
| RAID degraded | status blinking red | brightness 2 + `timer` | 2 |
| RAID rebuild / reshape / resync | status green/red alternating | `status/blink_bicolor` | 2 |
| Volume ≥ 95 % full | status solid red | brightness 2 | 2 |
| Disk present | `hddN` green | `hddN/brightness=1` | 2 |
| Disk activity | `hddN` blinking green | brightness 1 + `timer` (≈110 ms window) or oneshot per IO | 2 |
| Disk error (SMART fail / md faulty) | `hddN` red | brightness 2 | 2 |
| Locate disk | `hddN` blinking red | brightness 2 + `timer` | 2 (UI button) |
| USB device mounting / copying | `usb` blinking blue | brightness 1 + `timer` | 3 |
| USB device mounted | `usb` solid | brightness 1 | 3 |
| Brightness / night schedule | all LEDs | `panel_brightness` 0–100 | 1 ✅ / 2 (schedule) |
| QM2 SSD present | `qm2-A:green:slotN` | brightness 1 | 2 |
| QM2 SSD error (SMART critical warning) | `qm2-A:red:slotN` | brightness 1 | 2 |
| QM2 locate | `qm2-A:red:slotN` | brightness 2 (PIC blink) | 2 |

qm2mod LEDs differ from qnap8528: one LED per colour, red `2` = PIC blink,
green `1` and `2` are both solid. Panel brightness does not apply to them.

Status priority (highest wins): error (solid red) > degraded (red blink) >
rebuilding (bicolour) > starting (green blink) > ok (green). Mirrors
qnap8528's `examples/qnap-set-status.sh`.

### 6.2 Phase 2 sources

- RAID: parse `/proc/mdstat` (`[U_]` → degraded, `recovery|resync|reshape`
  → rebuilding). Optionally ZFS (`zpool status -x`) and Btrfs (`btrfs
  device stats`) later.
- Disk ↔ slot mapping: model config only names `hdd1`, `hdd2`; map via
  `/sys/block/sdX/device` → ATA port (`/sys/class/ata_port`) → slot order.
  Must be verified on hardware; provide an override table in config.
- Disk activity: poll `/sys/block/sdX/stat` each 0.3–0.5 s (as in
  `examples/qnap-disk-led-monitor.sh`) in a separate thread — **not**
  `disk-activity` trigger (that's global, not per disk).
- SMART health: reuse the disk poll (`smartctl -H`, standby-aware).
- QM2 slot ↔ NVMe mapping: the switch's downstream port order (`lspci -tv`)
  vs slot numbering, with qm2mod's slot-swap correction on generic 2P
  cards. Must be verified on hardware (insert one SSD, see which green LED
  is right).

## 7. Buttons design (Phase 3)

- Read `/dev/input/by-path/platform-qnap8528-event` (fallback: scan
  `/proc/bus/input/devices` for `Name="qnap8528"`) with stdlib `struct`
  parsing of `input_event` — no python3-evdev dependency.
- Keys (verified on a TS-253D, 2026-10-17): `BTN_1` Reset, `BTN_2` USB
  Copy, `BTN_0` chassis open (untested). Press and release arrive as
  separate events; measure hold time in userspace. No autorepeat (EV=3).
- Actions (admin-configured, validated):
  - **USB Copy**: none | run a command (e.g. an OMV rsync job via
    `omv-rpc` / a script). USB LED blinks while the action runs, solid on
    success, 3 short beeps on failure (QTS behaviour).
  - **Reset** short press (≥3 s): none | command. Default: none. Never a
    factory reset of OMV. A sensible built-in option to consider:
    `omv-firstaid`-style "reset web UI admin password / network to DHCP" —
    needs explicit design + confirmation in the UI.
  - **Reset long press (≥10 s)**: none (reserved).
  - **Chassis open**: log + OMV notification.
- Power button stays with systemd-logind (ACPI). Document
  `HandlePowerKey=` in `/etc/systemd/logind.conf` instead of reimplementing.
- **Beeper** (optional): QTS uses beeps for start/shutdown/fan failure.
  qnap8528 exposes no buzzer; investigate `pcspkr` + `beep`, or an EC
  register (future qnap8528 feature request). Low priority.

## 8. Notifications (Phase 2)

Faults (fan failure, critical temperature, chassis open) should reach the
user, not just the LED. Options, in order of preference:

1. syslog with a stable tag (`qnapd`) — done in Phase 1.
2. OMV's notification system: send via `omv-notify`/`mail` respecting the
   *System › Notification* settings; add a `conf.system.notification`
   entry type (`qnap`) so it can be toggled like other events.
3. monit check on `qnapd` process (OMV already uses monit for its services).

## 9. UI

- Navigation: **System › QNAP** (QTS keeps fans/LEDs under *Control
  Panel › Hardware*; OMV's equivalent is the System menu).
  - **Status** — datatable of fans (RPM), fan duty (%), every temperature
    source; auto-reload 5 s.
  - **Fan control** — enable, mode, interval, sources, custom curve
    (fields shown only for *Custom*), manual PWM.
  - **Front panel** — status LED, brightness, available LEDs (Phase 2:
    disk LEDs, night schedule).
  - **Power** — power recovery, EuP, `reboot=efi` (+ whether it is active).
  - **Drivers** — qnap8528 / qm2mod status, load at boot, `skip_hw_check`.
  - **System** — model, serial number, BIOS, EC firmware, manufacture
    date, board codes, QM2 cards (read-only). The first version had one
    *Hardware* form for the first three; split into tabs on request.
  - *(Phase 2)* **Disks** — slot table with Locate toggle.
  - *(Phase 3)* **Buttons** — button actions.
- Dashboard: grid widget "QNAP fans & temperatures" (10 s).
- *(Phase 2)* **Performance graphs** (fan RPM, duty, temperatures per zone)
  following openmediavault-tempmon's collectd-exec → mkrrdgraph pattern
  (see `reference/omv-plugin-conventions.md`). The exec script only reads
  `/run/qnapd/status.json` (world-readable). That means no sudo rule and no
  extra EC/smartctl polling, unlike tempmon, which runs each sensor script
  every interval *and* on every dashboard refresh. Useful for tuning and
  for the 48 h soak (PWM churn).
- Users already running tempmon with qnap8528/smartctl scripts duplicate
  the EC polling, and wake disks if `smartctl` lacks `-n standby`. Document
  this, and point them at `qnapd status --json` instead.
- Targets OMV 8's workbench (validated on OMV 8.5).

## 10. Packaging & platform

- Package `openmediavault-qnap`, `Architecture: all`, native version
  `8.0.N` (omv-extras convention: major = OMV major; 7.0.x were
  pre-releases). **Versions must be
  PEP 440 compatible** (no tilde pre-releases): `omv-confdbadm migrate`
  parses the old version and the migration file names with
  `packaging.version`.
- `Depends: openmediavault (>= 8), python3, smartmontools`;
  `Recommends: dkms`. **No hard dependency on the drivers** (they have no
  .deb yet); the UI shows "Not loaded" and the daemon refuses to start
  without the hwmon device.
- OMV 8 (Debian 13 Trixie) only, `debhelper-compat (= 13)` (stock Trixie
  debhelper), built in `debian:trixie`. OMV 7 would get its own `7.x`
  branch and release line if there is demand (omv-extras style).
- `qnapd.service` is installed with `--no-enable --no-start`; salt owns
  enable/start (`service.running` / `service.dead`), restarting on config
  change via `watch`.
- `postinst`: confdb create/migrate, `omv-salt deploy run qnap`,
  `try-restart` on upgrade. `postrm purge`: drop config node, generated
  files, grub drop-in (+ `update-grub`).
- `reboot=efi`: drop-in `/etc/default/grub.d/openmediavault-qnap.cfg`
  appending to `GRUB_CMDLINE_LINUX_DEFAULT` only if `reboot=efi` is not
  already there (the file is shell sourced by grub-mkconfig), on by default,
  `update-grub` only on change. Never edits `/etc/default/grub`; a manual
  `reboot=efi` there is not duplicated. The Power page shows whether it is
  active in `/proc/cmdline`.
  *To check:* systems booting via systemd-boot (rare on OMV) are not covered.
- Distribution: GitHub releases first; later propose to omv-extras.

## 11. Model support strategy

- Everything is discovered at runtime from sysfs (fans, PWM groups, LEDs,
  `ec/*` attributes present or not), so any qnap8528-supported model works
  without per-model code in the plugin.
- Multi-fan models: qnap8528 has up to 4 PWM groups. Phase 1 drives all
  groups with the same PWM. *Phase 2 option:* per-group curves (e.g. CPU
  fan vs disk fans on TS-x73A / TVS models).
- `skip_hw_check`: listed upstream for TS-453D, TS-464, TS-464EU, TR-464,
  Qu-X05. The reference TS-253D passed the chip check without it, so the
  UI hint only says to use it when dmesg shows the check failing.
- QM2 cards: fan zone per card (Phase 1, §5.4); slot LEDs from NVMe
  presence/health (Phase 2). The QM2-2S10G1TB02 is not supported by
  qm2mod (EC-attached), so it will not show up.
- Unknown models: qnap8528 refuses to load → UI shows driver not loaded;
  point the user to qnap8528's issue tracker.

## 12. Phases & milestones

### Phase 0 — Repo bootstrap ✅
- [x] Research (this doc + `docs/reference/`)
- [x] Package skeleton builds (now on Debian 13), lintian clean except benign tags
- [x] Unit tests for daemon logic against a fake sysfs

### Phase 1 — Fan control MVP (scaffolded, needs hardware validation)
- [x] Datamodel, confdb, RPC, engined module, salt state, workbench pages
- [x] `qnapd`: discovery, curve, presets, hysteresis, critical, failsafe
- [x] Status LED (ok / fault / starting / service failed)
- [x] Panel brightness, power recovery, EuP, module loading, `reboot=efi`
- [x] `reboot=efi` from the plugin alone (2026-10-17): manual entry removed
      from `/etc/default/grub`, drop-in written on Apply, reboot completed
      in 54 s without hanging, `/proc/cmdline` has `reboot=efi` once, qnapd
      in control 11 s into boot
- [x] Install on a TS-253D (OMV 8.5 / Debian 13): verify every page, Save/Apply flow,
      dashboard widget, service status (2026-10-17). OMV 8 has no generic
      *Diagnostics › Services* table; the module status shows in the
      dashboard *Services* widget. Fixed on the way: PEP 440 versions,
      postinst daemon-reload, start limit, ledtrig-timer, VPD NULs.
- [x] Measure PWM→RPM curve and stall point; tune presets / `minpwm`
      (chassis and QM2; noise check still open)
- [x] Verify qnapd does not wake disks (2026-10-17): sda put in standby
      with `smartctl -s standby,now` stayed asleep through three disk polls
      (temperature skipped, bay LED green). It was then woken by OMV's own
      smartd 30-min check (`-n never`), not by qnapd. Natural spindown on
      the reference box is not configured (hdparm not installed).
- [x] Verify failsafe: `kill -9` → chassis and QM2 fans 255, status LED red
      blink, systemd restart after ~11 s, LED green (2026-10-17). Found and
      fixed: the QM2 PIC ignores the first PWM write after a restart; the
      daemon now verifies the read-back every cycle.
- [x] QM2 card fan zones (qm2mod), `loadqm2`, card info (Drivers / System pages)
- [ ] Disk source: the TS-253D boots from a USB SSD (`sdc`, non-removable)
      that lands in the HDD temperature range; decide whether SSD/USB
      disks belong in `disk` (or the NVMe range)
- [ ] QM2 on hardware: discovery, NVMe-on-card mapping, card fan PWM→RPM
      and stall point, failsafe, what `fan_default` does
- [x] Target OMV 8 only, version 8.0.0 (OMV 7 dropped, 2026-10-17)
- [ ] GitHub Actions: build .deb in `debian:trixie`,
      run unit tests, lintian, `php -l`

### Phase 2 — QTS-like LEDs & health
- [ ] mdstat **and ZFS** (`zpool status -x`; the reference box uses ZFS
      pools, no mdraid) → status LED (degraded/rebuild), volume-full check
- [x] Disk slot mapping + present/error/activity LEDs (7.0.2; bay N = SATA
      port N, verified on a TS-253D by lighting each LED and by reading
      from sda only; health from S.M.A.R.T. + `zpool status -LP` + mdstat)
- [ ] Locate action in UI
- [x] QM2 slot LEDs: present / activity / error (7.0.2). Slot N = Nth
      NVMe-or-empty downstream port of the card's switch, swapped when
      qm2mod logs swap=1; verified on a QM2-2P-244A-A1 by lighting each slot
      and by reading from nvme0 only (slot 1 blinked). Green blink is the
      kernel timer trigger over the card's I2C; error = S.M.A.R.T. (NVMe
      critical warning) or a faulted ZFS/md member.
- [ ] Locate action for bays and QM2 slots
- [ ] LED brightness night schedule
- [ ] OMV notifications for faults
- [ ] Optional per-PWM-group curves for multi-fan models
- [ ] Performance graphs via collectd exec reading `/run/qnapd/status.json`
- [ ] confdb migration for new fields

### Phase 3 — Buttons & sounds
- [x] Verify key mapping on TS-253D (`tools/hw/button-test.py`: Reset = BTN_1,
      USB Copy = BTN_2)
- [ ] evdev reader and hold-time detection in qnapd
- [ ] USB Copy action + USB LED feedback
- [ ] Reset button actions (safe defaults)
- [ ] Chassis-open event, beeper investigation

### Phase 4 — Driver integration
- [ ] Package `qnap8528-dkms` / `qm2mod-dkms` (or vendor DKMS sources) and
      make the plugin depend/recommend them; install headers automatically
      (`linux-headers-amd64` or `proxmox-headers-*` for the OMV Proxmox kernel)
- [ ] Upstream contributions to qnap8528 if needed (README button table fix,
      buzzer support, EC auto-fan restore)

## 13. Testing strategy

- **Unit** (`make test`): fake sysfs tree emulating a TS-253D
  (`QNAPD_SYSFS_ROOT`); covers discovery, junk filtering, curve,
  hysteresis, critical, manual mode, fan-failure LED, failsafe, info.
- **Package**: build + lintian in a Debian 13 container; `php -l`.
- **Integration on hardware** (manual checklist in Phase 1): fresh install,
  upgrade, purge; Save/Apply; daemon restart on config change; reboot with
  `loadmodule`; failsafe on crash; `reboot=efi` toggling.
- **Soak**: 48 h with disks spinning down, check journal for PWM churn
  (hysteresis effectiveness) and no disk wake-ups.

## 14. Risks & open questions

| Risk / question | Mitigation |
|-|-|
| EC power-on fan behaviour unknown before the daemon starts | Daemon starts early (`After=systemd-modules-load`). Observed after an unplanned power loss on the TS-253D: the EC powered the box back on (power recovery = last state) and qnapd was controlling the fans 11.5 s after kernel start, without a login |
| Button mapping disagreement (README vs source) | Verify with `evtest`; report upstream |
| Disk-slot ↔ `/dev/sdX` mapping unknown | Discover via ATA port; config override |
| QM2 card fan needs a different minimum PWM than the chassis fan | Measure on hardware; per-zone `minpwm` if needed |
| `smartctl` cost on many-bay units | Separate `diskinterval`, standby-aware; consider `drivetemp` hwmon as an option |
| qnap8528 not packaged; kernel upgrades need DKMS rebuild | Recommend dkms + headers; Phase 4 packaging |
| Full-speed fan after disabling the plugin | Documented; optional "speed when stopped" |
| No buzzer interface | Defer; investigate pcspkr / EC |
| OMV 8.x workbench changes | Validate the UI after OMV updates (validate-ui runbook) |
| Driver load fails on unknown model → UI just says "Not loaded" | Show dmesg hint on the Drivers page (later) |

## 15. References

- qnap8528 driver: <https://github.com/0xGiddi/qnap8528>
- qnap-qm2 driver: <https://github.com/0xGiddi/qnap-qm2>
- Prior art: <https://github.com/Dag-Rui/omv-panq-plugin>,
  <https://github.com/Stonyx/QNAP-EC>,
  <https://github.com/edddeduck/QNAP_Fan_Control>,
  <https://forum.openmediavault.org/index.php?thread/57619-qnap-temperatures-fan-control/>
- OMV plugin development: <https://docs.openmediavault.org/en/latest/development/plugins.html>,
  <https://github.com/OpenMediaVault-Plugin-Developers>, <https://wiki.omv-extras.org/>
- QNAP TS-x53D user guide (LED/button/beep tables):
  <https://eu1.qnap.com/TechnicalDocument/Storage/SMB%20NAS/ts-x53d/ts-x53d-ug-en-us.pdf>
- QTS Smart Fan: <https://docs.qnap.com/operating-system/qts/5.1.x/en-us/configuring-smart-fan-settings-27A5C976.html>
