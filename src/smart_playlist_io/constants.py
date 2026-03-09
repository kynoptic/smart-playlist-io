"""Shared constants for Apple Music Smart Playlist binary format.

Field IDs, enum maps, logic constants, and time units. Single source of truth
for both encoder and decoder — forward maps defined once, reverse maps derived.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Field IDs (name → byte value)
# ---------------------------------------------------------------------------

STRING_FIELDS = {
    "Name": 0x02,
    "Artist": 0x04,
    "Album": 0x03,
    "Genre": 0x08,
    "Comments": 0x0E,
    "Grouping": 0x27,
    "Composer": 0x12,
    "AlbumArtist": 0x47,
    "Kind": 0x09,
}

INT_FIELDS = {
    "Rating": 0x19,
    "Year": 0x07,
    "Plays": 0x16,
    "BPM": 0x23,
    "BitRate": 0x05,
    "TrackNumber": 0x0B,
    "DiskNumber": 0x18,
    "Size": 0x0C,
    "Duration": 0x0D,
    "Skips": 0x44,
}

BOOL_FIELDS = {
    "Checked": 0x1D,
    "HasArtwork": 0x25,
}

DATE_FIELDS = {
    "DateAdded": 0x10,
    "DateModified": 0x0A,
    "LastPlayed": 0x17,
    "LastSkipped": 0x45,
}

ENUM_FIELDS = {
    "iCloudStatus": 0x86,
    "Love": 0x9A,
    "MediaKind": 0x3C,
    "Location": 0x85,
}

# ---------------------------------------------------------------------------
# Reverse maps (byte value → name), derived from forward maps
# ---------------------------------------------------------------------------

FIELD_NAMES: dict[int, str] = {}
for _map in (STRING_FIELDS, INT_FIELDS, BOOL_FIELDS, DATE_FIELDS, ENUM_FIELDS):
    FIELD_NAMES.update({v: k for k, v in _map.items()})

# Set lookups for fast field-type dispatch in decoder
STRING_FIELD_IDS = set(STRING_FIELDS.values())
INT_FIELD_IDS = set(INT_FIELDS.values())
BOOL_FIELD_IDS = set(BOOL_FIELDS.values())
DATE_FIELD_IDS = set(DATE_FIELDS.values())
ENUM_FIELD_IDS = set(ENUM_FIELDS.values())

# ---------------------------------------------------------------------------
# Enum value maps (name → byte value)
# ---------------------------------------------------------------------------

ICLOUD_STATUS = {
    "Purchased": 0x01,
    "Matched": 0x02,
    "Uploaded": 0x03,
    "Ineligible": 0x04,
    "Local Only": 0x05,
    "Duplicate": 0x07,
    "Apple Music": 0x08,
    "No Longer Available": 0x09,
}
LOVE_STATUS = {"None": 0x00, "Loved": 0x02, "Disliked": 0x03}
MEDIA_KIND = {"Music": 0x01, "Movie": 0x02, "Podcast": 0x04, "Music Video": 0x20}
LOCATION_KIND = {"Computer": 0x01, "iCloud": 0x10}

# Reverse enum maps (byte value → name)
ICLOUD_NAMES = {v: k for k, v in ICLOUD_STATUS.items()}
LOVE_NAMES = {v: k for k, v in LOVE_STATUS.items()}
MEDIA_NAMES = {v: k for k, v in MEDIA_KIND.items()}
LOCATION_NAMES = {v: k for k, v in LOCATION_KIND.items()}

# Enum lookup by field ID (for decoder)
ENUM_LOOKUPS = {
    0x86: ICLOUD_NAMES,
    0x9A: LOVE_NAMES,
    0x3C: MEDIA_NAMES,
    0x85: LOCATION_NAMES,
}

# Enum maps keyed by field name (for encoder)
ENUM_MAPS = {
    "iCloudStatus": ICLOUD_STATUS,
    "Love": LOVE_STATUS,
    "MediaKind": MEDIA_KIND,
    "Location": LOCATION_KIND,
}

# ---------------------------------------------------------------------------
# Logic constants
# ---------------------------------------------------------------------------

# LogicSign: controls whether a rule is positive (match) or negative (exclude)
SIGN_INT_POS = 0x00  # int/bool/date: match
SIGN_STR_POS = 0x01  # string: match
SIGN_INT_NEG = 0x02  # int/bool/date: exclude
SIGN_STR_NEG = 0x03  # string: exclude

# LogicRule: the comparison operator encoded in the rule block
LRULE_OTHER = 0x00  # context-dependent (range, relative-time)
LRULE_IS = 0x01  # equals
LRULE_CONT = 0x02  # contains
LRULE_START = 0x04  # starts with
LRULE_END = 0x08  # ends with
LRULE_GT = 0x10  # greater than
LRULE_LT = 0x40  # less than

# ---------------------------------------------------------------------------
# Time units
# ---------------------------------------------------------------------------

TIME_UNITS = {"days": 86400, "weeks": 604800, "months": 2628000}
TIME_UNIT_NAMES = {v: k for k, v in TIME_UNITS.items()}

# ---------------------------------------------------------------------------
# Smart Info constants
# ---------------------------------------------------------------------------

LIMIT_METHODS = {"items": 0x03, "minutes": 0x01, "hours": 0x04, "MB": 0x02, "GB": 0x05}
LIMIT_METHOD_NAMES = {v: k for k, v in LIMIT_METHODS.items()}

# SELECT_METHODS encodes directional names to byte values.
# most_played / least_played share byte 0x19 — direction is disambiguated
# by the SELECT_SIGN byte (0 = most/highest, 1 = least/lowest/oldest).
# Same pattern for most_recently_played/least_recently_played (0x1A)
# and most_recently_added/least_recently_added (0x15).
# Decoder recovers direction from the sign byte in decode_info_flags().
SELECT_METHODS = {
    "random": 0x02,
    "name": 0x05,
    "album": 0x06,
    "artist": 0x07,
    "genre": 0x09,
    "highest_rated": 0x1C,
    "lowest_rated": 0x01,
    "most_played": 0x19,
    "least_played": 0x19,
    "most_recently_played": 0x1A,
    "least_recently_played": 0x1A,
    "most_recently_added": 0x15,
    "least_recently_added": 0x15,
}

SELECT_METHOD_NAMES = {
    0x02: "random",
    0x05: "name",
    0x06: "album",
    0x07: "artist",
    0x09: "genre",
    0x15: "recently added",
    0x19: "played",
    0x1A: "recently played",
    0x1C: "highest rated",
}

# sign byte: 0 = most/highest (default), 1 = least/lowest/oldest
SELECT_SIGN = {
    "least_played": 1,
    "least_recently_played": 1,
    "least_recently_added": 1,
    "lowest_rated": 1,
}

# ---------------------------------------------------------------------------
# Smart Info byte offsets
# ---------------------------------------------------------------------------

_INFO_LIVEUPDATE = 0
_INFO_MATCHBOOL = 1
_INFO_LIMITBOOL = 2
_INFO_LIMITMETHOD = 3
_INFO_SELECTIONMETHOD = 7
_INFO_LIMITINT = 8  # 4 bytes big-endian
_INFO_LIMITCHECKED = 12
_INFO_SELECTIONMETHODSIGN = 13

# ---------------------------------------------------------------------------
# Date rule constants
# ---------------------------------------------------------------------------

# Sentinel value written at offset +61 in relative-time date rules (in_last /
# not_in_last). A uint32 of 0xFFFFFFFF signals "relative mode"; any other value
# at that offset is treated as an absolute timestamp.
_DATE_RELATIVE_SENTINEL = 0xFFFFFFFF

# Byte offset of the "SLst" magic within a 192-byte subexpression header block.
# Used by the decoder to distinguish nested subexpressions from leaf rules.
_SUBHDR_SLST_OFF = 53
