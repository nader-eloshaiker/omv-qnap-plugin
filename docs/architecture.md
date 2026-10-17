# Architecture

openmediavault-qnap gives QNAP NAS hardware running OpenMediaVault (OMV)
QTS-style fan control, LEDs and hardware settings, using only open source
kernel drivers. It never calls QNAP binaries and never talks to the
embedded controller (EC) from userspace.

## Components

```
OMV web UI (workbench YAML)          Dashboard widgets      Diagnostics › Performance statistics
  System › QNAP: Status, Fan control,   fans & temps (grid)    QNAP graphs (rrdPage)
  Front panel, Power, Drivers, System   device (table)                ▲
        │ JSON-RPC "Qnap"               history (rrd images)          │ PNGs
        ▼                                                             │
engined/rpc/qnap.inc ──► config.xml (conf.service.qnap) ──► Apply ──► srv/salt/omv/deploy/qnap
        │ reads only: qnapd status|info --json                         │ /etc/qnapd/qnapd.json
        ▼                                                             │ modules-load / modprobe.d
/usr/sbin/qnapd  ◄────────────────────────────────────────────────────┘ grub.d reboot=efi, EC settings
  run: control loop (fan zones, status LED) + disk LED thread           qnapd.service enabled/started
  writes /run/qnapd/status.json ──► qnapd collectd (as nobody) ──► collectd ──► RRD ──► mkrrdgraph plugin
        │ sysfs only
        ▼
qnap8528.ko (EC: fans, temps, LEDs, VPD, buttons)   qm2mod.ko (QM2 card: fan, temps, slot LEDs)
coretemp / k10temp / nvme hwmon · smartctl -n standby · zpool status · /proc/mdstat
```

## Rules that shape everything

1. **One owner of the hardware.** Only `qnapd run` writes fans and LEDs.
   The UI and the graphs read `/run/qnapd/status.json` or run read-only
   `qnapd status|info`. EC transactions are slow (up to seconds) and
   serialised by the driver; one poller avoids contention.
2. **Fail safe.** qnap8528 cannot hand the fan back to the EC, so when the
   daemon stops or crashes the chassis fans go to full speed
   (`ExecStopPost=qnapd failsafe`). QM2 fans go back to the card's own
   controller on a clean stop and to full speed after a failure.
3. **Never wake sleeping disks.** Disk temperatures and health use
   `smartctl -n standby`; disk activity uses `/sys/block/*/stat`; array
   health uses `zpool status` and `/proc/mdstat`. Nothing reads `drivetemp`.
4. **Discover, do not hard-code.** hwmon indexes, LED names, QM2 cards, disk
   bays and NVMe slots are all found at runtime by name or topology, so any
   qnap8528-supported model works without per-model code.
5. **Settings live in OMV's database.** Defaults only in the datamodel;
   salt renders `/etc/qnapd/qnapd.json`; the daemon reads that file.

## qnapd (python3, stdlib only)

| Sub-command | Who runs it | Does |
|-|-|-|
| `run` | qnapd.service | Control loop every `interval` s: read sensors, compute PWM per fan zone, write PWM, status LED, status file. A thread polls disk activity every 250 ms for the disk LEDs. |
| `status [--json]` | RPC, humans | Status file if fresh, else a live read (no smartctl) |
| `info [--json]` | RPC, humans | Driver, identity (cached per boot in `/run/qnapd.identity.json`), BIOS, EC, LEDs, QM2 cards |
| `failsafe` | ExecStopPost | Fans to safe state, stop LED blinking, status LED blinking red on failure |
| `collectd` | collectd exec plugin (as nobody) | Prints PUTVAL lines from the status file for the graphs |

Main classes: `Settings` (typed config), `Hardware` (qnap8528 hwmon,
CPU/NVMe temps, QM2 discovery), `Qm2Card`, `DiskTemps` (smartctl, cached,
also S.M.A.R.T. health), `FanCurve` + `Zone` (one zone for the chassis, one
per QM2 card), `StatusLed`, `DiskLeds`, `Daemon`.

Details: [hardware/fan-control.md](hardware/fan-control.md),
[hardware/leds.md](hardware/leds.md). OMV side:
[omv-integration.md](omv-integration.md).

## Repository layout

| Path | Contents |
|-|-|
| `usr/sbin/qnapd` | The daemon and CLI |
| `usr/share/openmediavault/` | datamodels, confdb create/migrations, engined RPC + module, workbench YAML, mkrrdgraph plugin |
| `srv/salt/omv/deploy/qnap/` | Salt state for config, modules, grub, EC settings, service |
| `srv/salt/omv/deploy/collectd/plugins/qnap.sls` | collectd exec plugin config for the graphs |
| `debian/` | Packaging (debhelper, `Architecture: all`), unit file, postinst/postrm |
| `tests/test_qnapd.py` | Unit tests against a fake sysfs tree (no hardware needed) |
| `tools/` | Dev-machine deploy script and NAS-side hardware test scripts |
| `docs/` | This documentation |
