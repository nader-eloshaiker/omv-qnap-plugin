# LEDs

Code: `StatusLed`, `status_led_state()`, `storage_health()`, `DiskLeds`,
`qm2_slot_disks()`, `set_panel_brightness()` in `usr/sbin/qnapd`. Tests:
`TestDiskLeds`, `TestDiskHealth`, `TestStorageHealth`,
`TestQm2.test_slot_leds_*`. Settings (Front panel tab): `ledstatus`,
`leddisk`, `ledbrightness`, `volumefull`.

## Driver interfaces

| LED | Values | Blink |
|-|-|-|
| `qnap8528::status` | 0 off, 1 green, 2 red | hardware via `timer` trigger (≈470–790 ms window) |
| `qnap8528::hddN` | 0 off, 1 green, 2 red | hardware via `timer`, 80–140 ms window (we use 100 ms) |
| `qnap8528::usb` | 0/1 (blue) | hardware, 280–470 ms |
| `qnap8528::panel_brightness` | 0–100, dims all front LEDs | — |
| `qm2-<i2c>:green:slotN` | 0 off, 1/2 on | **no** hardware blink: the kernel timer trigger toggles it over the card's I2C |
| `qm2-<i2c>:red:slotN` | 0 off, 1 on, 2 PIC blink (stays dark on the QM2-2P-244A-A1) | `timer` trigger (software) |

- Set the colour (brightness) **before** the `timer` trigger. Writing
  `trigger=none` stops blinking.
- The `timer` trigger is a module (`ledtrig-timer`) on Debian and Proxmox
  kernels. `qnapd.service` loads it in `ExecStartPre`; without it, writing
  `timer` fails with EINVAL and the daemon falls back to a solid colour.

## Status LED

Highest wins:

| State | LED | Cause |
|-|-|-|
| fault | solid red | fan stopped, no sensors, cannot set PWM; a pool FAULTED / UNAVAIL / SUSPENDED; a ZFS pool or local filesystem at least `volumefull` % used (default 95) |
| degraded / service failed | blinking red | a pool DEGRADED or an md array with a missing member (`[U_]`); `failsafe` after a crash |
| rebuilding | green/red alternating (`status/blink_bicolor`; red blink if the driver has `blink_sw_only`) | ZFS resilver, md recovery / resync / reshape |
| starting | blinking green | daemon start |
| ok | solid green | |

A ZFS scrub and an md `check` never change the LED: they are routine
maintenance, not warnings. Pools, arrays and usage are checked every
`diskinterval` from `zpool list -H -o name,health,cap`, `zpool status
-LP`, `/proc/mdstat` and `statvfs` of local ext*/xfs/btrfs/jfs/f2fs
mounts (one per device); none of these wake disks. The reasons show on
the Status page and dashboard widget as a `Storage` row.

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
- Activity blink on bays only for `HW_ACTIVITY_BLINK_MODELS` (TS-253D,
  where the EC blinks in hardware). Elsewhere a blink request falls back
  to software blinking through the EC (a write every ~100 ms per LED,
  flooding the EC lock), so bays show present / error only. QM2 slots
  blink through qm2mod and are not affected.
- One thread owns all disk LEDs; clean stop leaves present/error colours,
  `failsafe` stops any blinking.

## Locate

*System › QNAP › Disks* lists each bay and QM2 slot (device, model, size,
LED state). *Locate* blinks the slot's LED red for 10 minutes; *Stop
locating* ends it early. The RPC (`Qnap.locate`) only records the request
in `/run/qnapd/locate.json` (`{slot id: expiry}`); the disk LED thread
applies it within 0.25 s, so qnapd stays the only writer of LEDs. Bays:
brightness 2 + timer; QM2 slots: red 1 + timer (red 2, the PIC blink,
leaves the LED dark on the QM2-2P-244A-A1). Slot
ids are `bayN` and `<card>-slotN`. Needs *Drive the disk LEDs*.

## Verifying a mapping on new hardware

Use `tools/hw/led-test.sh` (5 s per LED) and ask a person which bay or slot
lit; then read from one disk only (`dd if=/dev/sdX of=/dev/null iflag=direct`)
and confirm which LED blinks. Protocol:
[../testing/hardware-testing.md](../testing/hardware-testing.md).

## Not done yet

USB LED for One Touch Copy (Phase 3), night brightness schedule, Btrfs
device errors in the status LED.
