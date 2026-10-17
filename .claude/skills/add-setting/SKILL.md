---
name: add-setting
description: Add a new configuration field to openmediavault-qnap end to end - datamodel, RPC schema, form page, daemon settings, migration, version bump, tests, docs. Use whenever a feature needs a user-visible option.
---

# Add a setting

Every step is required; skipping one breaks Save, upgrades or the daemon.
Example field: `leddisk` (bool, Front panel page).

1. **Datamodel** `usr/share/openmediavault/datamodels/conf.service.qnap.json`:
   add the property with `type` and `default` (the only place defaults live).
2. **RPC schema** `datamodels/rpc.qnap.json`: add it, `"required": true`, to
   the setter of the page that shows it (`setfansettings`,
   `setfrontpanelsettings`, `setpowersettings`, `setdriversettings`). A
   new page needs a new setter in `engined/rpc/qnap.inc` and its schema.
3. **Form** `workbench/component.d/omv-system-qnap-<page>-form-page.yaml`:
   add the field with the same `value` default and a hint. Avoid `": "`
   inside `_()` strings. Read-only computed fields use `readonly: true`
   and `submitValue: false`.
4. **Daemon** `usr/sbin/qnapd` `Settings.__init__`: read it with a
   default identical to the datamodel (`to_bool(raw.get("x", True))`).
   Salt already renders every config key into `/etc/qnapd/qnapd.json`.
5. **Salt**, only if the setting changes system files
   (`srv/salt/omv/deploy/qnap/default.sls`).
6. **Version and migration**: new `debian/changelog` entry `7.0.N+1`
   (PEP 440), and
   `confdb/migrations.d/conf.service.qnap_7.0.N+1.sh` (mode 755) adding
   the key idempotently with `omv_config_exists` / `omv_config_add_key`
   (booleans as `1`/`0`).
7. **Tests** in `tests/test_qnapd.py` for the behaviour; `TestPackaging`
   checks the version format.
8. **Docs**: the field table in `docs/omv-integration.md`, the behaviour
   doc in `docs/hardware/` if relevant, `docs/PLAN.md` §4.
9. Run `build-and-test`, then `deploy-to-nas` (check the migration ran)
   and `validate-ui` (the field loads, saves, applies).
