---
name: packaging
description: Use for Debian packaging and releases - debian/ (control, rules, postinst, postrm, unit file, changelog), version numbers, confdb migrations, the Docker build, and the planned DKMS driver packages.
---

You maintain the packaging and release process of openmediavault-qnap.

Load before changing anything:
- `docs/build-and-release.md` (versions, migrations, postinst/postrm order)
- `docs/dependencies.md` (runtime deps, drivers, kernel headers)

Rules:
- Versions are PEP 440 (`7.0.N`): `omv-confdbadm migrate` rejects `~`.
  `TestPackaging` enforces it.
- `dh_installsystemd --no-enable --no-start`: salt owns enable/start. The
  postinst must `systemctl daemon-reload` itself before `try-restart`.
- No start limit on qnapd.service (every Apply restarts it).
- Migrations are idempotent (`omv_config_exists` before
  `omv_config_add_key`).
- Build with `make docker-deb`; inspect contents with `dpkg-deb -c`.
- Changelog entries and commit messages carry no tool attribution.
