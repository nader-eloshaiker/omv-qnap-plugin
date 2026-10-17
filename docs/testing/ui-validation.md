# Validating the OMV web UI

The plugin's pages are YAML that OMV compiles into its Angular workbench,
so the only real test is loading them in a browser. The repo configures
the [Playwright MCP server](https://github.com/microsoft/playwright-mcp)
(`@playwright/mcp@0.0.83`) so any MCP-capable assistant can drive a
browser against a test NAS.

## Configuration in this repo

| Client | File |
|-|-|
| Claude Code | `.mcp.json` |
| Cursor | `.cursor/mcp.json` |
| VS Code / GitHub Copilot | `.vscode/mcp.json` |
| Gemini CLI | `.gemini/settings.json` |
| Codex CLI, others | add the same command to your client's MCP config (below) |

All run:

```
npx -y @playwright/mcp@0.0.83 --browser chrome --ignore-https-errors \
    --user-data-dir .playwright-mcp/profile --output-dir .playwright-mcp/output \
    --console-level warning
```

- `--ignore-https-errors`: OMV uses a self-signed certificate.
- `--user-data-dir`: a persistent, git-ignored profile, so a person logs in
  once and the session survives between runs. **Agents must not type the
  OMV password**; ask the person to log in in the opened browser window.
- `--browser chrome` uses the installed Google Chrome; without it, run
  `npx playwright install chromium` and drop the flag.
- Codex CLI (`~/.codex/config.toml`):
  ```toml
  [mcp_servers.playwright]
  command = "npx"
  args = ["-y", "@playwright/mcp@0.0.83", "--browser", "chrome", "--ignore-https-errors", "--user-data-dir", ".playwright-mcp/profile", "--output-dir", ".playwright-mcp/output", "--console-level", "warning"]
  ```

The NAS URL is not stored in the repo. Use `OMV_URL` (for example
`https://NAS_HOST:PORT`) from your shell or ask the owner.

## Checklist after a deploy

1. Hard-reload (the workbench config is cached) and log in if asked.
2. `System › QNAP`: six tiles in order Status, Fan control, Front panel,
   Power, Drivers, System.
3. Open each page; no error toast; no console errors.
   - Status: fan, duty and temperature rows (QM2 rows if a card is present).
   - Fan control: switching mode to Custom shows the curve fields.
   - Front panel / Power / Drivers: values load; Save stays disabled until a
     change. Saving shows the pending-changes bar; Apply asks to confirm.
   - System: model, serial, BIOS, EC firmware, boards, QM2 cards.
4. `Diagnostics › Performance statistics › QNAP`: three graph tabs.
5. Dashboard settings list "QNAP fans & temperatures", "QNAP device",
   "QNAP temperature history", "QNAP fan speed history"; enabled widgets
   render, and "QNAP hardware" is green in the Services widget.

Saving or applying changes the NAS configuration: do it only on a test box
or with the owner's agreement, and leave settings as you found them.
Never accept browser or cookie prompts on the owner's behalf.
