# Build and release

## Everyday commands

```sh
make test          # unit tests (python3 -m unittest), no hardware needed
make docker-deb    # build dist/openmediavault-qnap_<version>_all.deb in debian:trixie
make docker-drivers   # build dist/qnap8528-dkms_*.deb, dist/qm2mod-dkms_*.deb
make deb           # same, on a Debian 13 host with debhelper installed
make deploy NAS=root@NAS_HOST   # copy dist/*.deb to a NAS and install it (tools/nas-deploy.sh)
```

Extra checks before committing. CI (`.github/workflows/ci.yml`) runs all of
these in `debian:trixie` on every push and pull request, plus shell syntax,
the build and lintian (`--fail-on error`; the two known warnings are
`no-manual-page` and `uses-implicit-await-trigger`), and uploads the .deb as
a workflow artifact:

```sh
docker run --rm -v "$PWD":/r:ro php:8.2-cli php -l /r/usr/share/openmediavault/engined/rpc/qnap.inc
python3 -c "import json; [json.load(open(f'usr/share/openmediavault/datamodels/{f}')) for f in ('conf.service.qnap.json','rpc.qnap.json')]"
# YAML: every file under usr/share/openmediavault/workbench must parse
```

When a test command is piped (e.g. `| tail`), use `set -o pipefail`, or a
failing `make test` will not stop the build.

## Versions

- Native package, version `8.0.N`: major = OMV major (omv-extras style).
  The plugin targets OMV 8 only; 7.0.x were pre-releases. OMV 7 support
  would be a separate 7.x release line with its own testing.
- **Versions must be PEP 440 compatible: digits and dots only.**
  `omv-confdbadm migrate` parses the previous version and every migration
  file name with Python `packaging.version`; `7.0~alpha2` failed every
  upgrade with "No valid version". `TestPackaging` in `tests/test_qnapd.py`
  enforces this.
- Bump the version (new `debian/changelog` entry) whenever a release adds
  config fields, and add a migration for them.

## Config migrations

`usr/share/openmediavault/confdb/migrations.d/conf.service.qnap_<version>.sh`
runs on upgrade when `<version>` is newer than the installed one. Add keys
idempotently:

```sh
xpath="/config/services/qnap"
if ! omv_config_exists "${xpath}/newfield"; then
	omv_config_add_key "${xpath}" "newfield" "1"
fi
```

Booleans are stored as `1`/`0`. Fresh installs get defaults from the
datamodel via `confdb/create.d/conf.service.qnap.sh` instead.

## postinst / postrm (verified on OMV 8.5)

- postinst `configure`: trigger `update-workbench`, `omv-confdbadm create`,
  `migrate` with `${2%%~*}` (old versions may carry a `~`), deploy salt
  states `qnap` and `collectd`, draw placeholder graphs.
- **`dh_installsystemd --no-start` does not run `daemon-reload`.** The
  postinst reloads systemd itself, after `#DEBHELPER#`, before
  `try-restart qnapd` on upgrade; otherwise the restart uses the old unit.
- Salt (not dpkg) enables and starts `qnapd`.
- The postinst `touch`es the plugin's salt files first: salt only re-reads
  states whose mtime changed, and dpkg stamps files with the changelog
  date, so rebuilding the same version would otherwise keep a stale state.
- postrm `remove`: drop the collectd config and restart collectd. `purge`:
  config node, `/etc/qnapd`, RRD data, graph images, module-load and grub
  files (+ `update-grub`).

## Packaging layout

`Architecture: all`; `debian/install` copies `etc/`, `srv/` and `usr/`;
`debian/openmediavault-qnap.qnapd.service` is the unit (installed to
`/usr/lib/systemd/system` on Trixie). `Build-Depends: debhelper-compat
(= 13)`: stock Trixie's debhelper (13.24) provides up to 13; compat 14,
which some OMV 8 plugins use, needs debhelper from trixie-backports and
brings nothing for an `Architecture: all` package. Keep `__pycache__` out of
`usr/` (tests set `sys.dont_write_bytecode`).

## Releasing

1. Changelog entry, version bump, migration if needed.
2. `make test`, the extra checks, `make docker-deb`.
3. Deploy to a test NAS and run the relevant parts of
   [testing/hardware-testing.md](testing/hardware-testing.md).
4. Tick the items in PLAN.md, commit, push, then
   `git tag v<version> && git push origin v<version>`. CI checks the tag
   matches `debian/changelog`, builds, and publishes the GitHub release
   with the .deb and the driver packages (`qnap8528-dkms`, `qm2mod-dkms`,
   from `drivers/`; see [dependencies.md](dependencies.md)); the notes are
   the changelog entry plus the driver versions. A last CI job runs the
   Pages workflow, which rebuilds the apt repository from the new release.

`debian/changelog` is the single source of the version (migrations are
named after it when the feature is written), so releases are tag-driven
rather than generated from commit messages.

Commit messages: imperative subject, a body explaining why; no tool
attribution trailers.

## Install script and apt repository

GitHub Pages (`.github/workflows/pages.yml`, source: GitHub Actions)
publishes three things under <https://nader-eloshaiker.github.io/omv-qnap-plugin/>:

- the website, built by Jekyll from `docs/` exactly as the old "deploy
  from /docs" setting did;
- `install`, the one-command installer (`docs/install`), run as
  `wget -O - …/install | bash`. It checks root, amd64, OMV 8 and a
  QNAP-looking BIOS (QNAP leaves most DMI fields as "Default string", so
  `bios_version` like `Q04WAR09` is the hint; `--yes` skips the question),
  adds the repository for that run if the installed plugin doesn't ship it
  yet, installs `openmediavault-qnap`, then runs `Qnap.setupDrivers`
  through `omv-rpc` (the same job as the Set up drivers button) when
  `needssetup` is true. CI runs `bash -n` and shellcheck on it;
- `apt/`, a flat, signed apt repository with the `.deb` files of the
  latest GitHub release (`gh release download`), built with
  `apt-ftparchive` and signed (`InRelease`, `Release.gpg`) with the key in
  the `APT_SIGNING_KEY` Actions secret.

The plugin installs `etc/apt/sources.list.d/omv-qnap.sources` (a
conffile) and the public key `usr/share/keyrings/omv-qnap.asc`, so every
install, by script or by upload, gets updates in Update Management. OMV's
apt salt state only removes files it names itself, so the source file
survives `omv-salt deploy run apt`. Don't name it `openmediavault-*`.

Pages runs on pushes to `main` that touch `docs/`, the key or the
workflow, on demand (`gh workflow run pages.yml`), and from CI after each
release (a release made with the workflow token triggers no other
workflow, so CI calls it as a reusable workflow).

**Signing key**: ed25519, fingerprint
`9D86 7FB1 E064 1C86 78E1  5D2D ECD0 FBAF F87B 4AA9`, no expiry. The
private key is only in the `APT_SIGNING_KEY` secret and in the
maintainer's offline backup. Losing it means a new key, and every
install would have to replace `/usr/share/keyrings/omv-qnap.asc` by hand
before it sees another update, so keep the backup.

