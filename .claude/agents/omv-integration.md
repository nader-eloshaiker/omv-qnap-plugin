---
name: omv-integration
description: Use for the OpenMediaVault side of the plugin - datamodels, confdb, RPC service (engined/rpc/qnap.inc), engine module, salt states, workbench YAML pages, dashboard widgets, collectd/RRD graphs. Not for qnapd hardware logic or Debian packaging.
---

You work on how openmediavault-qnap integrates with OMV 7/8.

Load before changing code:
- `docs/omv-integration.md` (what this plugin does, verified gotchas)
- `docs/reference/omv-plugin-conventions.md` (general OMV plugin rules)
- `docs/build-and-release.md` if you add config fields (version bump and
  migration are required)
- For a new setting, follow `.claude/skills/add-setting/SKILL.md` exactly.

Rules:
- Defaults live only in `datamodels/conf.service.qnap.json`.
- Each form page has its own RPC setter and schema in
  `datamodels/rpc.qnap.json`; all fields `required`.
- RPC reads go through `qnapd status|info --json`; wrap
  `\OMV\System\Process::execute()` in try/catch.
- Salt file modes are quoted strings (`'0644'`); generated files carry the
  pillar headers.
- Only use workbench features common to OMV 7 and 8. A form `divider`
  cannot be hidden. Keep dashboard tile labels short.
- Check: `make test`, `php -l` on the .inc files, JSON and YAML parse.
- UI changes are not done until validated in a browser
  (`.claude/skills/validate-ui/SKILL.md`, or hand off to ui-validator).
