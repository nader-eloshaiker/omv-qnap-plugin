# Security policy

## Reporting a vulnerability

Do not open a public issue, discussion or pull request for a security problem.

Report it through GitHub's private vulnerability reporting:

1. Open this repository's **Security** tab and choose **Report a vulnerability**, or go straight to [the report form](https://github.com/nader-eloshaiker/omv-qnap-plugin/security/advisories/new).
2. Describe the problem: what is affected (for example the qnapd daemon, the OMV RPC service, the install script or the package repository), the version or commit, what an attacker could do, and how to see it happen.
3. Submit. You need only a GitHub account. No email address or other contact details are exchanged.

The report is visible only to you and the maintainer. The conversation about it, and the fix, stay in that private advisory until it is published.

## What happens next

1. The maintainer confirms the report and how serious it is in the advisory.
2. A fix is prepared in private and released.
3. The advisory is published with the fix. Where the problem affects a released version, a CVE ID is requested through GitHub, which assigns CVE IDs for advisories published on it, so the issue can be tracked in vulnerability databases.
4. You are credited in the advisory, unless you ask not to be.

Fixes go into the latest release; older releases are not patched. Problems in the current code on `main` are welcome through the same form.

## Scope

In scope: everything this project ships.

- The `openmediavault-qnap` package: the `qnapd` daemon (it runs as root), the OMV RPC service, salt states, web interface pages and dashboard widgets, and the files the package installs.
- The install script (`https://nader-eloshaiker.github.io/omv-qnap-plugin/install`), the signed apt repository and its key.
- The packaging of the `qnap8528-dkms` and `qm2mod-dkms` driver packages.

Out of scope here, report to their own projects instead:

- openmediavault itself (see its `SECURITY.md`) and other plugins.
- The code of the qnap8528 and qnap-qm2 kernel drivers: report to [0xGiddi/qnap8528](https://github.com/0xGiddi/qnap8528) and [0xGiddi/qnap-qm2](https://github.com/0xGiddi/qnap-qm2).
- QNAP firmware (BIOS and embedded controller).
