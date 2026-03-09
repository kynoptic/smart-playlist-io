# ADR-002: Top-level OR is emitted directly as the inner subexpression

## Status

Accepted

## Date

2026-03-08

## Context

The `Smart Criteria` blob structure is:

```
outer SLst (AND, N=2)
  └─ child 1: MediaKind filter (OR, N=2)
  └─ child 2: inner subexpression  ← user's rules go here
```

When a caller passes `OR([...])` as the root of their rule tree, the encoder must decide how to place it as child 2.

An early version of the encoder unconditionally wrapped the inner subexpression in an AND layer:

```
child 2: AND (N=1)
  └─ OR([...])   ← nested one level deeper than necessary
```

This caused Music.app to crash with error `-609 Connection invalid` when the playlist was imported. The crash affected all top-level OR playlists ("match any" playlists).

The fix was confirmed by comparing encoder output byte-for-byte against a real Music.app export of a "match any" playlist: Music.app emits OR directly as child 2, with no intermediate AND wrapper.

## Decision

When `encode()` receives a group node as its `rules` argument, emit that group's logic and children directly as the inner subexpression — whether AND or OR. Do not add an intermediate AND layer for OR roots.

If the caller passes a bare rule (not a group), promote it to a single-child AND for consistency.

## Alternatives considered

1. **Wrap OR in an AND (the original approach)** — causes deterministic -609 crash on import; not viable.
2. **Always emit AND and convert OR to individual rules** — loses the semantics of "match any"; not viable.

## Consequences

### Positive

- "Match any" (OR) playlists import successfully into Music.app.
- Encoder output is structurally identical to native Music.app exports for both AND and OR roots.

### Negative

- None identified. Both AND and OR roots are now equivalently supported.
