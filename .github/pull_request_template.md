## What and why

<!-- What does this change, and what problem does it solve? -->

## Tested on

<!-- "Unit tests only", or the NAS model, OMV version and what you checked
on it (fans, LEDs, UI pages...). Leave out host names, IP addresses and
serial numbers. -->

## Checklist

- [ ] `make test` passes
- [ ] New config fields: version bumped in `debian/changelog` and a confdb
      migration added (see `docs/build-and-release.md`)
- [ ] Hardware writes only from `qnapd`; nothing wakes sleeping disks
- [ ] Docs updated if behaviour changed
