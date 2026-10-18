# Developer helpers. The package itself builds with plain debhelper.
.PHONY: test deb docker-deb drivers docker-drivers deploy clean

test:
	python3 -m unittest discover -s tests -v

# Requires a Debian 13 build host: apt install build-essential debhelper fakeroot
deb:
	dpkg-buildpackage -us -uc -b

# Build on any Docker host (e.g. macOS); the .deb lands in dist/.
DEBIAN_IMAGE ?= debian:trixie
docker-deb:
	mkdir -p dist
	docker run --rm -v "$(CURDIR)":/src:ro -v "$(CURDIR)/dist":/dist $(DEBIAN_IMAGE) sh -ec '\
		apt-get update -qq && \
		apt-get install -y -qq --no-install-recommends build-essential debhelper fakeroot >/dev/null && \
		cp -r /src /build && cd /build && rm -rf dist && \
		dpkg-buildpackage -us -uc -b && cp ../*.deb /dist/'
	ls -l dist/*.deb

# Driver packages (qnap8528-dkms, qm2mod-dkms) from the pinned upstream
# commits in drivers/*/source. Needs Debian 13 with git and dh-dkms.
drivers:
	drivers/build.sh dist

docker-drivers:
	mkdir -p dist
	docker run --rm -v "$(CURDIR)":/src:ro -v "$(CURDIR)/dist":/dist $(DEBIAN_IMAGE) sh -ec '\
		apt-get update -qq && \
		apt-get install -y -qq --no-install-recommends build-essential debhelper dh-dkms fakeroot git ca-certificates python3 >/dev/null && \
		/src/drivers/build.sh /dist'
	ls -l dist/*-dkms_*.deb

# Install the newest dist/*.deb on a test NAS: make deploy NAS=root@host
deploy:
	tools/nas-deploy.sh $(NAS)

clean:
	fakeroot debian/rules clean
