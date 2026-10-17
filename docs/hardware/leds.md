# LEDs

Code: `StatusLed`, `DiskLeds`, `qm2_slot_disks()`, `array_faults()`,
`set_panel_brightness()` in `usr/sbin/qnapd`. Tests: `TestDiskLeds`,
`TestDiskHealth`, `TestQm2.test_slot_leds_*`. Settings (Front panel tab):
`ledstatus`, `leddisk`, `ledbrightness`.

## Driver interfaces

| LED | Values | Blink |
|-|-|-|
| `qnap8528::status` | 0 off, 1 green, 2 red | hardware via `timer` trigger (≈470–790 ms window) |
| `qnap8528::hddN` | 0 off, 1 green, 2 red | hardware via `timer`, 80–140 ms window (we use 100 ms) |
| `qnap8528::usb` | 0/1 (blue) | hardware, 280–470 ms |
| `qnap8528::panel_brightness` | 0–100, dims all front LEDs | — |
| `qm2-<i2c>:green:slotN` | 0 off, 1/2 on | **no** hardware blink: the kernel timer trigger toggles it over the card's I2C |
| `qm2-<i2c>:red:slotN` | 0 off, 1 on, 2 PIC blink | |

- Set the colour (brightness) **before** the `timer` trigger. Writing
  `trigger=none` stops blinking.
- The `timer` trigger is a module (`ledtrig-timer`) on Debian and Proxmox
  kernels. `qnapd.service` loads it in `ExecStartPre`; without it, writing
  `timer` fails with EINVAL and the daemon falls back to a solid colour.

## Status LED

Highest wins: fault (solid red: fan stopped, no sensors, cannot set PWM)
> service failed (blinking red, set by `failsafe` after a crash)
> starting (blinking green) > ok (solid green). Phase 2 adds RAID/ZFS
degraded (blinking red) and rebuild (green/red alternating).

## Disk LEDs (drive bays and QM2 slots)

| State | Bay LED | QM2 slot LEDs |
|-|-|-|
| disk present, idle or asleep | green | green on, red off |
| I/O in the last second | green, 100 ms hardware blink | green, kernel timer blink |
| failed S.M.A.R.T. or faulted ZFS/md member | red | red on, green off |
| empty | off | both off |

- **Bay N = the disk on SATA port N** (`/sys/block/sdX` real path contains
  `/ataN/`), so it survives `sdX` renaming and hot swap (rediscovered every
  control cycle).
- **QM2 slot N = the Nth downstream port of the card's PCIe switch that holds
  an NVMe SSD or nothing** (ports with a NIC are skipped), in PCI order;
  swapped when qm2mod logged `swap=1` for that card (generic QM2-2P cards).
- Activity: `/sys/block/<disk>/stat` read+write I/O counters or in-flight
  requests, polled every 250 ms, held for 1 s. Never wakes a disk.
- Errors (checked every `diskinterval`): `smartctl -n standby -H` for SATA,
  `smartctl -H` for NVMe (critical warning), `zpool status -LP` (not ONLINE,
  or non-zero READ/WRITE/CKSUM), `/proc/mdstat` `(F)` members.
- A ZFS mirror spread over both QM2 slots makes both blink together on
  writes. That is real activity, not a mapping error.
- One thread owns all disk LEDs; clean stop leaves present/error colours,
  `failsafe` stops any blinking.

## Verifying a mapping on new hardware

Use `tools/hw/led-test.sh` (5 s per LED) and ask a person which bay or slot
lit; then read from one disk only (`dd if=/dev/sdX of=/dev/null iflag=direct`)
and confirm which LED blinks. Protocol:
[../testing/hardware-testing.md](../testing/hardware-testing.md).

## Not done yet

Locate (red blink) from the UI, USB LED for One Touch Copy (Phase 3), night
brightness schedule, status LED for degraded/rebuilding arrays (Phase 2).
