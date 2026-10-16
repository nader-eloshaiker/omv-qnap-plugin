# Developer helpers. The package itself builds with plain debhelper.
.PHONY: test deb docker-deb clean

test:
	python3 -m unittest discover -s tests -v

# Requires a Debian 12/13 build host: apt install build-essential debhelper fakeroot
deb:
	dpkg-buildpackage -us -uc -b

# Build on any Docker host (e.g. macOS); the .deb lands in dist/.
DEBIAN_IMAGE ?= debian:bookworm
docker-deb:
	mkdir -p dist
	docker run --rm -v "$(CURDIR)":/src:ro -v "$(CURDIR)/dist":/dist $(DEBIAN_IMAGE) sh -ec '\
		apt-get update -qq && \
		apt-get install -y -qq --no-install-recommends build-essential debhelper fakeroot >/dev/null && \
		cp -r /src /build && cd /build && rm -rf dist && \
		dpkg-buildpackage -us -uc -b && cp ../*.deb /dist/'
	ls -l dist/*.deb

clean:
	fakeroot debian/rules clean
