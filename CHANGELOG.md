# Changelog
<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.2] - 2026-06-26

Fix Smart Criteria so imported playlists match tracks on current macOS.

### Fixed

- `_BOILERPLATE` placed the MediaKind subexpression's `0x01 0x01` prefix flags at byte offset 140-141 (derived from a 2021 library export); current macOS (Tahoe / Music 1.6.5) requires them at 143-144. Imported smart playlists registered as smart but matched zero tracks. Relocating the flags fixes matching — verified against 36 of 38 standard-format real exports and by live import (a `Genre contains "Ambient"` playlist matches 444 tracks, identical to the real export's criteria)

## [1.1.1] - 2026-03-09

Improve decoder robustness for malformed input.

### Fixed

- Decoding truncated Smart Criteria bytes no longer raises `IndexError`; the affected rule is replaced with a `<truncated at N>` marker

## [1.1.0] - 2026-03-09

Sharpen type signatures and fix decoder output for selection methods.

### Added

- `RuleNode` is now a typed union of `_GroupNode | _RuleNode` TypedDicts, giving IDEs and type checkers precise hints when building rule trees

### Changed

- Decoded selection method names now use spaces instead of underscores (`"recently added"`, `"recently played"`, `"highest rated"`)
- `decode_info_flags()` now raises `ValueError` with a descriptive message when passed fewer than 14 bytes, instead of crashing with `IndexError`

## [1.0.2] - 2026-03-08

Add developer tooling and repository hygiene.

### Added

- `py.typed` marker for PEP 561 compliance
- Ruff linter and formatter with `make lint`, `make fmt`, and a CI lint job
- Pre-commit hooks for Ruff formatting, import sorting, and file hygiene
- `SECURITY.md` with vulnerability reporting instructions
- `CODE_OF_CONDUCT.md` referencing Contributor Covenant v2.1
- Explicit `[tool.mypy]` and `[tool.ruff]` configuration in `pyproject.toml`
- 95% minimum coverage threshold enforced in CI and local test runs
- GitHub issue templates for bugs and features, and a pull request template

### Changed

- `THIRD_PARTY_NOTICES` renamed to `NOTICE` (conventional OSS filename)

## [1.0.1] - 2026-03-08

Add PyPI version badge to README.

### Added

- PyPI version badge in README

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
