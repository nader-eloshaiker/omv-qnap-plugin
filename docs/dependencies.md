# Dependencies

## Runtime (declared in `debian/control`)

| Package | Why |
|-|-|
| `openmediavault (>= 7)` | the host application |
| `python3 (>= 3.9)` | qnapd (stdlib only, no pip packages) |
| `smartmontools` | disk temperatures and health (`smartctl -n standby -j`) |
| Recommends `dkms` | the drivers below are DKMS modules |

Used if present, never required: `zpool` (ZFS health for disk LEDs),
`update-grub` (`reboot=efi`), `collectd`/`rrdtool` (OMV's performance
statistics, for the graphs).

## Kernel drivers (installed separately, not packaged yet)

| Driver | Source | Provides | Notes |
|-|-|-|-|
| `qnap8528` | <https://github.com/0xGiddi/qnap8528> (GPL-2.0-or-later) | EC hwmon (fans, temps, PWM), LEDs, VPD/EC sysfs, buttons input | Reference box runs 1.24; upstream 1.27 (Oct 2026). `skip_hw_check=true` only if dmesg shows the chip check failing |
| `qm2mod` | <https://github.com/0xGiddi/qnap-qm2> (GPL-2.0) | QM2 card hwmon (`qm2`), slot LEDs, `model/serial/pic_version/fan_default` | Needs `i2c-algo-bit`. Not for QM2-2S10G1TB02 |
| `ledtrig-timer` | in-tree | `timer` LED trigger for blinking | A module on Debian/Proxmox kernels; `qnapd.service` loads it |
| `coretemp` / `k10temp`, `nvme` | in-tree | CPU and NVMe temperatures | |

Install either driver with DKMS (`make install` = `dkms install .`) and
headers for the **running** kernel: `linux-headers-$(uname -r)` on Debian
kernels, `proxmox-headers-$(uname -r)` on the Proxmox kernel that
omv-extras offers. Load at boot with the plugin's Drivers page (writes
`/etc/modules-load.d/openmediavault-qnap.conf`) or your own file.

Interfaces the plugin relies on: [reference/qnap8528.md](reference/qnap8528.md)
(both drivers).

**Planned (PLAN Phase 4):** `qnap8528-dkms` and `qm2mod-dkms` packages,
pinned to upstream tags, recommended by the plugin; postinst must remove
hand-made DKMS registrations of the same module first.

## Upstream requests worth making

- qnap8528: export the detected model in sysfs (we parse the kernel log);
  README vs source disagree on `BTN_1`/`BTN_2`; add a LICENSE file.
- qnap-qm2: add a LICENSE file; expose the slot `swap` flag in sysfs.

## Build-time

Debian 12/13 with `build-essential debhelper fakeroot`, or any machine
with Docker (`make docker-deb`). Tests need only python3.
