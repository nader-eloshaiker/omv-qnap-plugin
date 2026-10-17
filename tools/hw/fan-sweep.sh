#!/bin/bash
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# fan-sweep.sh <hwmon name: qnap8528|qm2> [hold seconds]: run on the NAS,
# with qnapd stopped.
# Steps pwm1 down 255->0 then back up until the fan restarts, printing
# PWM written / read back, average RPM and the hottest sensor.
# Aborts to PWM 255 if a sensor passes its limit: CPU 85, NVMe/QM2 70,
# EC/other 50 (drivetemp is skipped: reading it may wake disks).
NAME=$1; HOLD=${2:-15}
for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name)" = "$NAME" ] && H=$h; done
[ -n "$H" ] || { echo "no hwmon $NAME"; exit 1; }
trap 'echo 255 > $H/pwm1; echo "restored PWM 255"' EXIT

# Prints: <hottest C> <sensor> <over-limit sensor or ->
hottest() {
  local max=0 who= over=- t h n lim
  for h in /sys/class/hwmon/hwmon*; do
    n=$(cat $h/name)
    case $n in
      drivetemp) continue ;;
      coretemp|k10temp|acpitz) lim=85 ;;
      nvme|qm2) lim=70 ;;
      *) lim=50 ;;
    esac
    for f in $h/temp*_input; do
      t=$(cat $f 2>/dev/null) || continue
      [ "$t" -gt "$max" ] && { max=$t; who="$n/$(basename $f)"; }
      [ "$((t / 1000))" -ge "$lim" ] && over="$n/$(basename $f)=$((t / 1000))C"
    done
  done
  echo "$((max / 1000)) $who $over"
}

step() {
  local pwm=$1 sum=0 i r
  echo "$pwm" > $H/pwm1
  sleep $((HOLD - 6))
  for i in 1 2 3; do r=$(cat $H/fan1_input); sum=$((sum + r)); sleep 2; done
  set -- $(hottest)
  printf "%-5s pwm=%3s readback=%3s rpm=%5s hottest=%sC (%s)\n" "$DIR" "$pwm" "$(cat $H/pwm1)" "$((sum / 3))" "$1" "$2"
  if [ "$3" != - ]; then echo "ABORT: $3"; exit 2; fi
  LAST_RPM=$((sum / 3))
}

echo "== $NAME ($H), hold ${HOLD}s"
DIR=down
for p in 255 224 192 160 128 112 96 80 72 64 56 48 40 32 24 16 8 0; do step $p; done
DIR=up
for p in 8 16 24 32 40 48 56 64 72 80 96; do
  step $p
  [ "$LAST_RPM" -gt 0 ] && break
done
