# Letting disks sleep

What keeps hard disks awake on an OMV box with this plugin, and how to
find the culprit. Marked **[measured]** where seen on the reference
TS-253D (OMV 8, ZFS mirror of two SATA disks, 2026-10-17/18); the rest is
general Linux / OMV behaviour that has not been measured here.

## How a disk falls asleep

OMV sets the spindown time (Storage › Disks › edit: *Spindown time*,
*Advanced Power Management*) and applies it at boot with the
`smartctl-hdparm` service (`smartctl --set=standby,N`; OMV 8 does not use
`hdparm`). The drive then sleeps after that long **without any command**.
Not only reads and writes count: any S.M.A.R.T. query to an awake drive,
even `smartctl -n standby`, restarts its standby timer **[measured]**. So
a disk only sleeps if nothing touches it for the whole spindown time.

## What the plugin does

qnapd never wakes a sleeping disk and, since 8.0.1, does not keep an
idle one awake **[measured]**:

- temperatures and health with `smartctl -n standby` (skips sleeping
  disks), and only for disks that did I/O since the last check, or every
  30 minutes;
- activity from `/sys/block/*/stat`, pool health from `zpool status` /
  `/proc/mdstat` (kernel state, no disk access);
- never the `drivetemp` hwmon driver.

With qnapd running, the reference disks reach standby 12–14 minutes
after their last wake with a 10-minute spindown **[measured]** (drives
add a little to the nominal time).

## Keeps disks awake: change or remove

| Cause | Why | What to do |
|-|-|-|
| OMV S.M.A.R.T. *Power mode: Never* | smartd checks every disk on each check interval (OMV default 30 min), waking sleeping ones **[measured]** | Storage › S.M.A.R.T. › Settings: *Power mode* = **Standby** (skips sleeping disks) |
| `drivetemp` kernel module | every read of its hwmon temperature sends a command to the drive; whatever reads it (OMV's Sensors widget, `sensors`, collectd's sensors plugin, Netdata, fan scripts) keeps the disk awake or wakes it | Don't load it: delete its line from `/etc/modules-load.d/*.conf`. The plugin already shows disk temperatures without it |
| Other temperature or fan tools (tempmon scripts, hddtemp, hddfancontrol, other fan plugins) | usually `smartctl` without `-n standby`, which wakes the disk **[measured: a tempmon setup did]** | Remove them; qnapd does fan control from disk temperatures itself |
| An older openmediavault-qnap (< 8.0.1) | queried idle disks every minute **[measured]** | Update |
| Scheduled S.M.A.R.T. self-tests, scrubs, snapshots, rsync / backup jobs | wake the disks by design | Schedule them together, at a time the disks may wake |

## Often keeps disks awake: check if you use it

Not measured on the reference box; common causes on any Linux NAS:

- **Apps writing to the data pool**: Docker containers (databases,
  logs, downloaders), media servers scanning libraries (Plex, Jellyfin),
  Syncthing, Nextcloud. Put their config and data on an SSD (the boot
  disk or an NVMe pool) and keep only bulk media on the HDDs.
- **ZFS `atime=on`**: reading a file writes its access time. Use
  `zfs set atime=off <pool>` (or `relatime=on`).
- **Clients browsing shares**: macOS Spotlight and Finder, Windows
  thumbnailing, DLNA. Spotlight can be turned off per SMB share
  (`spotlight = no`, the OMV default).
- **Swap or logs on a data disk.** OMV keeps both on the system disk by
  default.

## Finding what wakes a disk

1. Note the disk's I/O counters, wait, compare. Reading them does not
   touch the disk:

   ```sh
   awk '{print $1 + $5}' /sys/block/sda/stat
   ```

   A rising number means something read or wrote. Flat but still awake
   means a command such as `smartctl` (step 3).
2. File access by process: `fatrace -f W` (Debian package `fatrace`)
   or `iotop -oa`.
3. Commands: look for timers and services that run `smartctl`
   (`grep -rl smartctl /etc/cron* /etc/systemd`), and check the
   S.M.A.R.T. power mode above.
4. Check the state **once, at the end**: `smartctl -n standby -i
   /dev/sda` exits with status 2 when the disk is asleep. Every check on
   an awake disk restarts its timer, so polling it keeps it awake.

OMV's *Diagnostics › Performance statistics › Disk I/O* graphs show
gaps or flat lines while disks sleep. They read kernel counters and do
not wake disks.
