---
name: deploy-to-nas
description: Install a freshly built openmediavault-qnap package on a test NAS over SSH and confirm the daemon is healthy. Use after build-and-test when the change must be checked on hardware.
---

# Deploy to a test NAS

Needs `NAS=root@NAS_HOST` with SSH key access (agents never type
passwords). Tell the owner first: installing restarts qnapd (chassis fan
briefly to full speed) and OMV's engine (web sessions are logged out).

1. Build: follow `build-and-test`.
2. Deploy:
   ```sh
   make deploy NAS=$NAS
   ```
3. Confirm:
   ```sh
   ssh $NAS 'systemctl is-active qnapd; systemctl show qnapd -p NRestarts; \
     journalctl -u qnapd --since "-2min" --no-pager -o cat | tail -15; qnapd status'
   ```
   Expect `active`, no warnings or tracebacks, fan PWM settling within a
   minute, LEDs in their expected state.
4. If the package added config fields, check the migration ran
   (`Running migration 'conf.service.qnap_<version>'` in the apt output) and
   `omv-confdbadm read conf.service.qnap` shows the new keys.
5. If UI files changed, continue with `validate-ui`.
6. If `make test` was not green, do not deploy.
