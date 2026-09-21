# AGENTS.md

Guidelines for AI coding agents working in this repository.

## Project

Python package (`uv`, src-layout under `src/hut_services/`) providing services to retrieve (mountain) hut data from multiple sources (OSM, refuges.info, wikidata, ...). Pydantic v2 schemas. Type gate is **mypy** (not Pyright — see Gotchas).

## Commands

- `uv run inv check` — quality gates: `uv lock --locked`, pre-commit (ruff), deptry, mypy. Must pass before merge.
- `uv run inv tests.run` — pytest (some tests hit live APIs).
- Always use `uv run inv ...` so venv binaries (git-cliff, ...) are on PATH.

## Pull requests

- PRs are squash-merged; the PR title becomes the commit message.
- **Label every PR** — changelog grouping is label-driven (`cliff.toml`): `BREAKING`, `INTERNAL` (skip), `type:feature`, `type:bug`, `type:refactor`, `type:docs`, `type:deps`, `type:tooling`, `type:tests`, `type:others`. Unlabeled PRs are **skipped** from the changelog.

## Release flow

1. Branch `release_vX.Y.Z` from `main` (predecessor style: `release_V0.1.2`).
2. Generate changelog + bump version: `inv release` (git-cliff + bump2version).
   The bump level comes **from PR labels** of merged, unreleased PRs
   (via `git-cliff --context`):
   - `BREAKING` → minor while 0.x (major from 1.0.0 on)
   - `type:feature` → minor
   - anything else → patch
   git-cliff computes the actual version number from the latest tag
   (`GIT_CLIFF__BUMP__BUMP_TYPE` override; requires git-cliff >= 2.9 and `GITHUB_TOKEN`).
   No conventional-commit PR titles needed; plain sentences are fine.
3. **Re-lock**: run `uv lock`. `uv.lock` records the project's own version; CI
   (`uv lock --locked` inside `inv check`) fails without it.
4. Verify `inv check` green, review `CHANGELOG.md` (`inv release` tells you to).
5. Commit (`Release vX.Y.Z`), push, open a PR against `main`.
6. **Merge the PR — never tag manually.** After CI on `main` succeeds,
   `new-version.yml` reads `inv version`, creates and pushes tag `vX.Y.Z`
   automatically, and dispatches `new-tag-created`, which triggers:
   - `release.yml` — GitHub Release with `inv changelog` as body
   - `publish-pypi.yml` — `uv build` + trusted publishing to PyPI

## Gotchas

- git-cliff needs `GITHUB_TOKEN` for the remote API (PR titles/labels, bump level).
  Source it before running release commands.
- `.bumpversion.cfg` must stay in sync with `pyproject.toml` (`current_version`);
  `bump2version` (via `inv release`) keeps them in sync.
- Pyright is a dev dependency but is **not** wired into CI; mypy is the type gate.
  Known Pyright disagreements (pydantic `populate_by_name` kwargs, `str` → `HttpUrl`
  coercion, `is False` on `bool | None`) are accepted — do not "fix" them.
- `tests/geocode/test_geocode_service.py::test_geocode_get_elevations` is skipped
  (open-elevation.com certificate expired 2026-09-20). Remove the skip once the
  provider renews its certificate.
