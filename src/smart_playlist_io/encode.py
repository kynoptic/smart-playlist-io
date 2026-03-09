"""Encoder for Apple Music Smart Playlist binary format (Smart Info + Smart Criteria).

Format reverse-engineered from itunessmart by cvzi (https://github.com/cvzi/itunes_smartplaylist),
based on banshee-itunes-import-plugin by Scott Peterson.

Usage:
    from smart_playlist_io import AND, OR, rule, encode

    rules = AND([
        rule("Rating", "greater", 3),
        rule("LastPlayed", "not_in_last", 6, "months"),
        OR([
            rule("Genre", "starts", "Ambient"),
            rule("Genre", "starts", "Electronic / Ambient"),
        ]),
    ])
    info_bytes, criteria_bytes = encode(rules, limit=25, select_by="most_played", live=True)
"""

from __future__ import annotations

import base64
import struct
from typing import Any, Literal, TypedDict, cast

from .constants import (
    _DATE_RELATIVE_SENTINEL,
    _INFO_LIMITBOOL,
    _INFO_LIMITCHECKED,
    _INFO_LIMITINT,
    _INFO_LIMITMETHOD,
    _INFO_LIVEUPDATE,
    _INFO_MATCHBOOL,
    _INFO_SELECTIONMETHOD,
    _INFO_SELECTIONMETHODSIGN,
    BOOL_FIELDS,
    DATE_FIELDS,
    ENUM_FIELDS,
    ENUM_MAPS,
    INT_FIELDS,
    LIMIT_METHODS,
    LRULE_CONT,
    LRULE_END,
    LRULE_GT,
    LRULE_IS,
    LRULE_LT,
    LRULE_OTHER,
    LRULE_START,
    SELECT_METHODS,
    SELECT_SIGN,
    SIGN_INT_NEG,
    SIGN_INT_POS,
    SIGN_STR_NEG,
    SIGN_STR_POS,
    STRING_FIELDS,
    TIME_UNITS,
)


class _GroupNode(TypedDict):
    """A group node produced by AND() or OR()."""

    type: Literal["group"]
    logic: Literal["AND", "OR"]
    children: list[RuleNode]


class _RuleNode(TypedDict):
    """A leaf rule node produced by rule()."""

    type: Literal["rule"]
    field: str
    op: str
    value: int | str | bool | tuple[int, int]
    unit: str | None


# Public type alias for the rule/group tree built by AND(), OR(), and rule().
RuleNode = _GroupNode | _RuleNode


# ---------------------------------------------------------------------------
# Fixed boilerplate (bytes 0-578): identical across all playlists.
# Extracted from Library-2021-02.xml. Contains:
#
#   [0-138]   Outer SLst header (AND logic, N=2).
#             The outer SLst is the root of the entire Smart Criteria blob.
#             N=2 means it has two children:
#               child 1 = MediaKind filter subexpr (see below)
#               child 2 = the user's rules subexpression (what we append after this blob)
#             Real library exports use N=3: Apple inserts a library identity/name node
#             as child 1 for safety checking before writing. We omit it - Music.app
#             accepts N=2 without complaint.
#
#   [139-330] MediaKind filter subexpr (OR logic, N=2).
#             Allows only Music (0x01) and Music Video (0x20) tracks through.
#             Without this filter, smart playlists may include podcasts, movies, etc.
#
#   [331-578] Two MediaKind int rules: MediaKind=Music and MediaKind=Music Video.
#             Each is a 124-byte int rule block (field_id=0x3c).
# ---------------------------------------------------------------------------

_BOILERPLATE = bytes.fromhex(
    "534c737400010001000000020000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000101000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000180"
    "534c737400010001000000020000000100000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000003c0000000100000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000044"
    "0000000000000001000000000000000000000000000000010000000000000001"
    "0000000000000000000000000000000100000000000000000000000000000000"
    "000000000000003c000000010000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000004400000000"
    "0000002000000000000000000000000000000001000000000000002000000000"
    "0000000000000000000000010000000000000000000000000000000000000000"
    "000000"
)

# Total byte length of a subexpression header block (53-byte prefix + 139-byte SLst).
_SUBEXPR_BLOCK_SIZE = 192

# The skip-length field (bytes 51-52 of the header) tells the parser how many bytes
# to skip from the *start of the node* to reach the next sibling. The formula is:
#   skip_length = _SUBEXPR_SKIP_BASE + total_children_bytes
# so that: start_of_node + skip_length + 56 = start_of_next_sibling.
# The +3 padding (139 vs the theoretical 136 = 192 - 56) is required by Music.app:
# every real library export consistently shows skip_length = 139 + children_bytes.
# The exact purpose of the extra 3 bytes is unknown, but omitting them causes
# Music.app to crash (-609) on import.
_SUBEXPR_SKIP_BASE = 139


# ---------------------------------------------------------------------------
# Rule / group builders
# ---------------------------------------------------------------------------


def AND(children: list[RuleNode]) -> _GroupNode:
    """Create an AND group."""
    return {"type": "group", "logic": "AND", "children": children}


def OR(children: list[RuleNode]) -> _GroupNode:
    """Create an OR group."""
    return {"type": "group", "logic": "OR", "children": children}


def rule(
    field: str,
    op: str,
    value: str | int | bool | tuple[int, int],
    unit: str | None = None,
) -> _RuleNode:
    """Create a single rule.

    Args:
        field: Field name (e.g. "Genre", "Rating", "LastPlayed", "iCloudStatus").
        op: Operator ("is", "is_not", "contains", "not_contains", "starts",
            "ends", "greater", "less", "between", "in_last", "not_in_last").
        value: Comparison value. Type depends on field category.
        unit: Time unit for date ops ("days", "weeks", "months").
    """
    return {"type": "rule", "field": field, "op": op, "value": value, "unit": unit}


# ---------------------------------------------------------------------------
# Encoding internals
# ---------------------------------------------------------------------------


def _encode_string_data(text: str, *, null_terminate: bool = True) -> bytes:
    """Encode a string as UTF-16 LE with optional null terminator pair.

    Apple omits the null terminator from the last string rule in a criteria
    blob - the parser handles end-of-file as a natural string terminator.
    """
    out = text.encode("utf-16-le")
    if null_terminate and text:  # empty string needs no null (file just ends before string area)
        out += b"\x00\x00"
    return out


def _encode_time_value(n: int) -> bytes:
    """Apple stores time values as the bitwise complement of (n-1)."""
    raw = (n - 1) % 4294967296
    return bytes(255 - b for b in struct.pack(">I", raw))


# Offsets within a 124-byte int/enum/bool/date rule block
_IRULE_OFF_FIELD_ID = 0
_IRULE_OFF_SIGN = 1
_IRULE_OFF_EXTRA_FLAG = 3  # range(1) or relative-time(2) modifier
_IRULE_OFF_LOGIC_RULE = 4
_IRULE_OFF_REQUIRED_A = 52  # constant 0x44 Music.app requires
_IRULE_OFF_REQUIRED_B = 76  # constant 0x01 Music.app requires
_IRULE_OFF_REQUIRED_C = 100  # constant 0x01 Music.app requires
_IRULE_OFF_VAL_A = 57  # primary value (big-endian uint32)
_IRULE_OFF_VAL_B = 81  # secondary value for range rules


def _make_int_rule(
    field_id: int,
    sign: int,
    logic_rule: int,
    val_a: int,
    val_b: int | None = None,
    extra_flag: int = 0,
) -> bytes:
    """Build a 124-byte int/enum/bool/date rule block.

    Byte layout (all unlisted bytes are zero):
      [0]     field_id
      [1]     sign (SIGN_INT_POS=0x00 match, SIGN_INT_NEG=0x02 exclude)
      [2]     always 0
      [3]     extra_flag: 0x01 = range ("between"), 0x02 = relative-date mode
      [4]     logic_rule (LRULE_*)
      [5-51]  zeros
      [52]    0x44 - required constant; purpose unknown, but Music.app crashes or
              silently rejects the rule without it in some configurations
      [53-56] zeros
      [57-60] val_a BE uint32 - lower bound (or sole value for non-range ops)
      [61-75] zeros
      [76]    0x01 - required constant (same caveat as 0x44 above)
      [77-80] zeros
      [81-84] val_b BE uint32 - upper bound (= val_a for non-range ops)
      [85-99] zeros
      [100]   0x01 - required constant (same caveat)
      [101-123] zeros

    For non-range ops val_b is set equal to val_a; the parser appears to read
    it regardless and both values must be consistent.
    """
    if val_b is None:
        val_b = val_a
    buf = bytearray(124)
    buf[_IRULE_OFF_FIELD_ID] = field_id
    buf[_IRULE_OFF_SIGN] = sign
    buf[_IRULE_OFF_EXTRA_FLAG] = extra_flag
    buf[_IRULE_OFF_LOGIC_RULE] = logic_rule
    # Three required constants whose exact purpose is unknown. The itunessmart
    # reference parser ignores them, but Music.app requires them - omitting any
    # one causes the rule to be silently dropped or the app to crash.
    buf[_IRULE_OFF_REQUIRED_A] = 0x44
    buf[_IRULE_OFF_REQUIRED_B] = 0x01
    buf[_IRULE_OFF_REQUIRED_C] = 0x01
    struct.pack_into(">I", buf, _IRULE_OFF_VAL_A, val_a)
    struct.pack_into(">I", buf, _IRULE_OFF_VAL_B, val_b)
    return bytes(buf)


# Offsets within a 192-byte subexpression header block
_SUBHDR_OFF_FLAGS = 4  # two prefix flag bytes (always 0x01 0x01)
_SUBHDR_OFF_SKIP_LEN = 51  # BE uint16: parser skips (skip_len + 56) bytes to reach next sibling
_SUBHDR_OFF_SLST_MAGIC = 53  # "SLst" 4-byte magic
_SUBHDR_OFF_SLST_VER = 57  # BE uint32 version: 0x00010001
_SUBHDR_OFF_CHILD_COUNT = 61  # BE uint32 number of child rules/groups
_SUBHDR_OFF_LOGIC = 68  # 0x01 = OR, 0x00 = AND


def _make_subexpr_header(logic: str, n: int, children_size: int = 0) -> bytes:
    """Build a 192-byte subexpression header (53-byte prefix + 139-byte embedded SLst).

    Byte layout:
      [0-3]    zeros (purpose unknown)
      [4-5]    0x01 0x01 - prefix flags, always this value, purpose unknown
      [6-50]   zeros
      [51-52]  BE uint16 skip-length = _SUBEXPR_SKIP_BASE + children_size (139 + N bytes).
               The parser reads skip_length, then jumps (skip_length + 56) bytes forward
               from the start of this node to find the next sibling. The base of 139
               (vs theoretical 136 = 192 - 56) includes 3 bytes of required padding
               whose purpose is unknown - see _SUBEXPR_SKIP_BASE comment.
      [53-56]  "SLst" magic (0x534c7374) - required by Music.app
      [57-60]  BE uint32 version 0x00010001 - required by Music.app
      [61-64]  BE uint32 N = child count
      [65-67]  zeros
      [68]     logic: 0x01 = OR, 0x00 = AND
      [69-191] zeros

    itunessmart only reads N (offset 61) and logic (offset 68); Music.app reads
    and validates the full SLst header including magic and version.
    """
    buf = bytearray(_SUBEXPR_BLOCK_SIZE)
    # Prefix flags (purpose unknown, always 0x01 0x01)
    buf[_SUBHDR_OFF_FLAGS] = 0x01
    buf[_SUBHDR_OFF_FLAGS + 1] = 0x01
    # Skip-length: parser reads this + 56 to skip past the entire subexpr node
    struct.pack_into(">H", buf, _SUBHDR_OFF_SKIP_LEN, _SUBEXPR_SKIP_BASE + children_size)
    # Embedded SLst structure
    buf[_SUBHDR_OFF_SLST_MAGIC : _SUBHDR_OFF_SLST_MAGIC + 4] = b"SLst"
    struct.pack_into(">I", buf, _SUBHDR_OFF_SLST_VER, 0x00010001)
    struct.pack_into(">I", buf, _SUBHDR_OFF_CHILD_COUNT, n)
    buf[_SUBHDR_OFF_LOGIC] = 0x01 if logic == "OR" else 0x00
    return bytes(buf)


# Fill pattern used by Music.app at several offsets within date rule blocks.
# The value 0x2dae2dae has no known semantic meaning - it appears to be a
# placeholder Apple uses to mark "no value" in otherwise-unused fields.
# It occupies bytes [53-60] and [77-84] of the 124-byte date rule block.
_DATE_FILL = b"\x2d\xae\x2d\xae"


def _encode_string_rule(field: str, op: str, value: str, last: bool) -> bytes:
    """Build a string rule: 54-byte header followed by UTF-16 LE string data.

    Header byte layout:
      [0]     field_id
      [1]     sign (SIGN_STR_POS=0x01 match, SIGN_STR_NEG=0x03 exclude)
      [2-3]   zeros
      [4]     logic_rule (LRULE_IS / LRULE_CONT / LRULE_START / LRULE_END)
      [5-51]  zeros
      [52]    byte length of the string value encoded as UTF-16 LE, i.e. len(s) * 2.
              Does NOT include the null terminator bytes.
      [53]    always 0
    [54+]     UTF-16 LE string bytes, followed by a null terminator (0x00 0x00)
              for every rule except the very last one in the criteria blob.

    The null terminator omission on the last rule is Apple's format: the parser
    treats end-of-blob as a natural string terminator. The `last` parameter
    propagates through _encode_node so this function knows whether to omit it.
    """
    fid = STRING_FIELDS[field]
    sign = SIGN_STR_NEG if op in ("is_not", "not_contains") else SIGN_STR_POS
    logic_rule = {
        "is": LRULE_IS,
        "is_not": LRULE_IS,
        "contains": LRULE_CONT,
        "not_contains": LRULE_CONT,
        "starts": LRULE_START,
        "ends": LRULE_END,
    }[op]
    str_data = _encode_string_data(value, null_terminate=not last)
    buf = bytearray(54)
    buf[0] = fid
    buf[1] = sign
    buf[4] = logic_rule
    if len(value) > 127:
        raise ValueError(f"String value too long ({len(value)} chars, max 127)")
    buf[52] = len(value) * 2  # UTF-16 byte length (excluding null terminator)
    return bytes(buf) + str_data


def _encode_int_rule(field: str, op: str, value: int | tuple[int, int]) -> bytes:
    fid = INT_FIELDS[field]
    # Apple stores Rating as 0-100 in increments of 20 (1 star = 20, 5 stars = 100).
    # All other int fields are stored at face value.
    scale = 20 if field == "Rating" else 1

    if op in ("is", "is_not"):
        if not isinstance(value, int):
            raise TypeError(f"Expected int for op {op!r}, got {type(value).__name__}")
        sign = SIGN_INT_POS if op == "is" else SIGN_INT_NEG
        return _make_int_rule(fid, sign, LRULE_IS, value * scale)
    if op == "greater":
        if not isinstance(value, int):
            raise TypeError(f"Expected int for op {op!r}, got {type(value).__name__}")
        return _make_int_rule(fid, SIGN_INT_POS, LRULE_GT, value * scale)
    if op == "less":
        if not isinstance(value, int):
            raise TypeError(f"Expected int for op {op!r}, got {type(value).__name__}")
        return _make_int_rule(fid, SIGN_INT_POS, LRULE_LT, value * scale)
    if op == "between":
        if not isinstance(value, tuple):
            raise TypeError(f"Expected tuple for op 'between', got {type(value).__name__}")
        lo, hi = value
        # For Rating, the upper bound gets +9: confirmed from real library exports
        # (e.g. "between 5 and 5" -> val_a=100, val_b=109). The +9 ensures Music.app's
        # internal comparison includes the upper boundary correctly, since the parser
        # appears to use a half-open interval internally. extra_flag=0x01 tells the
        # parser this is a range rule with both val_a and val_b meaningful.
        val_b = hi * scale + 9 if field == "Rating" else hi * scale
        return _make_int_rule(fid, SIGN_INT_POS, LRULE_OTHER, lo * scale, val_b, extra_flag=0x01)
    raise ValueError(f"Unknown int op: {op!r}")


def _encode_bool_rule(field: str, value: bool) -> bytes:
    fid = BOOL_FIELDS[field]
    # Parser interprets: value = (sign != SIGN_INT_POS), so NEG -> True, POS -> False
    sign = SIGN_INT_NEG if value else SIGN_INT_POS
    return _make_int_rule(fid, sign, LRULE_IS, 0)


def _encode_date_rule(field: str, op: str, value: int, unit: str | None) -> bytes:
    """Build a 124-byte date rule block.

    Date rules reuse the same 124-byte layout as int rules but repurpose several
    fields, and add fill patterns in positions that would be zeros in int rules.

    Common base layout (shared by all date ops):
      [0]     field_id
      [52]    0x44 - same required constant as int rules
      [53-60] _DATE_FILL x 2 - 8 bytes of 0x2dae fill (purpose unknown)
      [77-84] _DATE_FILL x 2 - 8 bytes of 0x2dae fill (purpose unknown)
      [100]   0x01 - same required constant as int rules

    For "in_last" / "not_in_last" (relative-time ops), additional fields:
      [1]     sign: SIGN_INT_POS (in_last) or SIGN_INT_NEG (not_in_last)
      [3]     0x02 - extra_flag for relative-time mode
      [4]     LRULE_OTHER (the time value determines the comparison, not a logic rule)
      [61-64] 0xffffffff - sentinel that marks this as a relative-time rule
              (distinguishes it from an absolute timestamp at the same offset)
      [65-68] encoded time value N, formula: bytes(255 - b for b in pack(">I", (N-1) % 2^32))
              i.e. the bitwise complement of (N-1), big-endian. Derived empirically
              from real library exports by comparing N=1,7,30 day/week/month rules.
      [73-76] time unit in seconds: days=86400, weeks=604800, months=2628000

    For "after" / "before" (absolute-timestamp ops):
      [1]     SIGN_INT_POS
      [4]     LRULE_GT (after) or LRULE_LT (before)
      [57-60] absolute timestamp as BE uint32 (Mac epoch: seconds since 2001-01-01)
    """
    fid = DATE_FIELDS[field]
    buf = bytearray(124)
    buf[0] = fid
    # Constant bytes and fill patterns Music.app requires (see layout above)
    buf[52] = 0x44
    buf[53:57] = _DATE_FILL
    buf[57:61] = _DATE_FILL
    buf[77:81] = _DATE_FILL
    buf[81:85] = _DATE_FILL
    buf[100] = 0x01
    if op in ("in_last", "not_in_last"):
        if unit is None:
            raise ValueError(
                f"unit is required for {op!r} date rules (e.g. 'days', 'weeks', 'months')"
            )
        buf[1] = SIGN_INT_POS if op == "in_last" else SIGN_INT_NEG
        buf[3] = 0x02  # extra_flag: relative-time mode
        buf[4] = LRULE_OTHER
        struct.pack_into(">I", buf, 61, _DATE_RELATIVE_SENTINEL)  # marks relative-time mode
        buf[65:69] = _encode_time_value(value)
        struct.pack_into(">I", buf, 73, TIME_UNITS[unit])
    elif op == "after":
        buf[1] = SIGN_INT_POS
        buf[4] = LRULE_GT
        struct.pack_into(">I", buf, 57, value)
    elif op == "before":
        buf[1] = SIGN_INT_POS
        buf[4] = LRULE_LT
        struct.pack_into(">I", buf, 57, value)
    else:
        raise ValueError(f"Unknown date op: {op!r}")
    return bytes(buf)


def _encode_enum_rule(field: str, op: str, value: str) -> bytes:
    fid = ENUM_FIELDS[field]
    raw_val = ENUM_MAPS[field][value]
    sign = SIGN_INT_POS if op == "is" else SIGN_INT_NEG
    return _make_int_rule(fid, sign, LRULE_IS, raw_val, raw_val)


def _encode_node(node: RuleNode, last: bool = False) -> bytes:
    """Recursively encode a rule or group node.

    last=True signals that this is the final element in the criteria blob,
    so string rules should omit their trailing null terminator (Apple's format).
    """
    if node["type"] == "group":
        children = node["children"]
        n = len(children)
        encoded_children = [
            _encode_node(child, last=(last and i == n - 1)) for i, child in enumerate(children)
        ]
        children_blob = b"".join(encoded_children)
        header = _make_subexpr_header(node["logic"], n, len(children_blob))
        return header + children_blob

    field = node["field"]
    op = node["op"]
    value = node["value"]
    unit = node["unit"]

    if field in STRING_FIELDS:
        return _encode_string_rule(field, op, cast(str, value), last)
    if field in INT_FIELDS:
        return _encode_int_rule(field, op, cast("int | tuple[int, int]", value))
    if field in BOOL_FIELDS:
        return _encode_bool_rule(field, cast(bool, value))
    if field in DATE_FIELDS:
        return _encode_date_rule(field, op, cast(int, value), unit)
    if field in ENUM_FIELDS:
        return _encode_enum_rule(field, op, cast(str, value))

    raise ValueError(f"Unknown field: {field!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def encode(
    rules: RuleNode,
    *,
    limit: int | None = None,
    limit_by: str = "items",
    select_by: str = "most_played",
    live: bool = True,
    only_checked: bool = False,
) -> tuple[bytes, bytes]:
    """
    Encode smart playlist rules to (smart_info_bytes, smart_criteria_bytes).

    rules       : AND/OR/rule dict from the builder functions
    limit       : int or None
    limit_by    : "items" | "minutes" | "hours" | "MB" | "GB"
    select_by   : selection method (see SELECT_METHODS keys)
    live        : bool  live-updating
    only_checked: bool  exclude unchecked items

    Both AND and OR are supported as the top-level logic group. An earlier version
    incorrectly wrapped top-level OR in an extra AND layer, which caused Music.app
    to crash (-609). The fix: emit OR directly as the inner subexpression, matching
    how Music.app itself encodes "match any" playlists.
    """
    if limit_by not in LIMIT_METHODS:
        raise ValueError(f"Invalid limit_by={limit_by!r}. Valid values: {sorted(LIMIT_METHODS)}")
    if select_by not in SELECT_METHODS:
        raise ValueError(f"Invalid select_by={select_by!r}. Valid values: {sorted(SELECT_METHODS)}")

    # Smart Info (112 bytes)
    info = bytearray(112)
    info[_INFO_LIVEUPDATE] = 0x01 if live else 0x00
    info[_INFO_MATCHBOOL] = 0x01

    if limit is not None:
        info[_INFO_LIMITBOOL] = 0x01
        info[_INFO_LIMITMETHOD] = LIMIT_METHODS[limit_by]
        info[_INFO_SELECTIONMETHOD] = SELECT_METHODS[select_by]
        info[_INFO_SELECTIONMETHODSIGN] = SELECT_SIGN.get(select_by, 0)
        struct.pack_into(">I", info, _INFO_LIMITINT, limit)

    if only_checked:
        info[_INFO_LIMITCHECKED] = 0x01

    # Smart Criteria: _BOILERPLATE provides the outer SLst (AND, N=2) plus the
    # MediaKind filter as its first child. We append the inner subexpression as
    # the second child - either AND or OR logic is valid here. If the caller
    # passed a bare rule instead of a group, promote it to a one-child AND.
    if rules["type"] == "group":
        inner_logic = rules["logic"]
        children = rules["children"]
    else:
        inner_logic = "AND"
        children = [rules]

    n = len(children)
    inner_body = b"".join(_encode_node(c, last=(i == n - 1)) for i, c in enumerate(children))
    inner_subexpr = _make_subexpr_header(inner_logic, n, len(inner_body))
    criteria = _BOILERPLATE + inner_subexpr + inner_body

    return bytes(info), criteria


def encode_b64(rules: RuleNode, **kwargs: Any) -> tuple[str, str]:
    """Return (smart_info_b64, smart_criteria_b64) as base64 strings."""
    info, crit = encode(rules, **kwargs)
    return base64.b64encode(info).decode(), base64.b64encode(crit).decode()
