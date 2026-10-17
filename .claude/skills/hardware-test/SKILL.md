---
name: hardware-test
description: Verify fans, LEDs, failsafe or disk standby behaviour on a real QNAP NAS with the repo's test scripts - LED mapping checks, PWM/RPM sweeps, noise checks, failsafe and power-loss checks. Use when a change affects hardware behaviour or when supporting a new model.
---

# Hardware test

Full protocols and safety limits: `docs/testing/hardware-testing.md`.
Needs `NAS=root@NAS_HOST` (SSH key) and, for LED and noise checks, a
person at the box.

Before you start:
- Get the owner's consent for anything that slows/stalls fans, kills the
  daemon or reboots. Say what they will see or hear.
- Close the OMV dashboard in any browser (it loads the CPU).
- Copy the scripts: `scp tools/hw/*.sh $NAS:/root/`

Pick what the change needs:

| Check | Command (on the NAS) | Needs a person |
|-|-|-|
| LED mapping | `/root/led-test.sh qnap8528::hdd1 5` (then hdd2, `qm2-N:green:slotM`) | yes: which bay/slot lit |
| Activity mapping | `timeout 5 dd if=/dev/sdX of=/dev/null bs=1M iflag=direct` | yes: which LED blinks |
| PWM→RPM sweep | `systemctl stop qnapd; /root/fan-sweep.sh qnap8528 15; /root/fan-sweep.sh qm2 15; systemctl start qnapd` | no |
| Noise | `systemctl stop qnapd; /root/fan-hold.sh <chassis> <qm2> 30; systemctl start qnapd` | yes: audible? |
| Failsafe | `kill -9 $(pidof -x qnapd)`; check pwm1 = 255, status LED blinking red; restarts in 10 s | look at LED |
| Clean stop | `systemctl stop qnapd`; chassis 255, QM2 back to card; `systemctl start qnapd` | no |

Rules:
- Announce every LED or noise step before it starts; 5 s per LED.
- Always `systemctl start qnapd` afterwards, even after an abort.
- Record results with model and date in `docs/hardware/` (no IPs, host
  names or serial numbers) and tick `docs/PLAN.md`.
