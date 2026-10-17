#!/bin/bash
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# led-test.sh <led> [seconds]: run on the NAS. Lights one LED for a mapping
# check (default 5 s), then restores its previous brightness and trigger.
#   led-test.sh qnap8528::hdd1        bay LED, shown red
#   led-test.sh qm2-1:green:slot1     QM2 slot LED
# Stop qnapd first if it drives the LED (disk LEDs), or it may overwrite it.
L=/sys/class/leds/$1
[ -d "$L" ] || { echo "no such LED: $1"; ls /sys/class/leds; exit 1; }
old_b=$(cat $L/brightness)
old_t=$(grep -o '\[[^]]*\]' $L/trigger | tr -d '[]')
max=$(cat $L/max_brightness)
case $1 in qnap8528::hdd*) on=2;; *) on=1;; esac   # bays: red stands out
[ $on -gt $max ] && on=$max
echo none > $L/trigger
echo $on > $L/brightness
sleep "${2:-5}"
echo none > $L/trigger
echo $old_b > $L/brightness
[ "$old_t" != none ] && echo $old_t > $L/trigger
echo "$1 done"
