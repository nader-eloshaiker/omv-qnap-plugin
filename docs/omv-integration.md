# OMV integration

How the plugin hooks into openmediavault 8. Generic OMV plugin rules
are in [reference/omv-plugin-conventions.md](reference/omv-plugin-conventions.md);
this page is what *this* plugin does and what was verified on OMV 8.5.

## Save → Apply flow

1. A form page posts to its RPC setter → `$db->set()` on `conf.service.qnap`.
2. confdb fires `org.openmediavault.conf.service.qnap` → `OMVModuleQnap`
   marks module `qnap` dirty → yellow "pending changes" bar.
3. Apply runs `omv-salt deploy run qnap`: renders `/etc/qnapd/qnapd.json`,
   module-load files, grub drop-in, EC settings, and enables/starts or
   stops `qnapd` (`watch` restarts it when the JSON changes).

## Configuration (`conf.service.qnap`, xpath `.//services/qnap`)

Defaults live only in `usr/share/openmediavault/datamodels/conf.service.qnap.json`.

| Page | Fields | RPC setter |
|-|-|-|
| Fan control | `enable`, `interval`, `fanmode`, `manualpwm`, `minpwm`, `maxpwm`, `hysteresis`, `use{cpu,system,disk,nvme,qm2}`, `{cpu,sys,disk,nvme}{low,high}`, `diskinterval` | `setFanSettings` |
| Front panel | `ledstatus`, `leddisk`, `ledbrightness`, `volumefull` (8.0.2), `lednight`, `lednightstart`, `lednightend`, `lednightbrightness` (8.0.3) | `setFrontPanelSettings` |
| Buttons | `beep`, `usbcopytask`, `resettask` (8.0.4; task = a Scheduled Task uuid or empty) | `setButtonSettings` |
| Power | `powerrecovery`, `eupmode`, `rebootefi` | `setPowerSettings` |
| Drivers | `loadmodule`, `skiphwcheck`, `loadqm2` | `setDriverSettings` |

Every setter validates against its own schema in `datamodels/rpc.qnap.json`
(all fields `required`), so a page can only change its own fields.
Adding a field: follow `.claude/skills/add-setting/SKILL.md`.

## RPC service `Qnap` (`engined/rpc/qnap.inc`)

| Method | Role | Returns |
|-|-|-|
| `getSettings` | admin | whole config (Fan control page) |
| `getHardwareSettings` | admin | config + `driverstatus`, `leds`, `qm2cards`, `rebootefiactive` (Front panel, Power, Drivers pages) |
| `getStatus` | admin | rows `{type, kind, source, name, label, value, unit}` with plain labels for display (`friendlyRows`: "Processor", "Bay 1 drive", ...; Status page, fans & temperatures widget). qnapd's own names stay technical, so graphs and config are unaffected |
| `getGauges` | admin | `{fanduty, qm2duty, cpu, system, disk, nvme, qm2}`: duty % and hottest temperature per source, `null` if absent (gauge widgets) |
| `getDevice` | admin | rows `{property, value}`: model, serial, BIOS, EC firmware, manufactured, boards, QM2 cards (System page, device widget) |
| `getSlots` | admin | bays and QM2 slots `{id, label, device, model, size_gb, state, locate, locate_until}` from the status file (Disks page) |
| `locate` | admin | `{id, enable}`: starts (10 min) or stops a locate request in `/run/qnapd/locate.json`; rejects ids qnapd does not report |
| `getHardwareSettings` | admin | config plus read-only page values: `driverstatus`, `headersstatus`, `qm2cards`, `needssetup` (drivers missing / not running / outdated or no headers; drives the *Set up drivers* button's `enabledConstraint`), `leds`, `rebootefiactive` |
| `setupDrivers` | admin | background job (Drivers page task dialog): `apt-get install` the `header_packages` (best effort) and the bundled `driver_packages` from `/usr/share/openmediavault-qnap/drivers`, stop qnapd, reload the modules (retry `skip_hw_check=true`), set `loadmodule`, `loadqm2` (cards found), `skiphwcheck` (if the retry worked) and `enable`, then `Config.applyChanges` |
| `getFanSettings` | admin | the config plus `manualspeed`, `minspeed`, `maxspeed` in percent (Fan control page); `setFanSettings` takes percent and stores PWM 0-255 |
| `getTasks` | admin | `[{uuid, description}]`: "None" plus OMV's user-defined Scheduled Tasks (Buttons page) |
| `set*Settings` | admin | stores a subset; `setButtonSettings` rejects tasks that no longer exist |

Reads shell out to `qnapd status|info --json` via `\OMV\System\Process`,
wrapped in `try/catch` because `execute()` throws on a non-zero exit.

## Buttons

Salt turns each chosen task uuid into `{"script":
"/var/lib/openmediavault/cron.d/userdefined-<uuid>", "user": <task user>}`
(`usbcopy`, `reset` in `qnapd.json`); the engine module re-applies when a
Scheduled Task changes or is deleted. qnapd only runs scripts matching
that path, via `runuser` for non-root users. Behaviour:
[PLAN.md §7](PLAN.md).

## Notifications

The engine module implements `INotification`: *System › Notification ›
Events* lists "QNAP hardware" (id `qnap`, type Hardware). The salt state
renders `notify: true` into `/etc/qnapd/qnapd.json` when OMV email is
enabled and that event is ticked (off until saved: the page shows a
never-saved event as unticked), and the module
re-applies when either setting changes. qnapd then mails `root`
(`/usr/sbin/sendmail -t`; OMV's postfix maps root to the notification
address):

- when a problem has lasted 60 s (`Notifier.HOLD_SECONDS`): fan or sensor
  fault, critical temperature, a disk failed (S.M.A.R.T. or faulted
  member), a pool or array degraded / rebuilding / failed, a volume full;
- once when the problems clear;
- from `qnapd failsafe` when the daemon stopped unexpectedly.

## Engine module (`engined/module/qnap.inc`)

`getName()` must equal the salt directory (`qnap`). Implements
`IServiceStatus` (shows "QNAP hardware" in the dashboard *Services*
widget; OMV 8 has no generic Diagnostics › Services table).

## Salt

- `srv/salt/omv/deploy/qnap/default.sls`: modules-load file listing
  `qnap8528`/`qm2mod` as enabled, `options qnap8528 skip_hw_check=…`,
  `modprobe` now, EC `power_recovery`/`eup_mode` one-shot writes,
  `/etc/default/grub.d/openmediavault-qnap.cfg` + `update-grub` on change,
  `/etc/qnapd/qnapd.json`, `service.running`/`service.dead`.
- Generated files start with `pillar['headers']['auto_generated']` and
  `['warning']` (verified: OMV writes the same header).
- `srv/salt/omv/deploy/collectd/plugins/qnap.sls`: OMV's collectd state
  includes every `.sls` in that directory, and its cleanup step deletes
  unmanaged `collectd.conf.d/*.conf` on the next deploy.

## Workbench (UI)

| File | Page |
|-|-|
| `navigation.d/system.qnap*.yaml` | System › QNAP tiles, ordered by `position` (Status 10, Fan control 20, Front panel 30, Disks 35, Buttons 37, Power 40, Drivers 50, System 60) |
| `route.d/system.qnap.*.yaml` | URLs `/system/qnap/<page>` |
| `component.d/omv-system-qnap-*-page.yaml` | the pages (formPage / datatablePage) |
| `dashboard.d/qnap.yaml` | fans & temperatures grid |
| `dashboard.d/qnap-device.yaml` | device datatable |
| `dashboard.d/qnap-{temperature,fanspeed}-rrd.yaml` | history graphs (`type: rrd`, `kind` = image prefix) |
| `dashboard.d/qnap-gauge-*.yaml` | round gauges (`type: chart`, `chart.type: gauge`, fixed min/max): fan duty, QM2 fan duty, CPU / system / disk / NVMe temperature, each from `getGauges` |
| `*/diagnostics.performance-statistics.qnap.yaml`, `component.d/omv-diagnostics-performance-statistics-qnap-rrd-page.yaml` | Performance statistics › QNAP |

UI gotchas seen on OMV 8.5:
- A form `divider` ignores `modifiers`; it cannot be hidden.
- Browsers cache the workbench config: hard-reload (Cmd/Ctrl+Shift+R)
  after deploying or new routes 404.
- Every package install restarts engined, which logs the browser out.
- Dashboard tiles truncate long labels (≈10 characters): keep labels short.
- YAML labels: avoid `": "` inside `_()` strings.

## Graphs

`qnapd collectd` (collectd exec plugin, as `nobody`) reads the status file
and prints `PUTVAL "<host>/exec-qnap/<type>-<instance>"`:
`temperature-{cpu,system,disk,nvme,qm2}` (hottest per source),
`fanspeed-<fan>`, `percent-<pwm>`. The mkrrdgraph plugin
(`mkrrdgraph/plugins.d/qnap.py`) draws `exec-qnap-{temperature,fanspeed,duty}-<period>.png`;
OMV's cron regenerates them every 15 min. No extra hardware access.

## Packaging hooks

See [build-and-release.md](build-and-release.md) for postinst/postrm order,
migrations and versions.
