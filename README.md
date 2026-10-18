# openmediavault-qnap

An [OpenMediaVault](https://www.openmediavault.org/) plugin that brings
QTS-style hardware control to QNAP NAS devices, using only the open source
[qnap8528](https://github.com/0xGiddi/qnap8528) embedded controller driver.
It does not use QNAP's proprietary binaries.

Primary target is the **TS-253D**. Any model supported by qnap8528 should
work, because all hardware is discovered at runtime.

> **Status: early development (8.0.x, alpha quality).** Phase 1 is scaffolded and
> unit-tested but not yet validated on hardware. See
> [docs/PLAN.md](docs/PLAN.md).

## Features

| | Phase |
|-|-|
| Smart Fan: Quiet / Normal / Performance / Custom curve / Manual | 1 |
| Temperature sources: CPU, EC system sensors, HDD (S.M.A.R.T., no spin-up), NVMe | 1 |
| Hysteresis, critical-temperature override, fan-failure detection, full-speed failsafe | 1 |
| Status LED (green ok / red fault / blinking red on service failure) | 1 |
| Front panel LED brightness, power recovery, EuP mode | 1 |
| Load qnap8528 at boot (with `skip_hw_check`), `reboot=efi` kernel option | 1 |
| Status page and dashboard widget for fans and temperatures | 1 |
| RAID-aware status LED, disk LEDs (present/activity/error/locate), LED schedule, notifications | 2 |
| USB Copy and Reset buttons, USB LED, beeper | 3 |
| QM2 expansion cards (qnap-qm2): card fan control from its slot and NVMe temperatures | 1 |
| QM2 slot LEDs (present / error / locate) | 2 |
| DKMS driver packages (qnap8528, qnap-qm2) | 2 |

## Requirements

- OpenMediaVault 8 (Debian 13), tested on a TS-253D. OMV 7 is not
  supported (it would need a separate 7.x release line).
- Headers for the running kernel, so DKMS can build the drivers:
  `linux-headers-amd64` on the Debian kernel, `proxmox-default-headers`
  on the Proxmox kernel.

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
