# Developer helpers. The package itself builds with plain debhelper.
.PHONY: test deb clean

test:
	python3 -m unittest discover -s tests -v

# Requires a Debian 12/13 build host: apt install build-essential debhelper fakeroot
deb:
	dpkg-buildpackage -us -uc -b

clean:
	fakeroot debian/rules clean
