#!/bin/sh
# Build <name>-dkms .debs from the pinned upstream commits in
# drivers/<name>/source. Needs Debian 13 with git, debhelper and dh-dkms.
# Usage: drivers/build.sh OUTDIR [NAME...]   (default: every driver)
set -eu

here=$(cd "$(dirname "$0")" && pwd)
out=$(mkdir -p "$1" && cd "$1" && pwd)
shift
[ $# -gt 0 ] || set -- $(cd "$here" && ls -d */ | tr -d / | grep -vx debian)

for name in "$@"; do
    unset REPO VERSION COMMIT REVISION LICENSE SUMMARY DESCRIPTION
    . "$here/$name/source"
    export REPO VERSION LICENSE SUMMARY DESCRIPTION
    work=$(mktemp -d)
    tree="$work/$name-dkms-$VERSION"

    # A full commit hash pins the content; git verifies it on fetch.
    git init -q "$work/upstream"
    git -C "$work/upstream" fetch -q --depth 1 "$REPO" "$COMMIT"
    git -C "$work/upstream" checkout -q FETCH_HEAD
    upstream=$(sed -n 's/^PACKAGE_VERSION=//p' "$work/upstream/dkms.conf")
    if [ "$upstream" != "$VERSION" ]; then
        echo "$name: dkms.conf says $upstream, source says $VERSION" >&2
        exit 1
    fi

    mkdir -p "$tree"
    cp -r "$work/upstream/src" "$tree/"
    cp -r "$here/debian" "$tree/debian"
    cp "$work/upstream/dkms.conf" "$tree/"
    echo dkms.conf > "$tree/debian/$name-dkms.dkms"  # dh_dkms: its path
    later=""
    [ "$LICENSE" = GPL-2.0-or-later ] && later=", or (at your option)
 any later version"
    for f in "$tree"/debian/*; do
        [ -f "$f" ] || continue
        NAME=$name LATER=$later python3 - "$f" <<'PY'
import os, sys, textwrap
path = sys.argv[1]
text = open(path).read()
for key in ("NAME", "REPO", "VERSION", "LICENSE", "SUMMARY",
            "DESCRIPTION", "LATER"):
    value = os.environ.get(key, "")
    if key == "DESCRIPTION":  # a control field continuation
        value = textwrap.fill(value, 72).replace("\n", "\n ")
    text = text.replace("@%s@" % key, value)
open(path, "w").write(text)
PY
    done
    for f in install preinst; do
        mv "$tree/debian/$f" "$tree/debian/$name-dkms.$f"
    done
    cat > "$tree/debian/changelog" <<CL
$name-dkms ($VERSION-$REVISION) stable; urgency=low

  * Upstream v$VERSION, commit $COMMIT.

 -- Nader Eloshaiker <1904325+nader-eloshaiker@users.noreply.github.com>  $(date -R)
CL
    (cd "$tree" && dpkg-buildpackage -us -uc -b >"$work/build.log" 2>&1) || {
        cat "$work/build.log" >&2
        exit 1
    }
    mv "$work"/*.deb "$work"/*.buildinfo "$work"/*.changes "$out/"
    rm -rf "$work"
    echo "built $name-dkms $VERSION-$REVISION"
done
