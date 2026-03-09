# Reverse-engineered format constants

**Diátaxis type**: Explanation

Two constants in the encoder are empirically derived from real `Library.xml` exports rather than from a complete understanding of the binary format. This document records what was found and why the values are what they are.

## Skip-length base: 139 (not 136)

`_SUBEXPR_SKIP_BASE` governs bytes 51–52 of each subexpression header — a BE uint16 skip-length that tells the Music.app parser how many bytes to advance to the next sibling node.

The theoretical formula is `136 + children_bytes`, derived from the 192-byte header size minus a 56-byte internal parser offset. Using 136 causes a deterministic `-609 Connection invalid` crash on import.

The actual value was determined by:

1. Exporting `Library.xml` from a working Music.app library
2. Hex-diffing 40 smart playlists against encoder output
3. Observing `skip_length = 139 + children_bytes` consistently across all rule types and string lengths

The extra +3 is constant regardless of content. Its purpose is unknown — likely padding, an undocumented field count, or a versioning artifact. No public documentation of this format exists.

**If Music.app imports fail after a macOS update, this constant is the first thing to check.**

## Rating scale and "between" upper-bound offset: +9

Apple Music stores star ratings as integers 0–100 in steps of 20 (1 star = 20, 5 stars = 100). The encoder multiplies user-facing star values by 20 before writing them to the rule block.

For `between` (range) rules, the int block carries two values: `val_a` (lower bound) and `val_b` (upper bound). Real exports consistently show the upper bound stored as `hi * 20 + 9`, not `hi * 20`. A "between 5 and 5" rule encodes `val_a = 100`, `val_b = 109`.

The +9 applies only to:
- `field_id == 0x19` (Rating)
- `extra_flag == 0x01` (range mode)

Without the offset, Music.app silently excludes the upper boundary — a "between 4 and 5" rule would not match 5-star tracks. The +19 (full step) hypothesis was ruled out because real exports consistently show +9.

The decoder reverses this with `(val_b - 9) // 20` under the same conditions.

The purpose of the +9 is unknown.

## String field character limit: 127

String rule values are encoded as UTF-16 LE. The byte length of the encoded string is written into a single byte at offset 52 of the string rule header. A single byte can hold a maximum value of 255, and UTF-16 uses 2 bytes per character, so the maximum number of characters is 255 ÷ 2 = **127**.

Affected fields include: `Name`, `Artist`, `Album`, `Genre`, `Comments`, `Grouping`, `Composer`, `AlbumArtist`, `Kind`, and any other string-type field.

Passing a value longer than 127 characters raises `ValueError` with a message indicating the field name and the excess length. Values must be truncated before calling `rule()` if the source data may exceed this limit.
