# Release process

pixoo-spotify validates, builds, and publishes releases with GitHub Actions. PyPI publication uses
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) and short-lived OpenID Connect
credentials; the normal release path does not use a stored PyPI API token.

## One-time PyPI setup

Do not create the release tag until these settings are ready:

1. Create the `pixoo-spotify` project on PyPI, or open its publishing settings if it already exists.
2. Add a pending Trusted Publisher with:
   - Owner: `hotchpotch`
   - Repository: `pixoo-spotify`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. Create a GitHub environment named `pypi`. Optional required reviewers can provide a manual
   approval gate before publication.

The release workflow grants `id-token: write` only to its publish job. Build and PR jobs remain
read-only.

## Pull-request validation

`.github/workflows/ci.yaml` runs for every pull request, push to `main`, and manual dispatch. It
installs the locked development environment and runs the same suite used locally:

```console
$ uv sync --locked --extra dev
$ uv run --extra dev tox
```

Tox runs pytest, Ruff, and ty. Live Spotify E2E tests remain opt-in and are not run in CI because
they require real credentials.

## Prepare a release

Choose a new version that has not already been published to PyPI. The examples below use
`X.Y.Z`; replace it with the intended release version.

1. Update the version and lockfile together:

   ```console
   $ uv version X.Y.Z
   ```

2. Move user-visible entries from `## HEAD` in `release-log.md` into `## X.Y.Z`, leaving the HEAD
   section ready for future work.
3. Update `tests/test_release_workflow.py` when the expected release version changes.
4. Commit the release preparation and ensure the worktree is clean.

## Build and inspect locally

Run the complete release build without uploading anything:

```console
$ python build.py --build --tag vX.Y.Z
```

The build helper performs all of the following:

- checks that `uv.lock` is current;
- checks that the tag, package version, and release-log section agree;
- runs pytest, Ruff, and ty through tox;
- removes and rebuilds `dist/` with `uv build --no-sources`;
- validates both distributions with `twine check --strict`;
- installs the wheel into an isolated uv environment and runs `pixoo-spotify --version`.

Inspect the files before publishing:

```console
$ tar -tzf dist/pixoo_spotify-X.Y.Z.tar.gz
$ python -m zipfile -l dist/pixoo_spotify-X.Y.Z-py3-none-any.whl
```

The distributions must not contain `.env`, Spotify tokens, local caches, virtual environments,
test output, or previously built `dist/` files.

## Exercise GitHub Actions before PyPI authentication

Run the **Release** workflow manually from the Actions tab. A manual dispatch runs only the build
job and uploads the distributions and release notes. Publishing and GitHub Release creation remain
disabled for manual runs. Download and inspect the artifacts from the workflow run.

## Publish after Trusted Publishing is configured

Merge the release PR into `main`. CI validates the merge commit first. After CI succeeds, the
Release workflow automatically:

1. checks that the version is not already on PyPI;
2. validates and builds the package again;
3. publishes the verified artifacts through Trusted Publishing;
4. creates the `vX.Y.Z` tag and GitHub Release from the matching `release-log.md` section.

If the publish job fails because Trusted Publishing is not configured, configure PyPI and rerun the
failed job. Do not create or force-push the release tag manually. For an already-published package
version, the workflow still validates the build but safely skips publishing and release creation.

## Verify the published package

```console
$ uvx --refresh-package pixoo-spotify pixoo-spotify --version
$ uvx --refresh-package pixoo-spotify pixoo-spotify --help
```
