# ADR-001: Boilerplate outer SLst declares N=2, omitting Apple's library identity child

## Status

Accepted

## Date

2026-03-08

## Context

Every `Smart Criteria` blob begins with a fixed outer `SLst` header that acts as the root AND group. Real `Library.xml` exports from Music.app consistently include N=3 children in this root node:

1. A library identity/name node (Apple inserts this as a safety check)
2. A MediaKind filter subexpression (restricts tracks to Music and Music Video)
3. The user's rules subexpression

The boilerplate embedded in the encoder was extracted from a real library export and then simplified. It declares N=2 (not N=3), omitting child 1.

## Decision

Keep the outer SLst at N=2. Omit the library identity child entirely.

The 579-byte `_BOILERPLATE` constant contains: the outer SLst header (N=2) at bytes 0–138, and the MediaKind filter at bytes 139–578. No identity node is included.

## Alternatives considered

1. **Replicate Apple's N=3 with a real identity node** — requires reverse-engineering the identity node format, which is playlist-name-specific and undocumented. No tooling exists to generate it.
2. **Keep N=2 with a zeroed placeholder node** — Music.app reads the child count and would attempt to parse a third child from arbitrary bytes, causing a crash or silent rejection.

## Consequences

### Positive

- Boilerplate is truly fixed (identical across all playlists), simplifying the encoder to a single constant prepend.
- Music.app accepts N=2 without complaint; the identity node is not required for import.

### Negative

- Generated blobs are structurally different from native exports. If Apple adds a hard requirement for the identity node in a future macOS version, the boilerplate would need to be regenerated.
