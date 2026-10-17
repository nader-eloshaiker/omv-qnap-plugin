# AGENTS.md

openmediavault-qnap: an OpenMediaVault 8 plugin for fan control, LEDs
and hardware settings on QNAP NAS devices (and QM2 expansion cards), built
on the open source qnap8528 and qnap-qm2 kernel drivers. A Python daemon
(`usr/sbin/qnapd`) owns the hardware; OMV (PHP RPC, salt, YAML workbench)
configures it.

This file is a router. **Load only the documents your task needs**, using
the table below. Everything lives in `docs/`; start at `docs/README.md` if
unsure.

## Rules that always apply

1. **No AI attribution anywhere**: no `Co-Authored-By`, session links or
   "generated with" lines in commits, PRs, code or docs.
2. **No personal data in the repo**: no IP addresses, host names or serial
   numbers. Use `NAS_HOST` and "the reference TS-253D".
3. **Only qnapd writes hardware.** UI and graphs read `/run/qnapd/status.json`
   or `qnapd status|info`. Never talk to the EC from userspace, never call
   QNAP binaries.
4. **Never wake sleeping disks**: `smartctl -n standby`, `/sys/block/*/stat`,
   `zpool status`; never `drivetemp`.
5. **Fail safe**: stopped or crashed daemon → chassis fans full speed.
6. **Versions are PEP 440** (`8.0.N`; major = OMV major; no `~`). New
   config fields need a version bump and a confdb migration. Defaults live
   only in the datamodel.
7. **Hardware actions need the owner's consent** (stalling fans, killing the
   daemon, reboots, EC power settings). Agents never type passwords.
8. Run `make test` before every build; use `set -o pipefail` when piping it.

## Commands

```sh
make test                      # unit tests, no hardware needed
make docker-deb                # build the .deb in Docker (any OS)
make deploy NAS=root@NAS_HOST  # install on a test NAS over SSH
```

## Routing: task → context

| Task | Read | Agent | Runbook |
|-|-|-|-|
| Fan curve, presets, hysteresis, failsafe | `docs/hardware/fan-control.md`, `docs/hardware/ts-253d.md` | qnap-hardware | build-and-test |
| Status / disk / QM2 LEDs | `docs/hardware/leds.md` | qnap-hardware | hardware-test |
| Driver interfaces, new model support | `docs/reference/qnap8528.md`, `docs/dependencies.md` | qnap-hardware | — |
| Model test reports, other QNAP models | `docs/testing/model-testing.md`, `docs/hardware/models.md` | qnap-hardware | — |
| New setting or UI page, RPC, salt, graphs | `docs/omv-integration.md`, `docs/reference/omv-plugin-conventions.md` | omv-integration | add-setting |
| Packaging, versions, migrations, postinst | `docs/build-and-release.md` | packaging | build-and-test |
| Deploy to a NAS, test on hardware | `docs/testing/hardware-testing.md` | qnap-hardware | deploy-to-nas, hardware-test |
| Check the web UI | `docs/testing/ui-validation.md` | ui-validator | validate-ui |
| Roadmap, priorities, open questions | `docs/PLAN.md` | — | — |
| How the pieces fit | `docs/architecture.md` | — | — |
| QTS behaviour to imitate, prior art | `docs/reference/qts-behaviour.md`, `docs/reference/prior-art.md` | — | — |

## Agents and runbooks

- Agent definitions: `.claude/agents/*.md`. Each states its scope and the
  documents to load. Tools without sub-agents can use them as role
  prompts.
- Runbooks: `.claude/skills/<name>/SKILL.md` (Agent Skills format, plain
  Markdown): `build-and-test`, `deploy-to-nas`, `hardware-test`,
  `validate-ui`, `add-setting`. Any assistant can follow them step by step.
- UI validation uses the Playwright MCP server, preconfigured for several
  clients; see `docs/testing/ui-validation.md`.

How this context is organised, and how to wire up other assistants:
`docs/ai-context.md`.
