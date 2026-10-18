---
title: QNAP fan control, LEDs and buttons for OpenMediaVault
description: >-
  Replace QNAP QTS with OpenMediaVault and keep your hardware working. A free,
  open source OMV plugin for QNAP NAS fan control (no more loud fans), status
  and disk LEDs, buttons, temperature graphs and alerts. Verified on the TS-253D.
---

# Run OpenMediaVault on your QNAP, with quiet fans and working lights

Want to leave QNAP QTS for a free, open Linux NAS system? You can install
[OpenMediaVault](https://www.openmediavault.org/) (OMV) on most QNAP NAS
boxes. The catch: QNAP's fans, lights and buttons are run by a special
chip that a normal Linux system doesn't know how to talk to.

So after the switch the fans often scream at full speed (or don't speed
up when they should), the status and disk lights stay dark, and the
buttons do nothing.

**openmediavault-qnap fixes that.** It is a free plugin that adds a
**System › QNAP** section to the OMV web interface, so your QNAP behaves
the way it did under QTS. No command line needed.

![OpenMediaVault dashboard on a QNAP TS-253D with fan duty and temperature gauges](images/dashboard-gauges.jpg)

[Download the latest release](https://github.com/nader-eloshaiker/omv-qnap-plugin/releases/latest){: .btn }
[Moving from QTS to OMV](guide/qts-to-omv.md){: .btn }
[Source on GitHub](https://github.com/nader-eloshaiker/omv-qnap-plugin){: .btn }

## What you get

- ✅ **Quiet fans that react to heat.** Smart Fan presets like QTS (Quiet,
  Normal, Performance), your own curve, or a fixed speed. The fans follow
  the CPU, the system sensors, your hard disks and NVMe SSDs.
- ✅ **Disks can still sleep.** The plugin never wakes a sleeping disk to
  read its temperature.
- ✅ **Lights that mean something.** The status light turns red or blinks
  when a fan fails or a disk or pool has a problem. Disk bay lights show
  activity and errors. Blink a bay's light to find the right disk.
  Dim the front panel at night.
- ✅ **Buttons and beeps.** Make the USB Copy and Reset buttons run an OMV
  task. Optional QTS-style beeps at boot and on problems.
- ✅ **See what's happening.** Live fan and temperature status, dashboard
  gauges, history graphs by hour, day, week, month and year.
- ✅ **Email alerts** when a fan stops, something overheats or a disk or
  pool fails, using OMV's own notifications.
- ✅ **QM2 expansion cards.** The card's fan follows its NVMe temperatures,
  and its slot lights work.
- ✅ **Power settings**: what to do after a power cut, EuP mode, and a fix
  for QNAP boxes that hang on reboot under Linux.

See the [full feature list and screenshots](https://github.com/nader-eloshaiker/omv-qnap-plugin#features).

## Quick start

You need OpenMediaVault 8 already installed on your QNAP. If you are still
on QTS, start with the guide:
**[Moving from QNAP QTS to OpenMediaVault](guide/qts-to-omv.md)**.

1. Download **one file**, `openmediavault-qnap_<version>_all.deb`, from the
   [latest release](https://github.com/nader-eloshaiker/omv-qnap-plugin/releases/latest).
2. In the OMV web interface open **System › Plugins**, click **Upload**,
   choose the file, then select the plugin and click **Install**.
3. Open **System › QNAP › Drivers** and click **Set up drivers**. It
   installs the drivers and everything they need, and turns on fan control.
4. Open **System › QNAP › Status** and listen to your NAS go quiet.

## Questions

### Will it work on my QNAP model?

It is fully tested on the **TS-253D** (with a QM2-2P-244A-A1 card). The
plugin is built on the open source
[qnap8528](https://github.com/0xGiddi/qnap8528) driver, which supports
well over a hundred Intel and AMD based QNAP models, for example the
TS-251D, TS-451D, TS-453D, TS-464, TS-473A, TS-673A, TS-873A, TS-877 and
many TVS models. The plugin finds your hardware on its own, so these
should work, but they have not been tested with the plugin yet.
[Tested models](hardware/models.md) lists what has been checked.

If you try it on another model, a short
[test report](testing/model-testing.md) helps everyone. ARM based QNAP
models are not on the driver's list.

### Is it safe? What happens if something goes wrong?

The plugin is designed to fail safe. If its service stops or crashes, the
chassis fans go to **full speed**, so the NAS is loud but never too hot.
It also watches for a stopped fan and for temperatures that get too high,
and emails you. It only uses the open source drivers and never runs
QNAP's own programs.

### Do I need Linux skills?

Not for the plugin: you install and set it up in the OMV web interface.
Installing OpenMediaVault itself takes a USB stick, a keyboard and a
screen (or some patience). The
[guide](guide/qts-to-omv.md) walks you through it.

### Can I go back to QTS?

Usually, yes. On most models QTS lives on a small flash chip inside the
NAS, and OMV is installed on a separate drive, so QTS stays where it is.
Your data disks are set up fresh for OMV, though, so back up your data
before you switch, and again before you switch back. The
[guide](guide/qts-to-omv.md) has the details.

### Is it free?

Yes. It is free and open source under the GPL-3.0 license, like
OpenMediaVault and the drivers it uses. It is a community project, not
affiliated with QNAP.

### Where do I get help or report a problem?

Open an [issue on GitHub](https://github.com/nader-eloshaiker/omv-qnap-plugin/issues).
Developers can start at the [documentation index](README.md).
