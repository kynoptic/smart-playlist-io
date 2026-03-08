# ADR-001: Smart playlist skip-length requires +3 padding

## Status

Accepted

## Date

2026-03-08

## Context

The smart playlist encoder produces binary `Smart Criteria` blobs for import into Music.app via XML. Each subexpression header contains a skip-length field (bytes 51-52, BE uint16) that tells the parser how many bytes to advance to find the next sibling node.

The theoretical formula is `skip_length = (192 - 56) + children_bytes = 136 + children_bytes`, derived from the 192-byte header size minus the 56-byte offset the parser adds internally.

With `_SUBEXPR_SKIP_BASE = 136`, playlists imported into Music.app crashed with error `-609 Connection invalid`. Both top-level OR and nested OR structures exhibited this crash.

## Decision

Set `_SUBEXPR_SKIP_BASE = 139` (not the theoretical 136).

This was determined by:

1. Exporting `Library.xml` from Music.app containing a working manually-created playlist
2. Hex-diffing the real `Smart Criteria` bytes against encoder output
3. Scanning all 40 smart playlists — every one showed `skip_length = 139 + children_bytes` (a consistent +3 delta)
4. Bisect-testing: fixing only the skip-length made imports succeed; other byte differences were harmless

The purpose of the extra 3 bytes is unknown. It may be padding, an undocumented field, or a versioning artifact. No documentation of this format exists outside the [itunessmart](https://github.com/cvzi/itunes_smartplaylist) reverse-engineering project, which does not address this offset.

## Alternatives considered

1. **Keep 136 and work around crashes** — not viable; the crash is deterministic and affects all playlists
2. **Use 136 + string null terminator compensation** — initial hypothesis was that the delta correlated with omitted null terminators, but the +3 is constant regardless of rule types or string content

## Consequences

### Positive

- All rule types now import successfully, including top-level OR
- The encoder output matches real Music.app exports byte-for-byte (except for a cosmetic 1-byte trailing difference)

### Negative

- The +3 padding is empirically derived, not understood. A future Music.app update could change it
