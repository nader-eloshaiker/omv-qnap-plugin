# AI assistant context

This repository is set up so any coding assistant can find the right
context without loading everything at once. Nothing here depends on a
particular vendor: the source of truth is plain Markdown.

## Layers

| Layer | Where | Loaded |
|-|-|-|
| Router: rules that always apply + task → document table | `AGENTS.md` | always (keep it short) |
| Knowledge | `docs/` (index: `docs/README.md`) | per task, via the router |
| Roles | `.claude/agents/*.md` | when a task matches the role's description |
| Runbooks | `.claude/skills/<name>/SKILL.md` | when a task matches the runbook's description |
| Tools | MCP config files (Playwright for UI validation) | by the client |

Agents and runbooks are Markdown with a small YAML header (`name`,
`description`). The descriptions are what assistants match on, so keep
them specific: what it is for and when to use it.

## Per assistant

| Assistant | Instructions | Roles / runbooks | MCP |
|-|-|-|-|
| Claude Code | `CLAUDE.md` (imports `AGENTS.md`) | sub-agents and skills discovered from `.claude/` | `.mcp.json` |
| OpenAI Codex | `AGENTS.md` (native) | read `.claude/skills/*/SKILL.md` as runbooks | `~/.codex/config.toml`, see `docs/testing/ui-validation.md` |
| Cursor | `AGENTS.md` (native) | runbooks by path | `.cursor/mcp.json` |
| GitHub Copilot | `.github/copilot-instructions.md` → `AGENTS.md` | runbooks by path | `.vscode/mcp.json` |
| Gemini CLI | `GEMINI.md` (imports `AGENTS.md`) | runbooks by path | `.gemini/settings.json` |
| Others | point them at `AGENTS.md` | | same Playwright command |

## Keeping it healthy

- New knowledge goes into the one document that owns the topic (see
  `docs/README.md`), not into `AGENTS.md`. Add a routing row only for a
  new kind of task.
- A new repeatable procedure becomes a runbook in `.claude/skills/`; list
  it in `AGENTS.md`.
- Facts measured on hardware are marked as such, with model and date.
- No personal data (IP addresses, host names, serial numbers) and no
  assistant attribution anywhere in the repo.
- When an assistant learns something the hard way (a bug only visible on
  hardware, an OMV quirk), record it in the owning document's "lessons" or
  "gotchas" section so the next one does not repeat it.
