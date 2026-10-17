# Testing on real hardware

Unit tests cover logic against a fake sysfs. Anything involving OMV,
drivers, fans or LEDs must also be checked on a NAS. These are the
protocols that worked on the reference TS-253D.

## Access

- SSH as root with a key: `export NAS=root@NAS_HOST`. Agents must not type
  passwords; a person logs in, or keys are set up beforehand.
- The OMV web UI runs on the port set in OMV (the reference box uses SSL
  only on a non-default port); see [ui-validation.md](ui-validation.md).

## Deploy

```sh
make test && make docker-deb && make deploy NAS=$NAS
```

`tools/nas-deploy.sh` copies the .deb, checks its sha256 and runs
`apt-get install --reinstall`. Then check:

```sh
ssh $NAS 'systemctl is-active qnapd; journalctl -u qnapd -n 20 --no-pager; qnapd status; qnapd info'
```

Every install restarts `qnapd` (chassis fan briefly to full speed) and
OMV's engined (web UI sessions are logged out).

## Safety rules

- **Ask the owner before** deliberately slowing or stalling fans, killing
  the daemon, rebooting, toggling `reboot=efi`, or changing EC power
  settings. Tell them what they will hear or see.
- While holding fans by hand the daemon's critical protection is off: use
  the scripts below, which abort on CPU 85 °C, NVMe/QM2 70 °C, EC 50 °C.
- Never read `drivetemp` or run `smartctl` without `-n standby` on HDDs.
- Stop `qnapd` before writing PWM by hand (`systemctl stop qnapd`), and
  start it again afterwards; it otherwise overwrites your values.
- Close the OMV dashboard while measuring: its widgets load the CPU.

## Protocols

### LED mapping (needs a person looking at the box)
Announce each step *before* it starts; 5 seconds per LED is enough.
```sh
scp tools/hw/* $NAS:/root/
ssh $NAS '/root/led-test.sh qnap8528::hdd1 5'       # which bay lit?
ssh $NAS '/root/led-test.sh qm2-1:green:slot1 5'    # which slot lit? (rear bracket)
ssh $NAS 'timeout 5 dd if=/dev/sda of=/dev/null bs=1M iflag=direct'   # which bay blinks?
```

### Buttons (needs a person at the box)
```sh
ssh $NAS 'python3 /root/button-test.py 20'   # press one button per run
```
Prints each press and release with the hold time. One button per run
avoids guessing which press was which. **Never press the power button**
(ACPI: it shuts the NAS down). The Reset button is a rear pinhole.

### Fan PWM → RPM sweep
```sh
ssh $NAS 'systemctl stop qnapd; /root/fan-sweep.sh qnap8528 15; /root/fan-sweep.sh qm2 15; systemctl start qnapd'
```
Prints RPM per PWM going down, then up until the fan restarts. Floors
come from the restart PWM plus margin.

### Noise check (needs a person at the box)
```sh
ssh $NAS 'systemctl stop qnapd; /root/fan-hold.sh 48 64 30; /root/fan-hold.sh 64 64 30; systemctl start qnapd'
```
Arguments: chassis PWM, QM2 PWM, seconds. Announce each step first.

### Failsafe
`ssh $NAS 'kill -9 $(pidof -x qnapd)'` → chassis 255, QM2 255, status LED
blinking red; systemd restarts the daemon after 10 s (the LED then goes
green). A clean `systemctl stop qnapd` → chassis 255, QM2 back to the card
(≈1260 RPM on a QM2-2P-244A-A1).

### Disk standby
Remove anything else polling disks first (e.g. tempmon sensors that run
`smartctl` without `-n standby`). Put a disk to sleep by hand rather than
waiting for spindown: `smartctl -s standby,now /dev/sdX`. Check its state
without waking it: `smartctl -n standby -i /dev/sdX` exits 2 in standby.
Watch it across three `diskinterval`s: it must stay in standby, `qnapd
status` must skip its temperature, its bay LED must stay solid green.

If it wakes, find out why before blaming qnapd:
- `/sys/block/sdX/stat` read/write counters: S.M.A.R.T. queries do not
  count as I/O, so moving counters mean a real read or write.
- `journalctl -u smartmontools`: OMV's smartd with **Power mode "Never"**
  (`-n never` in `/etc/smartd.conf`) checks sleeping disks every 30 min
  and wakes them. Set *Storage › S.M.A.R.T. › Settings › Power mode* to
  *Standby* for spindown to work.
- `zpool iostat <pool> 10`: pool I/O.
- OMV applies spindown/APM with `hdparm`; if it is not installed the disk
  settings have no effect (seen on the reference box).

### Power loss / boot
After a reboot: `qnapd` active with `NRestarts=0`, journal shows control
within seconds of boot, `ledtrig_timer` loaded, LEDs green, pools healthy.

## Reporting

Record measured values with model, date and conditions in
[../hardware/ts-253d.md](../hardware/ts-253d.md) (or a new file per model)
and tick PLAN.md. Owners of other models use `tools/model-test.py`
instead; see [model-testing.md](model-testing.md). No IPs, host names or serial numbers in the repo.
