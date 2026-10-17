#!/bin/bash
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# fan-hold.sh <chassis pwm> <qm2 pwm> <seconds>: run on the NAS, with qnapd
# stopped. Holds the chassis (qnap8528) and first QM2 card fan at fixed PWM
# for a listening test, then prints RPM. Aborts and starts qnapd if a
# sensor passes its limit (CPU 85, NVMe/QM2 70, EC/other 50 C; drivetemp is
# skipped because reading it may wake disks).
for h in /sys/class/hwmon/hwmon*; do
  case $(cat $h/name) in qnap8528) C=$h;; qm2) Q=${Q:-$h};; esac
done
[ -n "$C" ] || { echo "qnap8528 hwmon not found"; exit 1; }
echo "$1" > $C/pwm1
[ -n "$Q" ] && echo "$2" > $Q/pwm1
end=$((SECONDS + $3))
while [ $SECONDS -lt $end ]; do
  for h in /sys/class/hwmon/hwmon*; do
    n=$(cat $h/name)
    case $n in drivetemp) continue;; coretemp|k10temp|acpitz) lim=85;; nvme|qm2) lim=70;; *) lim=50;; esac
    for f in $h/temp*_input; do
      t=$(( $(cat $f 2>/dev/null || echo 0) / 1000 ))
      if [ $t -ge $lim ]; then echo "ABORT $n $t C"; systemctl start qnapd; exit 2; fi
    done
  done
  sleep 2
done
echo "chassis pwm=$1 rpm=$(cat $C/fan1_input)${Q:+  qm2 pwm=$2 rpm=$(cat $Q/fan1_input)}"
