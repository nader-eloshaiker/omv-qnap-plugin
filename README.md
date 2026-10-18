# openmediavault-qnap

An [OpenMediaVault](https://www.openmediavault.org/) plugin that brings
QTS-style hardware control to QNAP NAS devices, using only the open source
[qnap8528](https://github.com/0xGiddi/qnap8528) embedded controller driver.
It does not use QNAP's proprietary binaries.

Primary target is the **TS-253D**. Any model supported by qnap8528 should
work, because all hardware is discovered at runtime.

> **Status: feature complete (8.0.5).** Every feature below is verified on
> the reference TS-253D with a QM2-2P-244A-A1 card (OMV 8.5). Other models
> are untested: see [docs/hardware/models.md](docs/hardware/models.md) and
> please send a [model test report](docs/testing/model-testing.md).

## Features

**Fan control**
- QTS-style Smart Fan: Quiet, Normal and Performance presets, a Custom
  curve (ramp-up and full-speed temperature per source, PWM range,
  hysteresis) and Manual.
- Temperature sources: CPU (coretemp / k10temp), the embedded controller's
  system sensors, hard disks (S.M.A.R.T., sleeping disks are never woken)
  and NVMe SSDs. USB disks are ignored, since the chassis fans can't cool
  them.
- Hysteresis, CPU spike smoothing, critical-temperature override,
  fan-failure detection and PWM read-back checks.
- Fail safe: if the daemon stops or crashes, the chassis fans go to full
  speed.
- QM2 expansion cards: each card's fan follows its own M.2 slot and NVMe
  temperatures, or can be left to the card.
- Idle disks are left alone so they can spin down
  ([what else keeps disks awake](docs/disk-sleep.md)).

**LEDs**
- Status LED following system and storage health, QTS style: green when
  healthy, solid red for a fan or sensor fault or a failed or full volume,
  blinking red for a degraded pool or array or a crashed daemon,
  green/red alternating while a pool resilvers or an array rebuilds. A
  scrub doesn't change it.
- Disk bay and QM2 slot LEDs: present, activity and error (S.M.A.R.T.,
  faulted ZFS or md member).
- Locate: blink a bay's or QM2 slot's LED red for 10 minutes from the
  Disks page.
- Front panel brightness with an optional night schedule.
- USB LED feedback for USB Copy.

**Buttons and sounds**
- USB Copy runs a chosen OMV Scheduled Task; Reset held 3 seconds runs
  another. Chassis open is logged and mailed.
- Optional QTS beeps through the buzzer: at boot, every 5 minutes while a
  fan has stopped, when a pool turns degraded, failed, full or rebuilding,
  and when USB Copy fails.

**Monitoring and notifications**
- Status page (fans, duty, every temperature, storage health) and a Disks
  page (bays, QM2 slots, devices, LED state).
- Dashboard: a fans and temperatures grid, a device widget, history graphs
  and round gauges for fan duty and CPU, system, disk and NVMe
  temperatures.
- Performance graphs (Diagnostics › Performance statistics › QNAP):
  temperatures, fan speed and fan duty, by hour, day, week, month and year.
- Fault emails through OMV's own notifications ("QNAP hardware" event):
  fan, temperature, disk or pool problems that last a minute, when they
  clear, and when the daemon stops unexpectedly.

**Hardware settings and drivers**
- Power recovery after a power failure, EuP mode and the `reboot=efi`
  kernel option (QNAP x86 boxes hang on reboot without it).
- System page: model, serial number, BIOS, EC firmware, boards, QM2 cards.
- Driver packages `qnap8528-dkms` and `qm2mod-dkms` in every release,
  loading at boot from the Drivers page, and one-click kernel headers so
  DKMS rebuilds the drivers after kernel updates.

The plugin never talks to the EC from userspace and never runs QNAP
binaries: all hardware access goes through the open source drivers.

## Screenshots

From the reference TS-253D; serial numbers, host name and addresses are
blurred.

| | |
|-|-|
| ![Dashboard](docs/images/dashboard.jpg) Dashboard | ![Dashboard gauges](docs/images/dashboard-gauges.jpg) Dashboard gauges |
| ![System › QNAP](docs/images/overview.jpg) System › QNAP | ![Status](docs/images/status.jpg) Status |
| ![Fan control](docs/images/fan-control.jpg) Fan control | ![Custom fan curve](docs/images/fan-custom.jpg) Custom fan curve |
| ![Front panel](docs/images/front-panel.jpg) Front panel | ![Disks](docs/images/disks.jpg) Disks |
| ![Buttons](docs/images/buttons.jpg) Buttons | ![Power](docs/images/power.jpg) Power |
| ![Drivers](docs/images/drivers.jpg) Drivers | ![System](docs/images/system.jpg) System |
| ![Temperature graphs](docs/images/graphs-temperatures.jpg) Temperature graphs | ![Fan speed graphs](docs/images/graphs-fan-speed.jpg) Fan speed graphs |
| ![Notification events](docs/images/notifications.jpg) Notification events | ![Device widget](docs/images/dashboard-device.jpg) Device widget |

<img src="docs/images/navbar.jpg" alt="Navigation" width="180"> Navigation

## Requirements

- OpenMediaVault 8 (Debian 13), tested on a TS-253D. OMV 7 is not
  supported (it would need a separate 7.x release line).
- Headers for the running kernel, so DKMS can build the drivers. The
  plugin's Drivers page shows whether they are installed and installs them
  with one click (also for future kernel updates).

## Install

Download the .debs from the latest
[release](https://github.com/nader-eloshaiker/omv-qnap-plugin/releases):
the plugin and the [qnap8528](https://github.com/0xGiddi/qnap8528) driver,
plus the [qnap-qm2](https://github.com/0xGiddi/qnap-qm2) driver for QM2
cards. The driver packages are built from upstream releases and replace a
hand-made `dkms install` of the same driver.

```sh
apt install ./qnap8528-dkms_<version>_all.deb ./qm2mod-dkms_<version>_all.deb \
            ./openmediavault-qnap_<version>_all.deb
```

Then go to **System › QNAP**:

1. **Drivers**: confirm the driver shows as *Loaded*. Optionally tick
   *Load the qnap8528 module at boot* (and *qm2mod* for QM2 cards).
2. **Fan control**: tick *Enable*, pick a mode, then Save and Apply.
3. **Status**: watch the fan speed and temperatures live.
4. **Front panel** / **Power**: status LED and brightness; power recovery,
   EuP mode and `reboot=efi`.
5. **System**: model, serial number and firmware versions.

When the service stops or crashes, the chassis fans go to **full speed**:
qnap8528 has no way to hand the fan back to the EC's automatic mode. QM2 card
fans go back to the card's own controller on a clean stop (full speed after
a crash), and you can leave them to the card permanently by unticking
*Control QM2 expansion card fans*.

### Disks that don't spin down

The plugin never wakes sleeping disks and lets idle ones sleep. Other
software often doesn't: OMV's S.M.A.R.T. power mode *Never*, the
`drivetemp` module, other fan or temperature tools. See
[docs/disk-sleep.md](docs/disk-sleep.md) for what to change and how to
find what wakes a disk.

### Reboot hangs

Some QNAP x86 units hang on reboot under Linux. **Power ›
Use the EFI reboot method** (on by default) adds `reboot=efi` to the kernel command line.
The plugin writes this to `/etc/default/grub.d/openmediavault-qnap.cfg` and
runs `update-grub`, so your own `/etc/default/grub` is not edited. The
change takes effect after the next reboot.

## Development

```sh
make test                      # unit tests against a fake sysfs (any OS with python3)
make docker-deb                # build dist/*.deb in Docker (macOS or any host)
make deb                       # or on a Debian 13 host with debhelper
make deploy NAS=root@NAS_HOST  # install on a test NAS over SSH
```

Documentation starts at [docs/README.md](docs/README.md): architecture,
hardware facts and measurements, fan control, LEDs, OMV integration,
dependencies, build and release, and testing on hardware and in the UI.
[docs/PLAN.md](docs/PLAN.md) has the roadmap.

Using an AI coding assistant? [AGENTS.md](AGENTS.md) routes it to the
right documents, roles and runbooks; see [docs/ai-context.md](docs/ai-context.md).

Useful on the NAS: `qnapd status`, `qnapd info`, `journalctl -u qnapd -f`.

## Credits

- [0xGiddi](https://github.com/0xGiddi) for qnap8528 and qnap-qm2
- Prior art: [omv-panq-plugin](https://github.com/Dag-Rui/omv-panq-plugin),
  [QNAP-EC](https://github.com/Stonyx/QNAP-EC),
  [QNAP_Fan_Control](https://github.com/edddeduck/QNAP_Fan_Control), and the
  [OMV forum guide](https://forum.openmediavault.org/index.php?thread/57619-qnap-temperatures-fan-control/)

Not affiliated with QNAP. Use at your own risk.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
