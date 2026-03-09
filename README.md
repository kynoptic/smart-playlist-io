# smart-playlist-io

Build and inspect Apple Music smart playlists from Python.

```python
from smart_playlist_io import AND, OR, rule, encode_b64

rules = AND([
    rule("Rating", "greater", 3),
    rule("LastPlayed", "not_in_last", 6, "months"),
    OR([
        rule("Genre", "starts", "Ambient"),
        rule("Genre", "starts", "Electronic / Ambient"),
    ]),
])

info_b64, criteria_b64 = encode_b64(rules, limit=25, select_by="most_played")
```

Produces the `Smart Info` and `Smart Criteria` base64 blobs used in Music.app's Library XML format. Import them via `File > Library > Import Playlist` or the AppleScript `add` command. Also decodes existing smart playlists back to readable rules.

> Not affiliated with or endorsed by Apple Inc.

## Install

Requires Python 3.12+.

```bash
pip install git+https://github.com/kynoptic/smart-playlist-io.git
```

## Encode

```python
from smart_playlist_io import AND, OR, rule, encode, encode_b64

# Raw bytes
info_bytes, criteria_bytes = encode(rules, limit=25, select_by="most_played", live=True)

# Base64 strings (for XML plist)
info_b64, criteria_b64 = encode_b64(rules, limit=25, select_by="most_played")
```

### Options

| Parameter | Default | Values |
| --------- | ------- | ------ |
| `limit` | `None` | Any int, or `None` to disable |
| `limit_by` | `"items"` | `"items"`, `"minutes"`, `"hours"`, `"MB"`, `"GB"` |
| `select_by` | `"most_played"` | `random`, `name`, `album`, `artist`, `genre`, `highest_rated`, `lowest_rated`, `most_played`, `least_played`, `most_recently_played`, `least_recently_played`, `most_recently_added`, `least_recently_added` |
| `live` | `True` | `True` / `False` |
| `only_checked` | `False` | `True` / `False` |

### Fields and operators

| Type | Fields | Operators |
| ---- | ------ | --------- |
| String | `Name`, `Artist`, `Album`, `Genre`, `Comments`, `Grouping`, `Composer`, `AlbumArtist`, `Kind` | `is`, `is_not`, `contains`, `not_contains`, `starts`, `ends` |
| Integer | `Rating` (1–5), `Year`, `Plays`, `BPM`, `BitRate`, `TrackNumber`, `DiskNumber`, `Size`, `Duration`, `Skips` | `is`, `is_not`, `greater`, `less`, `between` |
| Boolean | `Checked`, `HasArtwork` | `is` |
| Date | `DateAdded`, `DateModified`, `LastPlayed`, `LastSkipped` | `in_last`, `not_in_last` (+ `unit`: `"days"`, `"weeks"`, `"months"`), `after`, `before` |
| Enum | `iCloudStatus`, `Love`, `MediaKind`, `Location` | `is`, `is_not` |

## Decode

```python
from smart_playlist_io import decode_criteria, decode_info_flags

rules = decode_criteria(criteria_bytes)   # ['AND', 'Rating > 3', ...]
flags = decode_info_flags(info_bytes)     # 'live updating, limit 25 items, most played'
```

## CLI

Decode all smart playlists in a Library XML export:

```bash
decode-smart-playlists /path/to/Library.xml
decode-smart-playlists /path/to/Library.xml --out baseline.md
```

## Notes

Binary format details and the skip-length padding decision are in [`docs/format-constants.md`](docs/format-constants.md).

Format knowledge derived from [itunessmart](https://github.com/cvzi/itunes_smartplaylist) by cvzi and banshee-itunes-import-plugin by Scott Peterson. See `THIRD_PARTY_NOTICES` for license text.

## License

MIT
