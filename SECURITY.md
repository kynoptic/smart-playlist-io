# Security Policy

## Supported Versions

Only the latest release receives security fixes.

| Version | Supported |
|---------|-----------|
| 1.x     | ✓         |

## Reporting a Vulnerability

Please **do not** open a public issue for security vulnerabilities.

Report them privately via [GitHub's security advisory feature](https://github.com/kynoptic/smart-playlist-io/security/advisories/new). Include a description of the issue, steps to reproduce, and any relevant context.

You can expect an acknowledgement within 48 hours and a resolution or status update within 14 days.

## Format Stability

The encoded binary format is empirically derived from a 2021 Music.app library export and is not documented by Apple. The components most likely to change with future Apple updates are:

- `_BOILERPLATE` — the 579-byte fixed outer container and `MediaKind` filter block
- `_SUBEXPR_SKIP_BASE` — the skip-length base value (currently 139) in subexpression headers
- Scale constants such as the rating upper-bound +9 offset

If encoded playlists stop importing correctly after a macOS update, consult [`docs/runbook-format-changes.md`](docs/runbook-format-changes.md) for the re-extraction and validation procedure.

Encoded playlists are passive data structures. They do not execute code, do not make network requests, and have no known attack surface. Music.app parses them as plist XML blobs and would reject malformed input using its own XML parser.
