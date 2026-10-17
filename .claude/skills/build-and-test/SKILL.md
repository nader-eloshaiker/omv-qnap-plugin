---
name: build-and-test
description: Run the unit tests and static checks and build the openmediavault-qnap .deb. Use after any code change, before deploying or committing.
---

# Build and test

Run from the repository root. Stop at the first failure and fix it.

1. Unit tests (no hardware needed):
   ```sh
   set -o pipefail; make test 2>&1 | tail -5
   ```
2. Static checks:
   ```sh
   docker run --rm -v "$PWD":/r:ro php:8.2-cli sh -c 'for f in /r/usr/share/openmediavault/engined/*/*.inc; do php -l "$f"; done'
   python3 -c "import json; [json.load(open(f'usr/share/openmediavault/datamodels/{f}')) for f in ('conf.service.qnap.json','rpc.qnap.json')]"
   docker run --rm -v "$PWD/usr":/u:ro python:3.11-slim sh -c 'pip -q install pyyaml >/dev/null 2>&1; python3 -c "import glob,yaml; [yaml.safe_load(open(f)) for f in glob.glob(\"/u/share/openmediavault/workbench/**/*.yaml\", recursive=True)]; print(\"yaml ok\")"'
   ```
3. Build the package (any OS with Docker):
   ```sh
   set -o pipefail; make docker-deb 2>&1 | tail -2
   ```
   The .deb lands in `dist/`. To inspect: `dpkg-deb -c dist/*.deb` (in a
   Debian container on macOS).
4. If you added config fields: version bumped in `debian/changelog`
   (PEP 440, digits and dots only) and a migration added; see
   `docs/build-and-release.md`.

Report the test count and result, and the built file name.
