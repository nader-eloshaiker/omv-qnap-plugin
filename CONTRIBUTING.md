# Contributing

Thanks for helping. Issues and pull requests are welcome, especially
reports from QNAP models other than the TS-253D.

## Before you start

- Read [AGENTS.md](AGENTS.md) for the rules that always apply (they are
  for people too) and [docs/README.md](docs/README.md) for how the pieces
  fit.
- For anything larger than a fix, open an issue first so we can agree on
  the approach.

## Making a change

```sh
make test         # unit tests, no hardware needed
make docker-deb   # build the .deb in Docker (any OS)
```

- CI runs the tests, PHP/JSON/YAML/shell syntax checks, the package build
  and lintian on every pull request. Workflows from first-time
  contributors start once the maintainer approves them.
- Only `qnapd` writes to hardware, and nothing may wake sleeping disks.
- New config fields need a version bump in `debian/changelog` and a confdb
  migration ([docs/build-and-release.md](docs/build-and-release.md)).
  Versions are PEP 440: `8.0.N`.
- Commit messages: an imperative subject, and a body explaining why.
- Don't include host names, IP addresses or serial numbers in code, docs,
  logs or screenshots.

Changes that affect fans or LEDs are tested on the reference TS-253D
before release. If you tested on your own hardware, say what you checked
in the pull request.

## Releases

The maintainer adds the `debian/changelog` entry and pushes a `v<version>`
tag; CI builds the package and publishes the GitHub release.
