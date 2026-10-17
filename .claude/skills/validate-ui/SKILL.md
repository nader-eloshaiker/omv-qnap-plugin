---
name: validate-ui
description: Check the openmediavault-qnap pages in the OMV web UI with the Playwright MCP browser after a deploy - tiles, each System > QNAP page, dashboard widgets, performance graphs and console errors.
---

# Validate the web UI

Uses the Playwright MCP server from `.mcp.json` (other clients:
`docs/testing/ui-validation.md`). Get the UI address from the owner or
`OMV_URL` (e.g. `https://NAS_HOST:PORT`).

1. Open `$OMV_URL/#/system/qnap`. If the login page appears, ask the
   person to log in in the browser window and wait. Never type passwords.
2. Hard-reload once (Ctrl+Shift+R) so the cached workbench config refreshes.
3. Check the tiles: Status, Fan control, Front panel, Power, Drivers,
   System (in that order).
4. Open each page; capture a snapshot; read console messages at level
   error. Expect:
   - Status: fan, duty and temperature rows.
   - Fan control: choosing Custom reveals the curve fields (do not save).
   - Front panel, Power, Drivers: values load, Save disabled until edited.
   - System: model, serial, BIOS, EC firmware, boards, QM2 cards.
5. Open `#/diagnostics/performance-statistics/qnap`: tabs Temperatures,
   Fan speed, Fan duty each show a graph.
6. Dashboard (`#/dashboard`): QNAP widgets that are enabled render without
   error, "QNAP hardware" is green in Services. Leave the dashboard after
   checking (it loads the NAS CPU).
7. Only Save/Apply if the task requires it; restore previous values.

Report a table of page → pass/fail with the exact error text, and save
screenshots of failures to `.playwright-mcp/output/`.
