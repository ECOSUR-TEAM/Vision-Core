# Release process

## Branch and tag strategy

Develop work is integrated in `develop`. Releases are created from an immutable
tag in the form `vMAJOR.MINOR.PATCH` pointing to a commit already merged into
`develop` or `main`. Do not create release branches for normal releases.

Use a short-lived `release/vX.Y.Z` branch only when a changelog or release
candidate needs final stabilization. Merge it into `main` and delete it after
the tag is created.

## Hotfixes

1. Branch from `main` as `hotfix/vX.Y.Z`.
2. Fix the issue and add a `Fixed` or `Security` changelog entry.
3. Run the complete test suite and lint locally.
4. Merge through a pull request into `main`.
5. Tag the merge commit with the next patch version.
6. Backport the change to `develop` if it is not already included.

Never reuse or move an existing tag. Publish a new patch release when a tag
contains an error.

## Step-by-step stable release

1. Update `version = "X.Y.Z"` in `pyproject.toml`.
2. Move the relevant `Unreleased` entries into a new Keep a Changelog section.
3. Merge the release commit to `main`.
4. Create and push the tag:

```bash
git tag -s vX.Y.Z -m "Vision Core vX.Y.Z"
git push origin vX.Y.Z
```

The release workflow validates SemVer, runs tests and lint, builds both images,
scans Trivy results, and creates the GitHub Release only after those checks pass.
Stable tags publish `X.Y.Z` and `latest`; prerelease tags publish only the
semantic version tags.

## Rollback

Pull and run the previous immutable image digest instead of a mutable tag:

```bash
docker pull ghcr.io/ecosur-team/vision-core@sha256:<runtime-digest>
docker pull ghcr.io/ecosur-team/vision-core-camera-bridge@sha256:<bridge-digest>
```

The GitHub Release body and attached `release-digests.txt` record the digests.
Restore Compose with:

```bash
docker compose down
docker compose up -d
```

After changing the image references to the previous digest, run `docker compose up -d`.
Verify `/health` and `/ready`, then test the camera stream.

Retain at least the most recent 10 GitHub Releases and their digest artifacts.
Repository owners must configure package retention separately when needed.

## Approvals and ownership

- **Author:** the developer implementing the release.
- **Reviewer:** a maintainer responsible for code and changelog approval.
- **Operator:** the maintainer who approves and executes the production tag.
- **Security reviewer:** required for Security entries or dependency changes.

No release should be published without green CI and reviewer approval.
