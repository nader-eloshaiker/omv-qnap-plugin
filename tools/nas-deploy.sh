#!/bin/sh
#
# This file is part of openmediavault-qnap.
#
# openmediavault-qnap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# nas-deploy.sh <user@host>: run on the development machine. Copies the
# newest dist/*.deb to the NAS, verifies it and installs it. Needs SSH key
# access as root (or a user allowed to run apt-get via sudo).
set -e
NAS=${1:?usage: nas-deploy.sh user@host}
DEB=$(ls -t dist/openmediavault-qnap_*_all.deb | head -1)
SUM=$(sha256sum "$DEB" 2>/dev/null || shasum -a 256 "$DEB")
SUM=${SUM%% *}
NAME=$(basename "$DEB")
scp -q "$DEB" "$NAS:/tmp/$NAME"
ssh "$NAS" "echo '$SUM  /tmp/$NAME' | sha256sum -c - && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --reinstall /tmp/$NAME && \
  rm -f /tmp/$NAME && systemctl is-active qnapd || true"
