# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-03-08

Update package metadata.

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
