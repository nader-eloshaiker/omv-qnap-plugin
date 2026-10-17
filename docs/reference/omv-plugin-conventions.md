# OMV plugin conventions (cheat sheet)

Distilled from openmediavault-fail2ban, -cputemp, -wol, -omvextrasorg
(OMV 7 `7.x` branches and OMV 8 `master`) and core
`deb/openmediavault-snmp`. Official docs:
<https://docs.openmediavault.org/en/latest/development/plugins.html>.
(openmediavault-sensors is OMV 4 / ExtJS — do not copy.)
Also [openmediavault-tempmon](https://github.com/OpenMediaVault-Plugin-Developers/openmediavault-tempmon)
8.0.5 (`207fd51`, Jul 2026, OMV 8 only), the current reference for
collectd/RRD graphs and salt-generated workbench files.

## How Save → Apply works

1. Form posts to RPC `set…` → `$db->set($object)`.
2. confdb emits `OMV_NOTIFY_MODIFY org.openmediavault.conf.service.qnap`.
3. Our engined module (`OMVModuleQnap::bindListeners`) calls `setDirty`,
   the UI shows the yellow "pending changes" bar.
4. Apply → `omv-salt deploy run qnap` (module `getName()` **must** equal
   the salt directory `srv/salt/omv/deploy/qnap`).

## Files in this repo and their role

| Path | Role |
|-|-|
| `debian/control` | `Architecture: all`, `XB-Plugin-Section`, `Depends: openmediavault (>= 7)` |
| `debian/compat` = 13 | Works on Bookworm and Trixie builders (OMV 8 plugins use `debhelper-compat (= 14)` instead) |
| `debian/triggers` | `activate restart-engined` |
| `debian/postinst` | `dpkg-trigger update-workbench`, `omv-confdbadm create/migrate`, `omv-salt deploy run` |
| `debian/postrm` | purge → `omv_config_delete` (not omv-confdbadm; the model is already gone) |
| `debian/rules` | `dh $@`; `dh_installsystemd --no-enable --no-start` (salt owns the service) |
| `datamodels/conf.service.qnap.json` | Config schema + **defaults** |
| `datamodels/rpc.qnap.json` | RPC param schemas (`rpc.qnap.<method lowercase>`) |
| `confdb/create.d/conf.service.qnap.sh` | `omv-confdbadm read --defaults … \| omv-confdbadm update … -` |
| `confdb/migrations.d/conf.service.qnap_<ver>.sh` | Add/rename keys on upgrade (`omv_config_add_key`) |
| `engined/rpc/qnap.inc` | `OMVRpcServiceQnap extends \OMV\Rpc\ServiceAbstract` |
| `engined/module/qnap.inc` | `OMVModuleQnap extends \OMV\Engine\Module\ServiceAbstract implements IListener, IServiceStatus` |
| `srv/salt/omv/deploy/qnap/{init,default}.sls` | Render config, manage service (`service.running` / `service.dead`) |
| `workbench/{navigation,route,component,dashboard}.d/*.yaml` | UI |

## Gotchas

- YAML labels are plain scalars: `label: _("A: b")` breaks parsing —
  avoid `": "` inside `_()` strings (or quote the whole scalar).
- Salt file modes: quote them (`mode: '0644'`) — required on OMV 8's Salt.
- `\OMV\System\Process` does not escape arguments; validate input.
- **Salt caches states by modification time.** Its file server
  (`/var/cache/salt/minion/files`) only re-reads a `.sls` whose mtime
  changed, and dpkg stamps files with the changelog date
  (`SOURCE_DATE_EPOCH`). A rebuilt package of the *same version* with a
  changed state was silently ignored (seen on OMV 8.5); the postinst now
  `touch`es the plugin's salt files before deploying.
- With `dh_installsystemd --no-start` the generated postinst snippet does
  **not** run `systemctl daemon-reload`. A postinst that restarts its own
  service on upgrade must reload first, or the restart uses the old unit
  file (seen on OMV 8.5).
- Don't put a tight `StartLimitBurst` on a service that salt restarts on
  every Apply: a few Save/Apply rounds hit it and the service stays dead.
- Package versions and `migrations.d/<id>_<version>.sh` names must be
  PEP 440 versions: `omv-confdbadm migrate` uses `packaging.version`, so
  `7.0~alpha2` fails with "No valid version" (verified on OMV 8.5).
- Form `container` fields have no control, so put `modifiers` on the inner
  fields (as done for the custom-curve fields).
- Read-only computed fields in a form: `readonly: true`, `submitValue: false`.
- Dashboard widgets visible to non-admins need RPCs with `OMV_ROLE_EVERYONE`.
- After changing YAML on a dev box: `omv-mkworkbench all`; after changing
  PHP: `systemctl restart openmediavault-engined` (or `monit restart omv-engined`).
- Strings only used inside widget templates must be listed under `i18n:`.

## Patterns confirmed by openmediavault-tempmon

- `\OMV\System\Process::execute($output, $exitStatus)` is wrapped in
  `try/catch` there: treat a non-zero exit as an exception, not only a
  status code.
- Marking another module dirty: `$moduleMngr->getModule("collectd")` as
  the listener (`\OMV\Engine\Module\Manager::getInstance()`).
- **Performance graphs**:
  1. `srv/salt/omv/deploy/collectd/plugins/<name>.sls` writes
     `/etc/collectd/collectd.conf.d/<name>.conf` (`LoadPlugin exec`,
     `Exec "nobody" "<script>"`). OMV's collectd state includes it.
  2. The exec script loops forever printing
     `PUTVAL "$COLLECTD_HOSTNAME/<instance>/temperature-value" interval=$COLLECTD_INTERVAL N:<v>`.
     It runs as `nobody`, so tempmon needs a sudoers rule to read
     root-only sensors.
  3. `usr/share/openmediavault/mkrrdgraph/plugins.d/<name>.py`: class
     `Plugin(openmediavault.mkrrdgraph.IPlugin)`, `create_graph(config)`,
     image `{image_dir}/{instance}-{period}.png`, RRD
     `{data_dir}/{instance}/<type>-value.rrd`.
  4. An `rrdPage` component (`graphs: [{name: <instance>, label}]`), and
     route + navigation under `/diagnostics/performance-statistics/<name>`.
  5. postinst: `omv-salt deploy run <name> rrdcached collectd`.
- Workbench YAML can be **generated by salt** (e.g. one dashboard widget
  per sensor) followed by `omv-mkworkbench all` (`onchanges`). The plugin's
  postrm must then delete the generated files.
- Dashboard `type: chart` + `chart.type: gauge`, with `request:
  {service, method}` returning `{prop: value}`; `permissions.role: [admin,
  user]` pairs with an `OMV_ROLE_EVERYONE` RPC.
- Migrations guard each `omv_config_add_key` with `omv_config_exists`.

## OMV 7 vs 8 differences that matter

| | OMV 7 (Bookworm) | OMV 8 (Trixie) |
|-|-|-|
| debhelper | `debhelper (>= 13)` + `debian/compat` | `debhelper-compat (= 14)`, `dh-sequence-single-binary` |
| Salt modes | `644` accepted | must be `'0644'` |
| postrm | sources helper-functions | guard with `OMV_AVAILABLE` (we do) |
| Workbench | — | adds form `image`, `hasClearButton`, datatable tree mode, store `itemTemplates` (we avoid them) |

## Dev loop on a test NAS

```sh
make test && make docker-deb
make deploy NAS=root@NAS_HOST
ssh root@NAS_HOST 'journalctl -u qnapd -f'
ssh root@NAS_HOST 'qnapd status; qnapd info'
```

Full protocol: [../testing/hardware-testing.md](../testing/hardware-testing.md).
