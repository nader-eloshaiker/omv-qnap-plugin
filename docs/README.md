# openmediavault-qnap documentation

Read only what your task needs. Users discuss the plugin in the
[OMV forum thread](https://forum.openmediavault.org/index.php?thread/59641-openmediavault-qnap-fan-control-leds-and-hardware-settings-for-qnap-nas-omv-8-te/). Each document stands alone and links to
the others where they meet.

| Document | Read it when you are… |
|-|-|
| [guide/qts-to-omv.md](guide/qts-to-omv.md) | a QNAP owner moving from QTS to OMV: step-by-step user guide from backup to installing the plugin |
| [architecture.md](architecture.md) | new to the repo, or changing how components talk to each other |
| [hardware/ts-253d.md](hardware/ts-253d.md) | touching anything that reads or writes hardware; needing measured facts about the reference box |
| [hardware/fan-control.md](hardware/fan-control.md) | changing the fan curve, presets, hysteresis, floors, failsafe |
| [hardware/leds.md](hardware/leds.md) | changing the status, disk bay or QM2 slot LEDs |
| [omv-integration.md](omv-integration.md) | changing the datamodel, RPC, salt states, workbench pages, dashboard widgets or graphs |
| [disk-sleep.md](disk-sleep.md) | disks don't spin down; checking what may and may not run alongside the plugin |
| [dependencies.md](dependencies.md) | installing drivers, adding a package or kernel-module dependency |
| [build-and-release.md](build-and-release.md) | building the .deb, bumping the version, adding a confdb migration, editing postinst/postrm |
| [testing/hardware-testing.md](testing/hardware-testing.md) | deploying to a NAS and verifying behaviour on real hardware |
| [testing/model-testing.md](testing/model-testing.md) | collecting a test report from another QNAP model, or turning one into docs and a release |
| [hardware/ts-877.md](hardware/ts-877.md) | working on TS-877 support (LCD, buzzer, two fan groups, 10 slots) |
| [hardware/models.md](hardware/models.md) | checking which models have been tested and how |
| [testing/ui-validation.md](testing/ui-validation.md) | checking the OMV web UI (Playwright MCP) |
| [ai-context.md](ai-context.md) | setting up an AI coding assistant for this repo |
| [PLAN.md](PLAN.md) | checking the roadmap, phase checklists, design decisions and open questions |
| [reference/](reference/) | needing upstream facts: [qnap8528 and qnap-qm2 drivers](reference/qnap8528.md), [QTS behaviour](reference/qts-behaviour.md), [prior art](reference/prior-art.md), [OMV plugin conventions](reference/omv-plugin-conventions.md) |

## Conventions for these documents

- Facts measured on hardware say so, with the model and date. Everything
  else is from source code or vendor documentation and says where from.
- No personal data: no IP addresses, host names or serial numbers. Use
  `NAS_HOST` and "the reference TS-253D".
- When a decision changes, update the document that owns it (the table
  above) and PLAN.md's checklist. Do not leave the old text behind.
