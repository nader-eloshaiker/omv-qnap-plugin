# Search visibility notes

Maintainer notes for the GitHub settings and the Pages site. Excluded from
the Pages build in `_config.yml`.

## Repository description (About box)

> OpenMediaVault plugin for QNAP NAS: quiet fan control, status and disk LEDs, buttons, temperature graphs and alerts after replacing QTS. Free, open source, qnap8528 based.

(171 characters.) Website field:
`https://nader-eloshaiker.github.io/omv-qnap-plugin/` (enable Pages from
`main` › `/docs` first).

## Topics

`openmediavault`, `omv`, `openmediavault-plugin`, `qnap`, `qnap-nas`,
`qts`, `qts-alternative`, `nas`, `fan-control`, `fan-curve`, `led-control`,
`hardware-monitoring`, `temperature-monitoring`, `homelab`, `self-hosted`,
`debian`, `linux`, `qnap8528`, `ts-253d`, `dkms`

## Social preview

Image: `docs/images/dashboard-gauges.jpg` cropped to 1280×640, with the
text:

> **openmediavault-qnap**
> Quiet fans and working lights on your QNAP, after you leave QTS.

## Search phrases targeted

- replace QTS / QTS alternative / QNAP alternative OS
- install OpenMediaVault on QNAP / OMV on QNAP
- QNAP OpenMediaVault fan control / OMV QNAP fan
- QNAP fan loud Linux / QNAP fan full speed Linux / QNAP fan 100% TrueNAS
- QNAP LED Linux / QNAP status LED OpenMediaVault
- QNAP Debian fan control / QNAP Linux hardware support
- TS-253D OpenMediaVault, plus model names from the qnap8528 list
  (TS-251D, TS-451D, TS-453D, TS-464, TS-473A, TS-673A, TS-873A, TS-877)
- qnap8528 / IT8528 fan control
- QM2 card fan Linux

Forum threads where people ask these (TrueNAS community "QNAP fans at
100%", the TrueNAS feature request for qnap8528, the OMV forum QNAP fan
thread) are good places for a short reply linking the site.

## On-page setup

- Search titles and descriptions for pages whose Markdown has no front
  matter are set under `defaults` in `_config.yml`, so the files read
  cleanly on GitHub.
- Developer pages are marked `noindex` and left out of the sitemap
  (`sitemap: false, noindex: true` in `defaults`); only pages for QNAP
  owners are offered to search engines.
- Every page shares `images/banner.png` as its link preview image.
- The home page adds SoftwareApplication structured data
  (`_includes/software-jsonld.html`): free, GPL-3.0, OpenMediaVault 8.
- Visitor counts: GoatCounter (cookie-free, no consent banner), switched on
  by `goatcounter:` in `_config.yml`.
- The two plugin sites link to each other where it helps a reader.
