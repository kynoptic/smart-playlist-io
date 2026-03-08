"""Unit tests for the smart playlist encoder.

Component: encode
Category: unit
Purpose: Validates that encode() produces correctly structured binary blobs
         for all supported rule types. Tests assert byte-level layout confirmed
         against real Apple Music library exports.
"""

import struct
import pytest

from smart_playlist_io.encode import (
    AND, OR, rule, encode, encode_b64,
    _BOILERPLATE, _SUBEXPR_BLOCK_SIZE, _SUBEXPR_SKIP_BASE,
    _make_int_rule, _make_subexpr_header, _encode_time_value,
)
from smart_playlist_io.constants import (
    SIGN_INT_POS, SIGN_INT_NEG, SIGN_STR_POS, SIGN_STR_NEG,
    LRULE_IS, LRULE_CONT, LRULE_START, LRULE_END, LRULE_GT, LRULE_LT, LRULE_OTHER,
    ENUM_FIELDS, LOVE_STATUS, ICLOUD_STATUS,
)

BOILERPLATE_LEN = 579
INNER_SUBEXPR_LEN = 192
INT_RULE_LEN = 124


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def criteria_for(rules_node, **kwargs):
    """Return raw criteria bytes for the given rule tree."""
    _, crit = encode(rules_node, **kwargs)
    return crit


def inner_subexpr(crit):
    """Return the 192-byte inner subexpression header."""
    return crit[BOILERPLATE_LEN:BOILERPLATE_LEN + INNER_SUBEXPR_LEN]


def rules_blob(crit):
    """Return everything after boilerplate + inner subexpr header."""
    return crit[BOILERPLATE_LEN + INNER_SUBEXPR_LEN:]


# ---------------------------------------------------------------------------
# _make_int_rule
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMakeIntRule:
    def test_should_place_field_id_at_byte_0(self):
        buf = _make_int_rule(0x19, SIGN_INT_POS, LRULE_GT, 60)
        assert buf[0] == 0x19

    def test_should_place_sign_at_byte_1(self):
        pos = _make_int_rule(0x19, SIGN_INT_POS, LRULE_GT, 60)
        neg = _make_int_rule(0x19, SIGN_INT_NEG, LRULE_GT, 60)
        assert pos[1] == SIGN_INT_POS
        assert neg[1] == SIGN_INT_NEG

    def test_should_place_extra_flag_at_byte_3(self):
        plain = _make_int_rule(0x19, SIGN_INT_POS, LRULE_OTHER, 60, extra_flag=0)
        ranged = _make_int_rule(0x19, SIGN_INT_POS, LRULE_OTHER, 60, extra_flag=0x01)
        assert plain[3] == 0x00
        assert ranged[3] == 0x01

    def test_should_place_logic_rule_at_byte_4(self):
        buf = _make_int_rule(0x19, SIGN_INT_POS, LRULE_GT, 60)
        assert buf[4] == LRULE_GT

    def test_should_place_required_constants(self):
        buf = _make_int_rule(0x19, SIGN_INT_POS, LRULE_IS, 40)
        assert buf[52] == 0x44
        assert buf[76] == 0x01
        assert buf[100] == 0x01

    def test_should_encode_val_a_as_be_uint32_at_offset_57(self):
        buf = _make_int_rule(0x19, SIGN_INT_POS, LRULE_GT, 0xABCD)
        assert struct.unpack_from(">I", buf, 57)[0] == 0xABCD

    def test_should_mirror_val_a_to_val_b_when_no_range(self):
        buf = _make_int_rule(0x19, SIGN_INT_POS, LRULE_IS, 60)
        assert struct.unpack_from(">I", buf, 57)[0] == 60
        assert struct.unpack_from(">I", buf, 81)[0] == 60

    def test_should_use_explicit_val_b_for_range(self):
        buf = _make_int_rule(0x19, SIGN_INT_POS, LRULE_OTHER, 60, val_b=89, extra_flag=0x01)
        assert struct.unpack_from(">I", buf, 57)[0] == 60
        assert struct.unpack_from(">I", buf, 81)[0] == 89

    def test_should_be_exactly_124_bytes(self):
        assert len(_make_int_rule(0x19, SIGN_INT_POS, LRULE_IS, 0)) == INT_RULE_LEN


# ---------------------------------------------------------------------------
# _make_subexpr_header
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMakeSubexprHeader:
    def test_should_be_exactly_192_bytes(self):
        assert len(_make_subexpr_header("AND", 1)) == _SUBEXPR_BLOCK_SIZE

    def test_should_set_prefix_flags_at_bytes_4_5(self):
        buf = _make_subexpr_header("AND", 2)
        assert buf[4] == 0x01
        assert buf[5] == 0x01

    def test_should_embed_slst_magic_at_offset_53(self):
        buf = _make_subexpr_header("AND", 1)
        assert buf[53:57] == b"SLst"

    def test_should_embed_version_at_offset_57(self):
        buf = _make_subexpr_header("AND", 1)
        assert struct.unpack_from(">I", buf, 57)[0] == 0x00010001

    def test_should_encode_child_count_at_offset_61(self):
        for n in (1, 2, 5):
            buf = _make_subexpr_header("AND", n)
            assert struct.unpack_from(">I", buf, 61)[0] == n

    def test_should_set_logic_byte_for_and(self):
        buf = _make_subexpr_header("AND", 1)
        assert buf[68] == 0x00

    def test_should_set_logic_byte_for_or(self):
        buf = _make_subexpr_header("OR", 2)
        assert buf[68] == 0x01

    def test_should_encode_skip_length_as_base_plus_children_size(self):
        children_size = 248
        buf = _make_subexpr_header("AND", 2, children_size)
        skip = struct.unpack_from(">H", buf, 51)[0]
        assert skip == _SUBEXPR_SKIP_BASE + children_size


# ---------------------------------------------------------------------------
# _encode_time_value
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEncodeTimeValue:
    def test_should_be_bitwise_complement_of_n_minus_1(self):
        for n in (1, 3, 7, 30):
            result = _encode_time_value(n)
            expected = bytes(255 - b for b in struct.pack(">I", (n - 1) % 2**32))
            assert result == expected, f"failed for n={n}"

    def test_should_return_4_bytes(self):
        assert len(_encode_time_value(1)) == 4


# ---------------------------------------------------------------------------
# Criteria structure
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCriteriaStructure:
    def test_should_start_with_boilerplate(self):
        crit = criteria_for(AND([rule("Rating", "greater", 3)]))
        assert crit[:BOILERPLATE_LEN] == _BOILERPLATE

    def test_should_have_and_logic_in_inner_subexpr(self):
        crit = criteria_for(AND([rule("Rating", "greater", 3)]))
        hdr = inner_subexpr(crit)
        assert hdr[68] == 0x00  # AND

    def test_should_have_correct_length_for_single_int_rule(self):
        crit = criteria_for(AND([rule("Rating", "greater", 3)]))
        assert len(crit) == BOILERPLATE_LEN + INNER_SUBEXPR_LEN + INT_RULE_LEN

    def test_should_have_correct_length_for_two_int_rules(self):
        crit = criteria_for(AND([
            rule("Rating", "greater", 3),
            rule("Year", "greater", 2009),
        ]))
        assert len(crit) == BOILERPLATE_LEN + INNER_SUBEXPR_LEN + 2 * INT_RULE_LEN

    def test_should_wrap_bare_rule_in_and(self):
        # A single rule (not wrapped in AND/OR) should still produce AND logic
        crit = criteria_for(rule("Rating", "greater", 3))
        hdr = inner_subexpr(crit)
        assert hdr[68] == 0x00  # AND

    def test_should_preserve_top_level_or(self):
        # Top-level OR emits OR directly as the inner subexpression
        crit = criteria_for(OR([
            rule("Genre", "contains", "Jazz"),
            rule("Genre", "contains", "Blues"),
        ]))
        hdr = inner_subexpr(crit)
        assert hdr[68] == 0x01  # inner subexpr is OR


# ---------------------------------------------------------------------------
# Rating encoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRatingEncoding:
    def test_should_scale_rating_by_20(self):
        crit = criteria_for(AND([rule("Rating", "greater", 3)]))
        blob = rules_blob(crit)
        val_a = struct.unpack_from(">I", blob, 57)[0]
        assert val_a == 60  # 3 * 20

    def test_should_apply_plus_9_to_between_upper_bound(self):
        # "between 3 and 4" -> val_a=60, val_b=89 (4*20 + 9)
        crit = criteria_for(AND([rule("Rating", "between", (3, 4))]))
        blob = rules_blob(crit)
        val_a = struct.unpack_from(">I", blob, 57)[0]
        val_b = struct.unpack_from(">I", blob, 81)[0]
        assert val_a == 60
        assert val_b == 89

    def test_should_apply_plus_9_to_five_star_between(self):
        # "between 5 and 5" -> val_b=109 (confirmed from real exports)
        crit = criteria_for(AND([rule("Rating", "between", (5, 5))]))
        blob = rules_blob(crit)
        val_b = struct.unpack_from(">I", blob, 81)[0]
        assert val_b == 109

    def test_should_set_extra_flag_for_between(self):
        crit = criteria_for(AND([rule("Rating", "between", (3, 4))]))
        blob = rules_blob(crit)
        assert blob[3] == 0x01  # extra_flag = range

    def test_should_use_lrule_lt_for_less(self):
        crit = criteria_for(AND([rule("Rating", "less", 3)]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_LT

    def test_should_use_lrule_gt_for_greater(self):
        crit = criteria_for(AND([rule("Rating", "greater", 3)]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_GT


# ---------------------------------------------------------------------------
# Bool encoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBoolEncoding:
    def test_should_use_sign_int_neg_for_true(self):
        crit = criteria_for(AND([rule("Checked", "is", True)]))
        blob = rules_blob(crit)
        assert blob[1] == SIGN_INT_NEG

    def test_should_use_sign_int_pos_for_false(self):
        crit = criteria_for(AND([rule("Checked", "is", False)]))
        blob = rules_blob(crit)
        assert blob[1] == SIGN_INT_POS


# ---------------------------------------------------------------------------
# String encoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStringEncoding:
    def test_should_set_utf16_byte_length_at_offset_52(self):
        crit = criteria_for(AND([rule("Genre", "contains", "Jazz")]))
        blob = rules_blob(crit)
        # "Jazz" = 4 chars -> 8 bytes UTF-16
        assert blob[52] == 8

    def test_should_include_null_terminator_for_non_last_string(self):
        # Two string rules: first should have null terminator
        crit = criteria_for(AND([
            rule("Genre", "contains", "Jazz"),
            rule("Genre", "contains", "Blues"),
        ]))
        blob = rules_blob(crit)
        # First rule header is 54 bytes, "Jazz" is 8 bytes UTF-16, then 2 null bytes
        jazz_end = 54 + 8
        assert blob[jazz_end:jazz_end + 2] == b"\x00\x00"

    def test_should_omit_null_terminator_for_last_string(self):
        # Single string rule: last in blob, no null terminator
        crit = criteria_for(AND([rule("Genre", "contains", "Jazz")]))
        blob = rules_blob(crit)
        # Header=54, "Jazz"=8 bytes, no null -> total 62 bytes
        assert len(blob) == 54 + 8
        assert not blob.endswith(b"\x00\x00")

    def test_should_use_sign_str_neg_for_not_contains(self):
        crit = criteria_for(AND([rule("Genre", "not_contains", "Jazz")]))
        blob = rules_blob(crit)
        assert blob[1] == SIGN_STR_NEG

    def test_should_use_lrule_start_for_starts(self):
        crit = criteria_for(AND([rule("Genre", "starts", "Trip Hop")]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_START


# ---------------------------------------------------------------------------
# Date encoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDateEncoding:
    def _date_blob(self, op, value, unit="months"):
        crit = criteria_for(AND([rule("LastPlayed", op, value, unit)]))
        return rules_blob(crit)

    def test_should_set_0x44_at_offset_52(self):
        blob = self._date_blob("not_in_last", 3)
        assert blob[52] == 0x44

    def test_should_set_date_fill_pattern_at_offsets_53_60(self):
        blob = self._date_blob("not_in_last", 3)
        fill = b"\x2d\xae\x2d\xae"
        assert blob[53:57] == fill
        assert blob[57:61] == fill

    def test_should_set_0x01_at_offset_100(self):
        blob = self._date_blob("not_in_last", 3)
        assert blob[100] == 0x01

    def test_should_set_ffffffff_sentinel_for_relative_rule(self):
        blob = self._date_blob("not_in_last", 3)
        assert blob[61:65] == b"\xff\xff\xff\xff"

    def test_should_encode_time_value_at_offset_65(self):
        blob = self._date_blob("not_in_last", 3)
        assert blob[65:69] == _encode_time_value(3)

    def test_should_encode_time_unit_seconds_at_offset_73(self):
        blob = self._date_blob("not_in_last", 3, "months")
        unit = struct.unpack_from(">I", blob, 73)[0]
        assert unit == 2628000  # months in seconds

    def test_should_use_sign_int_neg_for_not_in_last(self):
        blob = self._date_blob("not_in_last", 3)
        assert blob[1] == SIGN_INT_NEG

    def test_should_use_sign_int_pos_for_in_last(self):
        blob = self._date_blob("in_last", 3)
        assert blob[1] == SIGN_INT_POS


# ---------------------------------------------------------------------------
# Smart Info encoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSmartInfoEncoding:
    def test_should_set_live_update_byte(self):
        info, _ = encode(AND([rule("Rating", "greater", 3)]), live=True)
        assert info[0] == 0x01
        info, _ = encode(AND([rule("Rating", "greater", 3)]), live=False)
        assert info[0] == 0x00

    def test_should_set_limit_bytes_when_limit_given(self):
        info, _ = encode(AND([rule("Rating", "greater", 3)]), limit=25)
        assert info[2] == 0x01  # limitBool
        assert struct.unpack_from(">I", info, 8)[0] == 25

    def test_should_leave_limit_bytes_zero_when_no_limit(self):
        info, _ = encode(AND([rule("Rating", "greater", 3)]))
        assert info[2] == 0x00
        assert struct.unpack_from(">I", info, 8)[0] == 0

    def test_should_set_selection_sign_for_least_recently_played(self):
        info, _ = encode(AND([rule("Rating", "greater", 3)]),
                         limit=25, select_by="least_recently_played")
        assert info[13] == 1  # sign = 1 -> least

    def test_should_leave_selection_sign_zero_for_most_recently_played(self):
        info, _ = encode(AND([rule("Rating", "greater", 3)]),
                         limit=25, select_by="most_recently_played")
        assert info[13] == 0

    def test_should_be_112_bytes(self):
        info, _ = encode(AND([rule("Rating", "greater", 3)]))
        assert len(info) == 112

    def test_should_set_only_checked_byte(self):
        info, _ = encode(AND([rule("Rating", "greater", 3)]), only_checked=True)
        assert info[12] == 0x01


# ---------------------------------------------------------------------------
# encode_b64
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEncodeB64:
    def test_should_return_valid_base64_strings(self):
        import base64
        si, sc = encode_b64(AND([rule("Rating", "greater", 3)]))
        # Should not raise
        base64.b64decode(si)
        base64.b64decode(sc)

    def test_should_round_trip_to_same_bytes_as_encode(self):
        import base64
        rules_node = AND([rule("Rating", "greater", 3)])
        si, sc = encode_b64(rules_node)
        info, crit = encode(rules_node)
        assert base64.b64decode(si) == info
        assert base64.b64decode(sc) == crit


# ---------------------------------------------------------------------------
# Skip-length padding regression tests (ADR-001)
#
# Music.app crashes with -609 if skip-length uses base 136 instead of 139.
# Every real library export shows skip_length = 139 + children_bytes.
# These tests guard the empirically-derived +3 padding.
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSkipLengthPadding:
    def test_skip_base_should_be_139_not_136(self):
        # ADR-001: theoretical base is 136 (= 192 - 56) but Music.app
        # requires 139. This was the root cause of all import crashes.
        assert _SUBEXPR_SKIP_BASE == 139

    def test_should_encode_skip_length_with_139_base(self):
        children_size = 500
        buf = _make_subexpr_header("AND", 3, children_size)
        skip = struct.unpack_from(">H", buf, 51)[0]
        assert skip == 139 + children_size

    def test_inner_subexpr_skip_should_use_139_base_for_single_int_rule(self):
        crit = criteria_for(AND([rule("Rating", "greater", 3)]))
        hdr = inner_subexpr(crit)
        skip = struct.unpack_from(">H", hdr, 51)[0]
        assert skip == 139 + INT_RULE_LEN

    def test_inner_subexpr_skip_should_use_139_base_for_string_rules(self):
        crit = criteria_for(AND([
            rule("Genre", "contains", "Jazz"),
            rule("Genre", "contains", "Blues"),
        ]))
        hdr = inner_subexpr(crit)
        skip = struct.unpack_from(">H", hdr, 51)[0]
        children_bytes = len(crit) - BOILERPLATE_LEN - INNER_SUBEXPR_LEN
        assert skip == 139 + children_bytes


# ---------------------------------------------------------------------------
# Top-level OR regression tests
#
# Top-level OR was previously wrapped in AND([OR([...])]), adding an
# extra nesting layer. Music.app encodes "match any" as OR directly
# in the inner subexpression - no wrapper needed.
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTopLevelOR:
    def test_should_emit_or_logic_directly(self):
        crit = criteria_for(OR([
            rule("Genre", "contains", "Jazz"),
            rule("Genre", "contains", "Blues"),
        ]))
        hdr = inner_subexpr(crit)
        assert hdr[68] == 0x01  # OR, not AND

    def test_should_have_correct_child_count(self):
        crit = criteria_for(OR([
            rule("Genre", "contains", "Idm"),
            rule("Genre", "contains", "Trip Hop"),
            rule("Genre", "contains", "Downtempo"),
        ]))
        hdr = inner_subexpr(crit)
        count = struct.unpack_from(">I", hdr, 61)[0]
        assert count == 3  # 3 children, not 1 (wrapped OR)

    def test_should_not_add_extra_nesting_layer(self):
        # Regression: old code wrapped OR in AND, producing boilerplate + AND header
        # + OR header + rules. Correct: boilerplate + OR header + rules.
        crit = criteria_for(OR([
            rule("Genre", "contains", "Jazz"),
            rule("Genre", "contains", "Blues"),
        ]))
        # Rules should start immediately after inner subexpr header, no nested header
        blob = rules_blob(crit)
        # First byte of first rule should be Genre field_id (0x08), not subexpr prefix
        assert blob[0] == 0x08

    def test_skip_length_should_cover_all_children_directly(self):
        crit = criteria_for(OR([
            rule("Genre", "contains", "Jazz"),
            rule("Genre", "contains", "Blues"),
        ]))
        hdr = inner_subexpr(crit)
        skip = struct.unpack_from(">H", hdr, 51)[0]
        children_bytes = len(crit) - BOILERPLATE_LEN - INNER_SUBEXPR_LEN
        assert skip == 139 + children_bytes


# ---------------------------------------------------------------------------
# Nested OR inside AND
#
# The most common real-world pattern. Validates that nested subexpressions
# have correct skip-lengths and child counts at all levels.
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNestedGroups:
    def test_nested_or_should_create_subexpr_with_or_logic(self):
        crit = criteria_for(AND([
            rule("Checked", "is", True),
            OR([
                rule("Genre", "contains", "Jazz"),
                rule("Genre", "contains", "Blues"),
            ]),
        ]))
        hdr = inner_subexpr(crit)
        # Inner subexpr is AND with 2 children: bool rule + OR group
        assert hdr[68] == 0x00  # AND
        count = struct.unpack_from(">I", hdr, 61)[0]
        assert count == 2

    def test_nested_or_subexpr_should_have_correct_child_count(self):
        crit = criteria_for(AND([
            rule("Checked", "is", True),
            OR([
                rule("Genre", "contains", "Jazz"),
                rule("Genre", "contains", "Blues"),
                rule("Genre", "contains", "Funk"),
            ]),
        ]))
        blob = rules_blob(crit)
        # First child: bool rule (124 bytes). Second child: OR subexpr header.
        or_header = blob[INT_RULE_LEN:INT_RULE_LEN + INNER_SUBEXPR_LEN]
        assert or_header[68] == 0x01  # OR
        or_count = struct.unpack_from(">I", or_header, 61)[0]
        assert or_count == 3

    def test_nested_or_skip_length_should_use_139_base(self):
        crit = criteria_for(AND([
            rule("Checked", "is", True),
            OR([
                rule("Genre", "contains", "Jazz"),
                rule("Genre", "contains", "Blues"),
            ]),
        ]))
        blob = rules_blob(crit)
        or_header = blob[INT_RULE_LEN:INT_RULE_LEN + INNER_SUBEXPR_LEN]
        or_skip = struct.unpack_from(">H", or_header, 51)[0]
        # Children of the OR: everything after its header to end of blob
        or_children_bytes = len(blob) - INT_RULE_LEN - INNER_SUBEXPR_LEN
        assert or_skip == 139 + or_children_bytes


# ---------------------------------------------------------------------------
# Enum encoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEnumEncoding:
    def test_should_encode_love_loved_with_correct_value(self):
        crit = criteria_for(AND([rule("Love", "is", "Loved")]))
        blob = rules_blob(crit)
        assert blob[0] == ENUM_FIELDS["Love"]  # field_id = 0x9a
        assert blob[1] == SIGN_INT_POS
        val_a = struct.unpack_from(">I", blob, 57)[0]
        assert val_a == LOVE_STATUS["Loved"]  # 0x02

    def test_should_encode_love_is_not_with_neg_sign(self):
        crit = criteria_for(AND([rule("Love", "is_not", "Loved")]))
        blob = rules_blob(crit)
        assert blob[1] == SIGN_INT_NEG

    def test_should_encode_icloud_status_no_longer_available(self):
        crit = criteria_for(AND([rule("iCloudStatus", "is_not", "No Longer Available")]))
        blob = rules_blob(crit)
        assert blob[0] == ENUM_FIELDS["iCloudStatus"]  # 0x86
        assert blob[1] == SIGN_INT_NEG
        val_a = struct.unpack_from(">I", blob, 57)[0]
        assert val_a == ICLOUD_STATUS["No Longer Available"]  # 0x09

    def test_should_mirror_val_a_to_val_b_for_enum(self):
        crit = criteria_for(AND([rule("Love", "is", "Disliked")]))
        blob = rules_blob(crit)
        val_a = struct.unpack_from(">I", blob, 57)[0]
        val_b = struct.unpack_from(">I", blob, 81)[0]
        assert val_a == val_b == LOVE_STATUS["Disliked"]


# ---------------------------------------------------------------------------
# Non-Rating integer fields (must NOT scale by 20)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNonRatingIntFields:
    def test_year_should_not_scale(self):
        crit = criteria_for(AND([rule("Year", "greater", 2009)]))
        blob = rules_blob(crit)
        val_a = struct.unpack_from(">I", blob, 57)[0]
        assert val_a == 2009  # not 2009 * 20

    def test_plays_should_not_scale(self):
        crit = criteria_for(AND([rule("Plays", "is", 5)]))
        blob = rules_blob(crit)
        val_a = struct.unpack_from(">I", blob, 57)[0]
        assert val_a == 5

    def test_year_between_should_not_apply_plus_9(self):
        # +9 adjustment is Rating-only
        crit = criteria_for(AND([rule("Year", "between", (2000, 2009))]))
        blob = rules_blob(crit)
        val_a = struct.unpack_from(">I", blob, 57)[0]
        val_b = struct.unpack_from(">I", blob, 81)[0]
        assert val_a == 2000
        assert val_b == 2009  # not 2009 + 9

    def test_int_is_not_should_use_neg_sign(self):
        crit = criteria_for(AND([rule("Year", "is_not", 2020)]))
        blob = rules_blob(crit)
        assert blob[1] == SIGN_INT_NEG


# ---------------------------------------------------------------------------
# Additional string operator coverage
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStringOperators:
    def test_should_use_lrule_is_for_string_is(self):
        crit = criteria_for(AND([rule("Genre", "is", "Alternative")]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_IS
        assert blob[1] == SIGN_STR_POS

    def test_should_use_lrule_is_with_neg_sign_for_is_not(self):
        crit = criteria_for(AND([rule("Genre", "is_not", "Comedy")]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_IS
        assert blob[1] == SIGN_STR_NEG

    def test_should_use_lrule_end_for_ends(self):
        crit = criteria_for(AND([rule("Genre", "ends", "Pop")]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_END

    def test_should_encode_utf16_string_data_correctly(self):
        crit = criteria_for(AND([rule("Genre", "contains", "R&B")]))
        blob = rules_blob(crit)
        # "R&B" = 3 chars -> 6 bytes UTF-16
        assert blob[52] == 6
        # UTF-16 LE data starts at offset 54: R(52 00) &(26 00) B(42 00)
        assert blob[54:56] == b"\x52\x00"  # R
        assert blob[56:58] == b"\x26\x00"  # &
        assert blob[58:60] == b"\x42\x00"  # B


# ---------------------------------------------------------------------------
# Date absolute timestamp ops
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDateAbsoluteOps:
    def test_should_use_lrule_gt_for_after(self):
        crit = criteria_for(AND([rule("DateAdded", "after", 700000000)]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_GT
        assert blob[1] == SIGN_INT_POS

    def test_should_use_lrule_lt_for_before(self):
        crit = criteria_for(AND([rule("DateAdded", "before", 700000000)]))
        blob = rules_blob(crit)
        assert blob[4] == LRULE_LT

    def test_should_encode_timestamp_at_offset_57(self):
        ts = 700000000
        crit = criteria_for(AND([rule("DateAdded", "after", ts)]))
        blob = rules_blob(crit)
        val = struct.unpack_from(">I", blob, 57)[0]
        assert val == ts

    def test_should_still_have_date_fill_patterns(self):
        crit = criteria_for(AND([rule("DateAdded", "after", 700000000)]))
        blob = rules_blob(crit)
        fill = b"\x2d\xae\x2d\xae"
        # Date fill at 53-56 is overwritten by the fill, then 57-60 by timestamp
        assert blob[53:57] == fill
        assert blob[77:81] == fill
        assert blob[81:85] == fill


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestErrorHandling:
    def test_should_reject_unknown_field(self):
        with pytest.raises(ValueError, match="Unknown field"):
            encode(AND([rule("FakeField", "is", 1)]))

    def test_should_reject_unknown_int_op(self):
        with pytest.raises(ValueError, match="Unknown int op"):
            encode(AND([rule("Rating", "like", 3)]))

    def test_should_reject_unknown_date_op(self):
        with pytest.raises(ValueError, match="Unknown date op"):
            encode(AND([rule("LastPlayed", "during", 3, "months")]))
