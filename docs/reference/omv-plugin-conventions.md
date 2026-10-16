# OMV plugin conventions (cheat sheet)

Distilled from openmediavault-fail2ban, -cputemp, -wol, -omvextrasorg
(OMV 7 `7.x` branches and OMV 8 `master`) and core
`deb/openmediavault-snmp`. Official docs:
<https://docs.openmediavault.org/en/latest/development/plugins.html>.
(openmediavault-sensors is OMV 4 / ExtJS — do not copy.)

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
- Form `container` fields have no control, so put `modifiers` on the inner
  fields (as done for the custom-curve fields).
- Read-only computed fields in a form: `readonly: true`, `submitValue: false`.
- Dashboard widgets visible to non-admins need RPCs with `OMV_ROLE_EVERYONE`.
- After changing YAML on a dev box: `omv-mkworkbench all`; after changing
  PHP: `systemctl restart openmediavault-engined` (or `monit restart omv-engined`).
- Strings only used inside widget templates must be listed under `i18n:`.

## OMV 7 vs 8 differences that matter

| | OMV 7 (Bookworm) | OMV 8 (Trixie) |
|-|-|-|
| debhelper | `debhelper (>= 13)` + `debian/compat` | `debhelper-compat (= 14)`, `dh-sequence-single-binary` |
| Salt modes | `644` accepted | must be `'0644'` |
| postrm | sources helper-functions | guard with `OMV_AVAILABLE` (we do) |
| Workbench | — | adds form `image`, `hasClearButton`, datatable tree mode, store `itemTemplates` (we avoid them) |

## Dev loop on a test NAS

```sh
make deb                        # on a Debian 12/13 host or container
scp ../openmediavault-qnap_*_all.deb nas:
ssh nas 'apt install ./openmediavault-qnap_*_all.deb'
ssh nas 'journalctl -u qnapd -f'
ssh nas 'qnapd status; qnapd info'
```
