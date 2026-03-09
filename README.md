# smart-playlist-io

Encode and decode Apple Music Smart Playlist binary format (`Smart Info` + `Smart Criteria`).

Encodes rule trees to binary blobs for XML import into Music.app via `File > Library > Import Playlist` or the AppleScript `add` command. Decodes existing smart playlists from Library XML exports to readable rule trees.

> This project is not affiliated with or endorsed by Apple Inc. Apple, Apple Music, and Music are trademarks of Apple Inc.

## Install

```bash
pip install git+https://github.com/kynoptic/smart-playlist-io.git
```

## Quick start

### Encode

```python
from smart_playlist_io import AND, OR, rule, encode, encode_b64, RuleNode

rules = AND([
    rule("Rating", "greater", 3),
    rule("LastPlayed", "not_in_last", 6, "months"),
    OR([
        rule("Genre", "starts", "Ambient"),
        rule("Genre", "starts", "Electronic / Ambient"),
    ]),
])

# Raw bytes
info_bytes, criteria_bytes = encode(rules, limit=25, select_by="most_played", live=True)

# Base64 (for XML plist)
info_b64, criteria_b64 = encode_b64(rules, limit=25, select_by="most_played")
```

### Decode

```python
from smart_playlist_io import decode_criteria, decode_info_flags

rules = decode_criteria(criteria_bytes)   # ['AND', 'Rating > 3', ...]
flags = decode_info_flags(info_bytes)     # 'live updating, limit 25 items, most played'
```

### CLI

```bash
decode-smart-playlists /path/to/Library.xml
decode-smart-playlists /path/to/Library.xml --out baseline.md
```

## API reference

### Rule builders

| Function | Signature | Returns |
|----------|-----------|---------|
| `AND` | `AND(children: list)` | Group dict with AND logic |
| `OR` | `OR(children: list)` | Group dict with OR logic |
| `rule` | `rule(field, op, value, unit=None)` | Rule dict |
| `encode` | `encode(rules, *, limit, limit_by, select_by, live, only_checked)` | `(info_bytes, criteria_bytes)` |
| `encode_b64` | `encode_b64(rules, **kwargs)` | `(info_b64_str, criteria_b64_str)` |
| `RuleNode` | `dict[str, Any]` | Type alias for any node returned by `AND`, `OR`, or `rule` |

### `encode()` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rules` | dict | required | AND/OR/rule tree from builder functions |
| `limit` | `int \| None` | `None` | Max items (disables limit when `None`) |
| `limit_by` | str | `"items"` | `"items"`, `"minutes"`, `"hours"`, `"MB"`, `"GB"` |
| `select_by` | str | `"most_played"` | Selection method (see below) |
| `live` | bool | `True` | Live-updating playlist |
| `only_checked` | bool | `False` | Exclude unchecked items |

**Selection methods:** `random`, `name`, `album`, `artist`, `genre`, `highest_rated`, `lowest_rated`, `most_played`, `least_played`, `most_recently_played`, `least_recently_played`, `most_recently_added`, `least_recently_added`

### Decoder

| Function | Signature | Returns |
|----------|-----------|---------|
| `decode_criteria` | `decode_criteria(data: bytes)` | `list` — rule tree `[logic, *rules]` |
| `decode_info_flags` | `decode_info_flags(info_bytes: bytes)` | `str` — human-readable flags |

### Supported fields

**String:** `Name`, `Artist`, `Album`, `Genre`, `Comments`, `Grouping`, `Composer`, `AlbumArtist`, `Kind`
Operators: `is`, `is_not`, `contains`, `not_contains`, `starts`, `ends`

**Integer:** `Rating` (1-5 star scale), `Year`, `Plays`, `BPM`, `BitRate`, `TrackNumber`, `DiskNumber`, `Size`, `Duration`, `Skips`
Operators: `is`, `is_not`, `greater`, `less`, `between` (tuple)

**Boolean:** `Checked`, `HasArtwork`
Operator: `is` with `True`/`False`

**Date:** `DateAdded`, `DateModified`, `LastPlayed`, `LastSkipped`
Operators: `in_last`, `not_in_last` (require `unit`: `"days"`, `"weeks"`, `"months"`), `after`, `before` (Mac epoch timestamp)

**Enum:** `iCloudStatus`, `Love`, `MediaKind`, `Location`
Operators: `is`, `is_not`

## Binary format

The encoder produces two binary blobs per playlist:

- **Smart Info** (112 bytes): playlist behavior settings (live update, limit, selection method)
- **Smart Criteria** (variable): 579-byte boilerplate + subexpression headers + rule blocks

The skip-length base in subexpression headers is **139** (not the theoretical 136). See `docs/adr-001-skip-length-padding.md` for the discovery and rationale.

## Attribution

Format knowledge derived from:

- [itunessmart](https://github.com/cvzi/itunes_smartplaylist) by cvzi (MIT)
- banshee-itunes-import-plugin by Scott Peterson

See `THIRD_PARTY_NOTICES` for full license text.

## License

MIT
