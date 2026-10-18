# Dependencies

## Runtime (declared in `debian/control`)

| Package | Why |
|-|-|
| `openmediavault (>= 8)` | the host application (OMV 8, Debian 13) |
| `python3 (>= 3.9)` | qnapd (stdlib only, no pip packages) |
| `smartmontools` | disk temperatures and health (`smartctl -n standby -j`) |
| Recommends `qnap8528-dkms`, Suggests `qm2mod-dkms` | the drivers below |

Used if present, never required: `zpool` (ZFS health for disk LEDs),
`update-grub` (`reboot=efi`), `collectd`/`rrdtool` (OMV's performance
statistics, for the graphs).

## Kernel drivers (`qnap8528-dkms`, `qm2mod-dkms`, released with the plugin)

| Driver | Source | Provides | Notes |
|-|-|-|-|
| `qnap8528` | <https://github.com/0xGiddi/qnap8528> (GPL-2.0-or-later) | EC hwmon (fans, temps, PWM), LEDs, VPD/EC sysfs, buttons input | Packaged: 1.27. `skip_hw_check=true` only if dmesg shows the chip check failing |
| `qm2mod` | <https://github.com/0xGiddi/qnap-qm2> (GPL-2.0) | QM2 card hwmon (`qm2`), slot LEDs, `model/serial/pic_version/fan_default` | Needs `i2c-algo-bit`. Not for QM2-2S10G1TB02 |
| `ledtrig-timer` | in-tree | `timer` LED trigger for blinking | A module on Debian/Proxmox kernels; `qnapd.service` loads it |
| `coretemp` / `k10temp`, `nvme` | in-tree | CPU and NVMe temperatures | |

`drivers/build.sh` (`make drivers` / `make docker-drivers`, and CI on
every build) packages each driver from the upstream commit pinned in
`drivers/<name>/source` with `dh-dkms`; the release attaches the .debs.
DKMS builds the module on the NAS, so it needs headers for the
**running** kernel and for each kernel update: the Drivers page shows
whether they are there and *Install kernel headers* installs
`proxmox-headers-<release>` + `proxmox-headers-X.Y` (Proxmox kernel) or
`linux-headers-<release>` + `linux-headers-<flavour>` (Debian kernel). The
package's preinst removes a hand-made `dkms install .` of the same module
(an unowned `/usr/src/<name>-<version>` registered in DKMS). New modules
load at the next boot, or after stopping qnapd and reloading them. Load at
boot with the plugin's Drivers page (writes
`/etc/modules-load.d/openmediavault-qnap.conf`) or your own file.

To update a driver: set `VERSION` and `COMMIT` in `drivers/<name>/source`
to the new upstream tag, reset `REVISION` to 1 (bump it for packaging-only
changes), and release the plugin.

Interfaces the plugin relies on: [reference/qnap8528.md](reference/qnap8528.md)
(both drivers).

## Upstream requests worth making

- qnap8528: export the detected model in sysfs (we parse the kernel log);
  fix the source comment that swaps `BTN_1`/`BTN_2` (the README is right,
  verified on a TS-253D); add a LICENSE file.
- qnap-qm2: add a LICENSE file; expose the slot `swap` flag in sysfs.

## Build-time

Debian 13 with `build-essential debhelper fakeroot`, or any machine
with Docker (`make docker-deb`). Tests need only python3.
