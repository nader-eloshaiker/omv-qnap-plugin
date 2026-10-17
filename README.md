# openmediavault-qnap

An [OpenMediaVault](https://www.openmediavault.org/) plugin that brings
QTS-style hardware control to QNAP NAS devices, using only the open source
[qnap8528](https://github.com/0xGiddi/qnap8528) embedded controller driver.
It does not use QNAP's proprietary binaries.

Primary target is the **TS-253D**. Any model supported by qnap8528 should
work, because all hardware is discovered at runtime.

> **Status: early development (7.0.x, alpha quality).** Phase 1 is scaffolded and
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
| Bundled DKMS drivers (qnap8528, qnap-qm2) | 4 |

## Requirements

- OpenMediaVault 8 (Debian 13), tested on a TS-253D. OMV 7 (Debian 12) is
  targeted but untested.
- The **qnap8528 driver installed** (DKMS):

  ```sh
  apt install build-essential dkms git linux-headers-$(uname -r)
  git clone https://github.com/0xGiddi/qnap8528.git && cd qnap8528
  make install
  modprobe qnap8528     # add skip_hw_check=true only if dmesg shows the chip ID check failing
  ```

- For QM2 cards: the [qnap-qm2](https://github.com/0xGiddi/qnap-qm2)
  driver (`qm2mod`), installed the same way.

## Install

```sh
apt install ./openmediavault-qnap_<version>_all.deb
```

Then go to **System › QNAP**:

1. **Hardware**: confirm the driver shows as *Loaded*. Optionally tick
   *Load the qnap8528 module at boot* and *Skip the chip ID check*.
2. **Fan control**: tick *Enable*, pick a mode, then Save and Apply.
3. **Status**: watch the fan speed and temperatures live.

When the service stops or crashes, the fans go to **full speed**. qnap8528
has no way to hand the fan back to the EC's automatic mode.

### Reboot hangs

Some QNAP x86 units hang on reboot under Linux. Ticking **Hardware ›
Use the EFI reboot method** adds `reboot=efi` to the kernel command line.
The plugin writes this to `/etc/default/grub.d/openmediavault-qnap.cfg` and
runs `update-grub`, so your own `/etc/default/grub` is not edited. The
change takes effect after the next reboot.

## Development

```sh
make test     # unit tests against a fake sysfs (any OS with python3)
make deb      # build the package on a Debian 12/13 host
# or, from macOS/any host with Docker:
docker run --rm -v "$PWD":/src:ro debian:bookworm bash -c \
  'apt-get update -qq && apt-get install -y -qq build-essential debhelper fakeroot >/dev/null &&
   cp -a /src /b && cd /b && dpkg-buildpackage -us -uc -b && ls ../*.deb'
```

Layout:

```
debian/                          packaging (qnapd.service lives here)
srv/salt/omv/deploy/qnap/        salt state applied on "Apply"
usr/sbin/qnapd                   the daemon (python3, stdlib only)
usr/share/openmediavault/
  datamodels/                    config + RPC schemas
  confdb/create.d/               config DB initialisation
  engined/{rpc,module}/          PHP RPC service + engine module
  workbench/                     UI (navigation, routes, pages, dashboard)
tests/                           unit tests
docs/PLAN.md                     design and roadmap
docs/reference/                  research notes (driver, QTS, prior art, OMV)
```

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
