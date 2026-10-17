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

## Model support (delete if not applicable)

<!-- For changes that add or fix support for a QNAP model. See
docs/testing/model-testing.md. -->

- Model and QM2 card:
- Model test report: <!-- link to the issue, or paste the output of
  `sudo python3 tools/model-test.py --interactive` below -->
- [ ] `docs/hardware/<model>.md` added or updated with what was measured
- [ ] Row added or updated in `docs/hardware/models.md`
- [ ] Unit tests cover the model's sysfs layout where the code changed
