"""Decode Apple Music Smart Playlist binary format into human-readable rules.

Binary format knowledge derived from itunessmart by cvzi
(https://github.com/cvzi/itunes_smartplaylist), based on
banshee-itunes-import-plugin by Scott Peterson.
See NOTICE for license details.

Handles all Apple Music Smart Criteria features including nested AND/OR groups,
iCloudStatus 9 ("No Longer Available"), and non-standard boilerplate-free blobs.

Usage (library):
    from smart_playlist_io import decode_criteria, decode_info_flags

Usage (CLI):
    decode-smart-playlists /path/to/Library.xml
    decode-smart-playlists /path/to/Library.xml --out baseline.md
"""

from __future__ import annotations

import base64
import plistlib
import struct
import sys
from pathlib import Path

from .constants import (
    BOOL_FIELD_IDS,
    DATE_FIELD_IDS,
    ENUM_FIELD_IDS,
    ENUM_LOOKUPS,
    FIELD_NAMES,
    LIMIT_METHOD_NAMES,
    LRULE_GT,
    LRULE_LT,
    SELECT_METHOD_NAMES,
    STRING_FIELD_IDS,
    TIME_UNIT_NAMES,
)

# Smart Info offsets
_INFO_LIVEUPDATE = 0
_INFO_LIMITBOOL = 2
_INFO_LIMITMETHOD = 3
_INFO_SELECTIONMETHOD = 7
_INFO_LIMITINT = 8
_INFO_LIMITCHECKED = 12
_INFO_SELECTIONMETHODSIGN = 13


# ---------------------------------------------------------------------------
# Rule decoders
# ---------------------------------------------------------------------------


def _decode_int_rule(data: bytes, offset: int) -> tuple[str, int]:
    """Decode a 124-byte int/enum/bool/date rule."""
    field_id = data[offset]
    sign = data[offset + 1]
    extra_flag = data[offset + 3]
    logic_rule = data[offset + 4]
    field_name = FIELD_NAMES.get(field_id, f"field_0x{field_id:02x}")

    val_a = struct.unpack_from(">I", data, offset + 57)[0]
    val_b = struct.unpack_from(">I", data, offset + 81)[0]
    negated = sign in (0x02, 0x03)

    if field_id in BOOL_FIELD_IDS:
        return f"{field_name} is {negated}", offset + 124

    if field_id in ENUM_FIELD_IDS:
        lookup = ENUM_LOOKUPS.get(field_id, {})
        val_name = lookup.get(val_a, f"0x{val_a:02x}")
        op = "is not" if negated else "is"
        return f'{field_name} {op} "{val_name}"', offset + 124

    if field_id in DATE_FIELD_IDS:
        sentinel = struct.unpack_from(">I", data, offset + 61)[0]
        if extra_flag == 0x02 and sentinel == 0xFFFFFFFF:
            time_encoded = data[offset + 65 : offset + 69]
            time_raw = struct.unpack(">I", bytes(255 - b for b in time_encoded))[0]
            time_val = time_raw + 1
            time_unit_secs = struct.unpack_from(">I", data, offset + 73)[0]
            unit_name = TIME_UNIT_NAMES.get(time_unit_secs, f"{time_unit_secs}s")
            op = "not in last" if negated else "in last"
            return f"{field_name} {op} {time_val} {unit_name}", offset + 124
        op = ">" if logic_rule == LRULE_GT else "<" if logic_rule == LRULE_LT else "is"
        if negated:
            op = f"not {op}"
        return f"{field_name} {op} {val_a}", offset + 124

    # Int field - Rating is stored as 0-100 (20 per star)
    scale = 20 if field_id == 0x19 else 1
    display_a = val_a // scale if scale > 1 else val_a
    if extra_flag == 0x01:  # between
        display_b = (
            (val_b - 9) // scale
            if field_id == 0x19 and val_b > 0
            else val_b // scale
            if scale > 1
            else val_b
        )
        op_str = "not between" if negated else "between"
        return f"{field_name} {op_str} {display_a} and {display_b}", offset + 124

    if logic_rule == LRULE_GT:
        return f"{field_name} > {display_a}", offset + 124
    if logic_rule == LRULE_LT:
        return f"{field_name} < {display_a}", offset + 124
    op = "is not" if negated else "is"
    return f"{field_name} {op} {display_a}", offset + 124


def _decode_string_rule(data: bytes, offset: int) -> tuple[str, int]:
    """Decode a string rule (54-byte header + variable-length UTF-16 LE string)."""
    field_id = data[offset]
    sign = data[offset + 1]
    logic_rule = data[offset + 4]
    str_len = data[offset + 52]
    field_name = FIELD_NAMES.get(field_id, f"field_0x{field_id:02x}")

    negated = sign in (0x02, 0x03)
    op_map = {
        0x01: ("is", "is not"),
        0x02: ("contains", "does not contain"),
        0x04: ("starts with", "does not start with"),
        0x08: ("ends with", "does not end with"),
    }
    ops = op_map.get(logic_rule, ("?", "?"))
    op_name = ops[1] if negated else ops[0]

    str_start = offset + 54
    available = min(str_len, len(data) - str_start)
    str_bytes = data[str_start : str_start + available]
    # Pad with 0x00 if we have an odd byte count (last string in blob may be truncated)
    if len(str_bytes) % 2 != 0:
        str_bytes += b"\x00"
    try:
        value = str_bytes.decode("utf-16-le")
    except Exception:
        value = f"<{str_len} bytes>"

    pos = str_start + str_len
    if pos + 1 < len(data) and data[pos] == 0 and data[pos + 1] == 0:
        pos += 2

    return f'{field_name} {op_name} "{value}"', pos


# ---------------------------------------------------------------------------
# Subexpression / group decoders
# ---------------------------------------------------------------------------


def _decode_children(data: bytes, child_offset: int, child_count: int) -> tuple[list, int]:
    """Decode N child rules/subexpressions starting at child_offset."""
    rules: list[str | list] = []
    for _ in range(child_count):
        if child_offset >= len(data):
            rules.append(f"<truncated at {child_offset}>")
            break

        if (
            child_offset + 57 <= len(data)
            and data[child_offset + 53 : child_offset + 57] == b"SLst"
        ):
            skip_len = struct.unpack_from(">H", data, child_offset + 51)[0]
            sub_rules = _decode_subexpr(data, child_offset)
            rules.append(sub_rules)
            child_offset = child_offset + skip_len + 56
        else:
            field_id = data[child_offset]
            if field_id in STRING_FIELD_IDS:
                desc, child_offset = _decode_string_rule(data, child_offset)
            else:
                desc, child_offset = _decode_int_rule(data, child_offset)
            rules.append(desc)

    return rules, child_offset


def _decode_subexpr(data: bytes, offset: int) -> list:
    """Decode a subexpression (192-byte header + children). Returns [logic, *rules]."""
    child_count = struct.unpack_from(">I", data, offset + 61)[0]
    logic = "OR" if data[offset + 68] == 0x01 else "AND"
    rules, _ = _decode_children(data, offset + 192, child_count)
    return [logic] + rules


def decode_criteria(data: bytes) -> list:
    """Decode Smart Criteria blob into a rule tree.

    Handles two formats:
    1. Standard: 579-byte boilerplate (outer SLst + MediaKind filter) + inner subexpr
    2. Non-standard: SLst directly at offset 0 (simpler playlists without MediaKind filter)
    """
    # Standard format with 579-byte boilerplate
    if len(data) >= 579 + 192 and data[579 + 53 : 579 + 57] == b"SLst":
        return _decode_subexpr(data, 579)

    # Non-standard: starts with SLst directly (139-byte header + children)
    if data[0:4] == b"SLst":
        child_count = struct.unpack_from(">I", data, 8)[0]
        logic = "OR" if data[15] == 0x01 else "AND"
        rules, _ = _decode_children(data, 139, child_count)
        return [logic] + rules

    return ["RAW", f"<unrecognized format: {len(data)} bytes>"]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _format_rules(rules: list, indent: int = 0) -> str:
    """Format decoded rules into readable text."""
    lines = []
    prefix = "  " * indent

    if not rules:
        return f"{prefix}<empty>"

    logic = rules[0]
    if logic in ("AND", "OR"):
        lines.append(f"{prefix}{logic}:")
        for child in rules[1:]:
            if isinstance(child, list):
                lines.append(_format_rules(child, indent + 1))
            else:
                lines.append(f"{prefix}  {child}")
    else:
        for item in rules:
            lines.append(f"{prefix}{item}")

    return "\n".join(lines)


def decode_info_flags(info_bytes: bytes) -> str:
    """Decode Smart Info into a compact annotation string."""
    parts = []
    if info_bytes[_INFO_LIMITCHECKED]:
        parts.append("only checked")
    if info_bytes[_INFO_LIVEUPDATE]:
        parts.append("live updating")
    if info_bytes[_INFO_LIMITBOOL]:
        limit_val = struct.unpack_from(">I", info_bytes, _INFO_LIMITINT)[0]
        limit_by = LIMIT_METHOD_NAMES.get(info_bytes[_INFO_LIMITMETHOD], "?")
        sel_method = SELECT_METHOD_NAMES.get(info_bytes[_INFO_SELECTIONMETHOD], "?")
        sel_sign = info_bytes[_INFO_SELECTIONMETHODSIGN]
        prefix = "least" if sel_sign == 1 else "most"
        parts.append(f"limit {limit_val} {limit_by}, {prefix} {sel_method}")
    return ", ".join(parts) if parts else "no flags"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Decode smart playlists from Library XML")
    parser.add_argument("library", help="Path to Library XML export")
    parser.add_argument("--out", help="Write output to file instead of stdout")
    args = parser.parse_args()

    xml_path = Path(args.library)
    if not xml_path.exists():
        print(f"Error: {xml_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {xml_path}...", file=sys.stderr)
    with open(xml_path, "rb") as f:
        lib = plistlib.load(f)

    playlists = lib.get("Playlists", [])
    smart = []
    for p in playlists:
        if "Smart Info" in p and "Smart Criteria" in p:
            name = p.get("Name", "(unnamed)")
            info_bytes = p["Smart Info"]
            crit_bytes = p["Smart Criteria"]
            if isinstance(info_bytes, str):
                info_bytes = base64.b64decode(info_bytes)
            if isinstance(crit_bytes, str):
                crit_bytes = base64.b64decode(crit_bytes)
            smart.append((name, info_bytes, crit_bytes))

    print(f"Found {len(smart)} smart playlists", file=sys.stderr)

    lines = []
    lines.append("# Smart playlist baseline")
    lines.append("")
    lines.append(f"Source: `{xml_path.name}`")
    lines.append(f"Playlists: {len(smart)}")
    lines.append("")

    for name, info_bytes, crit_bytes in sorted(smart, key=lambda x: x[0].lower()):
        rules = decode_criteria(crit_bytes)
        info_text = decode_info_flags(info_bytes)

        lines.append(f"## {name}")
        lines.append("")
        lines.append("```")
        lines.append(_format_rules(rules))
        lines.append("```")
        lines.append("")
        lines.append(f"[{info_text}]")
        lines.append("")

    output = "\n".join(lines)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output)
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
