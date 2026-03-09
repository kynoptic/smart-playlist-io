# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Add developer tooling and repository hygiene for professional open-source standards.

### Added

- `py.typed` marker for PEP 561 compliance
- Ruff linter and formatter (`make lint`, `make fmt`, CI lint job)
- `.pre-commit-config.yaml` with Ruff and basic file hooks
- `SECURITY.md` with vulnerability reporting instructions
- `CODE_OF_CONDUCT.md` referencing Contributor Covenant v2.1
- Explicit `[tool.mypy]` and `[tool.ruff]` configuration in `pyproject.toml`
- 95% coverage threshold enforced via `--cov-fail-under`

## [1.0.1] - 2026-03-08

Improve package metadata for PyPI discoverability.

### Changed

- Added PyPI homepage URL, source URL, and bug tracker URL to package metadata
- Added keywords and classifiers for PyPI discoverability
- Pinned supported Python versions (3.12, 3.13) in classifiers

## [1.0.0] - 2026-03-08

First public release enabling Python-based creation and inspection of Apple Music smart playlists.

### Added

- Encode smart playlist rule trees to the `Smart Info` and `Smart Criteria` binary blobs required by Apple Music's Library XML format
- Decode existing smart playlists from Library XML exports back to readable rule descriptions
- Rule support for all field types: string (`Name`, `Artist`, `Album`, `Genre`, and more), integer (`Rating`, `Year`, `Plays`, `BPM`, and more), boolean (`Checked`, `HasArtwork`), date (`DateAdded`, `LastPlayed`, and more), and enum (`iCloudStatus`, `Love`, `MediaKind`, `Location`)
- Logical nesting with `AND` and `OR` at arbitrary depth
- Playlist options: item/time/size limits, selection ordering (most played, random, highest rated, etc.), live updating, and checked-only filtering
- Input validation on all public encoder arguments with clear error messages
- `decode-smart-playlists` CLI command for batch-decoding all smart playlists in a Music.app Library XML export
- Zero runtime dependencies; requires Python 3.12+
