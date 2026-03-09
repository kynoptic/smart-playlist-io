# AGENTS.md

Apple Music Smart Playlist binary format encoder and decoder. Encodes rule trees to `Smart Info` + `Smart Criteria` binary blobs for XML import into Music.app. Decodes existing smart playlists from Library XML exports.

## Commands

```bash
make init    # Create .venv and install dependencies
make test    # Run full test suite
make clean   # Remove .venv and caches
```

## Architecture

```
src/smart_playlist_io/
  __init__.py    # Re-exports public API
  constants.py   # Field IDs, enum maps, logic constants (single source of truth)
  encode.py      # Encoder: AND/OR/rule builders + encode()/encode_b64()
  decode.py      # Decoder: decode_criteria()/decode_info_flags() + CLI
tests/
  test_encode.py # 86 encoder unit tests (byte-level layout verification)
  test_decode.py # Roundtrip tests (encode -> decode -> verify)
```

## Key constants

- `_SUBEXPR_SKIP_BASE = 139` — NOT 136. See `docs/format-constants.md`.
- `_BOILERPLATE` — 579 fixed bytes (outer SLst + MediaKind filter)
- Int/enum/bool/date rules: 124 bytes. String rules: 54-byte header + UTF-16 LE data.

## Public API

| Module | Exports |
|--------|---------|
| `encode` | `AND`, `OR`, `rule`, `encode`, `encode_b64`, `RuleNode` |
| `decode` | `decode_criteria`, `decode_info_flags` |
| `constants` | All field/enum/logic maps |

## Console script

`decode-smart-playlists <library.xml>` — decodes all smart playlists to readable text.

## Docs

| File | Diátaxis type | Contents |
|------|---------------|----------|
| `docs/format-constants.md` | Explanation | Empirically-derived constants: skip-length base, rating offset, string length limit |
| `docs/adr-001-boilerplate-n2-no-identity-child.md` | Architecture Decision Record | Why `_BOILERPLATE` uses N=2 without an identity child node |
| `docs/adr-002-top-level-or-emitted-directly.md` | Architecture Decision Record | Why top-level OR is emitted directly rather than wrapped |
| `docs/runbook-format-changes.md` | How-to | Diagnosing and fixing broken imports after a macOS update |

## Safety

- Encoder is battle-tested: 86 tests + verified Music.app imports for all rule types
- The +3 skip-length padding is empirically derived — if Music.app imports fail after a macOS update, the padding may have changed
- String fields are capped at 127 characters (UTF-16 byte length must fit in one byte)
