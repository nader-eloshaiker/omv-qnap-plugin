# QTS hardware behaviour (what we are replicating)

Sources: QNAP TS-x53D User Guide pp. 42–46
(<https://eu1.qnap.com/TechnicalDocument/Storage/SMB%20NAS/ts-x53d/ts-x53d-ug-en-us.pdf>),
QTS 5.1 / 4.2 / 5.0 online docs. TS-253D: Celeron J4125, one 70 mm 12 V
fan, 17.1 dB(A) at low speed, 0–40 °C ambient.

## Smart Fan (Control Panel › System › Hardware › Smart Fan)

- **Automatic** (default): QTS monitors system, disk and CPU temperatures.
  Modes: **Quiet**, **Normal** (default), **Performance**. Some versions
  allow user-defined temperature rules (target temp / lowest speed / full
  speed above X).
- **Manual**: fixed speed (low / medium / high or a slider).
- Some models control system and CPU fans separately.
- QTS shuts down when a model-specific temperature limit is exceeded.
- QNAP publishes **no numeric thresholds**. Known: `ADJUST_SYS_TEMP=-2` in
  QTS `hal_util.conf` (EC chassis temp reads ~2 °C high); the EC has its
  own auto modes (`ec_sys_set_tfan_auto` / `qfan_auto` in the HAL) which
  qnap8528 does not expose.

## Status LED

| LED | Meaning |
|-|-|
| Green/red alternating (0.5 s) | Formatting, initialising, firmware update, RAID rebuild, capacity expansion, RAID migration |
| Solid red | Invalid drive, volume full/nearly full, **system fan not working**, R/W error, bad sector, degraded read-only, hardware self-test error |
| Red blinking (0.5 s) | Degraded (one drive failed in RAID 1/5/6) |
| Green blinking (0.5 s) | Starting up, not configured, drive not formatted |
| Solid green | Ready |
| Off | All drives in standby |

## Drive LEDs

| LED | Meaning |
|-|-|
| Green | Ready |
| Green blinking | Being accessed |
| Red | R/W error |
| Red blinking | Locate, or R/W error during access |
| Off | No drive / not initialised |

## Other LEDs

- LAN: orange blinking on access; solid orange on error (NIC-driven, not EC).
- USB One Touch Copy: blue blinking 2×/s while mounting/copying/unmounting;
  solid when mounted; off when no device.
- Brightness: "Turn on LED" + brightness level + schedule (Control Panel ›
  System › Hardware › General) → qnap8528 `panel_brightness`.

## Buttons

- Power: press = on; hold 1.5 s = clean shutdown; hold 5 s = force off.
  (Handled by ACPI/systemd-logind on OMV.)
- Reset: hold 3 s = basic reset (admin password, network → DHCP, port
  8080, …); hold 10–15 s = advanced reset (factory defaults, data kept).
  QTS can disable the reset switch.
- USB One Touch Copy: incremental copy between front USB and the NAS.

## Buzzer

| Pattern | Meaning |
|-|-|
| 1 short (0.5 s) | Startup, shutdown, reset pressed, firmware updated |
| 3 short | One Touch Copy failed |
| 3 long (1.5 s), every 5 min | **System fan failure** |
| 2 long | Volume full, degraded, rebuild started, drive inserted/removed |
| 1 long | Forced shutdown, or powered on and ready |

## Power

- Power recovery: restore previous state / power on / stay off
  (→ qnap8528 `ec/power_recovery` 2 / 1 / 0).
- EuP mode: minimal standby power; disables WOL and power recovery
  (→ `ec/eup_mode`).
