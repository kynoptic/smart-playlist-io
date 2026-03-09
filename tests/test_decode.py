"""Roundtrip tests: encode -> decode -> verify match.

Component: decode
Category: unit
Purpose: Validates that decode_criteria() correctly reverses encode() output
         for all supported rule types.
"""

import base64
import plistlib
import struct
import subprocess
import sys

import pytest

from smart_playlist_io import AND, OR, decode_criteria, decode_info_flags, encode, rule
from smart_playlist_io.constants import (
    LRULE_CONT,
    LRULE_GT,
    SIGN_INT_NEG,
    SIGN_INT_POS,
    SIGN_STR_POS,
)
from smart_playlist_io.decode import _format_rules
from smart_playlist_io.encode import _BOILERPLATE, _make_int_rule, _make_subexpr_header

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def decoded_rules(rules_node, **kwargs):
    """Encode a rule tree and decode it back, returning the decoded list."""
    _, crit = encode(rules_node, **kwargs)
    return decode_criteria(crit)


def decoded_info(rules_node, **kwargs):
    """Encode a rule tree and decode the info flags string."""
    info, _ = encode(rules_node, **kwargs)
    return decode_info_flags(info)


# ---------------------------------------------------------------------------
# Basic roundtrip: single rules
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoundtripIntRules:
    def test_should_roundtrip_rating_greater(self):
        result = decoded_rules(AND([rule("Rating", "greater", 3)]))
        assert result[0] == "AND"
        assert "Rating > 3" in result[1]

    def test_should_roundtrip_rating_less(self):
        result = decoded_rules(AND([rule("Rating", "less", 3)]))
        assert "Rating < 3" in result[1]

    def test_should_roundtrip_rating_is(self):
        result = decoded_rules(AND([rule("Rating", "is", 4)]))
        assert "Rating is 4" in result[1]

    def test_should_roundtrip_rating_between(self):
        result = decoded_rules(AND([rule("Rating", "between", (3, 4))]))
        assert "Rating between 3 and 4" in result[1]

    def test_should_roundtrip_year_greater(self):
        result = decoded_rules(AND([rule("Year", "greater", 2009)]))
        assert "Year > 2009" in result[1]

    def test_should_roundtrip_plays_is(self):
        result = decoded_rules(AND([rule("Plays", "is", 5)]))
        assert "Plays is 5" in result[1]

    def test_should_roundtrip_year_between(self):
        result = decoded_rules(AND([rule("Year", "between", (2000, 2009))]))
        assert "Year between 2000 and 2009" in result[1]


@pytest.mark.unit
class TestRoundtripBoolRules:
    def test_should_roundtrip_checked_true(self):
        result = decoded_rules(AND([rule("Checked", "is", True)]))
        assert "Checked is True" in result[1]

    def test_should_roundtrip_checked_false(self):
        result = decoded_rules(AND([rule("Checked", "is", False)]))
        assert "Checked is False" in result[1]


@pytest.mark.unit
class TestRoundtripStringRules:
    def test_should_roundtrip_genre_contains(self):
        result = decoded_rules(AND([rule("Genre", "contains", "Jazz")]))
        assert 'Genre contains "Jazz"' in result[1]

    def test_should_roundtrip_genre_starts(self):
        result = decoded_rules(AND([rule("Genre", "starts", "Electronic")]))
        assert 'Genre starts with "Electronic"' in result[1]

    def test_should_roundtrip_genre_is(self):
        result = decoded_rules(AND([rule("Genre", "is", "Alternative")]))
        assert 'Genre is "Alternative"' in result[1]

    def test_should_roundtrip_genre_ends(self):
        result = decoded_rules(AND([rule("Genre", "ends", "Pop")]))
        assert 'Genre ends with "Pop"' in result[1]

    def test_should_roundtrip_not_contains(self):
        result = decoded_rules(AND([rule("Genre", "not_contains", "Comedy")]))
        assert 'Genre does not contain "Comedy"' in result[1]


@pytest.mark.unit
class TestRoundtripDateRules:
    def test_should_roundtrip_not_in_last(self):
        result = decoded_rules(AND([rule("LastPlayed", "not_in_last", 3, "months")]))
        assert "LastPlayed not in last 3 months" in result[1]

    def test_should_roundtrip_in_last(self):
        result = decoded_rules(AND([rule("LastPlayed", "in_last", 7, "days")]))
        assert "LastPlayed in last 7 days" in result[1]

    def test_should_roundtrip_after(self):
        result = decoded_rules(AND([rule("DateAdded", "after", 700000000)]))
        assert "DateAdded > 700000000" in result[1]


@pytest.mark.unit
class TestRoundtripEnumRules:
    def test_should_roundtrip_love_is_loved(self):
        result = decoded_rules(AND([rule("Love", "is", "Loved")]))
        assert 'Love is "Loved"' in result[1]

    def test_should_roundtrip_icloud_is_not(self):
        result = decoded_rules(AND([rule("iCloudStatus", "is_not", "No Longer Available")]))
        assert 'iCloudStatus is not "No Longer Available"' in result[1]


# ---------------------------------------------------------------------------
# Roundtrip: groups and nesting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoundtripGroups:
    def test_should_roundtrip_and_group(self):
        result = decoded_rules(
            AND(
                [
                    rule("Rating", "greater", 3),
                    rule("Year", "greater", 2009),
                ]
            )
        )
        assert result[0] == "AND"
        assert len(result) == 3  # AND + 2 rules

    def test_should_roundtrip_or_group(self):
        result = decoded_rules(
            OR(
                [
                    rule("Genre", "contains", "Jazz"),
                    rule("Genre", "contains", "Blues"),
                ]
            )
        )
        assert result[0] == "OR"
        assert len(result) == 3

    def test_should_roundtrip_nested_or_in_and(self):
        result = decoded_rules(
            AND(
                [
                    rule("Checked", "is", True),
                    OR(
                        [
                            rule("Genre", "contains", "Jazz"),
                            rule("Genre", "contains", "Blues"),
                        ]
                    ),
                ]
            )
        )
        assert result[0] == "AND"
        assert len(result) == 3
        # Second child should be an OR sublist
        or_group = result[2]
        assert isinstance(or_group, list)
        assert or_group[0] == "OR"
        assert len(or_group) == 3


# ---------------------------------------------------------------------------
# Smart Info flags roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoundtripInfoFlags:
    def test_should_roundtrip_live_updating(self):
        result = decoded_info(AND([rule("Rating", "greater", 3)]), live=True)
        assert "live updating" in result

    def test_should_roundtrip_limit(self):
        result = decoded_info(
            AND([rule("Rating", "greater", 3)]), limit=25, select_by="most_played"
        )
        assert "limit 25 items" in result
        assert "most played" in result

    def test_should_roundtrip_only_checked(self):
        result = decoded_info(AND([rule("Rating", "greater", 3)]), only_checked=True)
        assert "only checked" in result

    def test_should_roundtrip_no_flags(self):
        result = decoded_info(AND([rule("Rating", "greater", 3)]), live=False)
        assert result == "no flags"

    def test_should_roundtrip_least_selection(self):
        result = decoded_info(
            AND([rule("Rating", "greater", 3)]), limit=50, select_by="least_recently_played"
        )
        assert "least recently played" in result

    def test_should_raise_for_short_info_bytes(self):
        with pytest.raises(ValueError, match="too short"):
            decode_info_flags(b"\x00" * 5)


# ---------------------------------------------------------------------------
# Absolute date ops roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoundtripAbsoluteDateOps:
    def test_should_roundtrip_date_before(self):
        result = decoded_rules(AND([rule("DateAdded", "before", 700000000)]))
        assert "DateAdded < 700000000" in result[1]


# ---------------------------------------------------------------------------
# decode_criteria format handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecodeCriteriaFormats:
    def test_should_return_raw_for_unrecognized_format(self):
        result = decode_criteria(b"\x00" * 100)
        assert result[0] == "RAW"
        assert "unrecognized" in result[1]

    def test_should_decode_nonstandard_slst_at_offset_0(self):
        # Non-standard format: SLst header at byte 0 instead of 579-byte boilerplate.
        # Some simpler playlists from older Music.app versions use this layout.
        header = bytearray(139)
        header[0:4] = b"SLst"
        struct.pack_into(">I", header, 8, 1)  # child_count = 1
        header[15] = 0x00  # AND logic
        int_rule = _make_int_rule(0x19, SIGN_INT_POS, LRULE_GT, 60)  # Rating > 3
        result = decode_criteria(bytes(header) + int_rule)
        assert result[0] == "AND"
        assert "Rating > 3" in result[1]

    def test_should_decode_nonstandard_or_logic(self):
        header = bytearray(139)
        header[0:4] = b"SLst"
        struct.pack_into(">I", header, 8, 1)  # child_count = 1
        header[15] = 0x01  # OR logic
        int_rule = _make_int_rule(0x19, SIGN_INT_POS, LRULE_GT, 60)
        result = decode_criteria(bytes(header) + int_rule)
        assert result[0] == "OR"


# ---------------------------------------------------------------------------
# Decoder edge cases: malformed / truncated data
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecodeEdgeCases:
    def test_should_handle_truncated_children(self):
        # Subexpr header claims 3 children but blob only contains 1 rule.
        # Decoder should emit one rule then a truncation sentinel, not crash.
        int_rule = _make_int_rule(0x19, SIGN_INT_POS, LRULE_GT, 60)
        inner_header = _make_subexpr_header("AND", 3, len(int_rule))
        data = _BOILERPLATE + inner_header + int_rule
        result = decode_criteria(data)
        assert result[0] == "AND"
        assert any("<truncated" in str(r) for r in result[1:])

    def test_should_decode_negated_absolute_date(self):
        # Manually construct a negated absolute-date rule (e.g. "not after <ts>").
        # The encoder does not produce this op, but real library exports may contain it.
        buf = bytearray(124)
        buf[0] = 0x10  # DateAdded field_id
        buf[1] = SIGN_INT_NEG  # negated
        buf[3] = 0x00  # not relative-time, not range
        buf[4] = LRULE_GT  # greater-than comparison
        buf[52] = 0x44  # required constant
        buf[53:57] = b"\x2d\xae\x2d\xae"
        buf[57:61] = b"\x2d\xae\x2d\xae"
        struct.pack_into(">I", buf, 57, 700000000)
        buf[61:65] = b"\x00\x00\x00\x00"  # sentinel != 0xFFFFFFFF → absolute path
        buf[77:81] = b"\x2d\xae\x2d\xae"
        buf[81:85] = b"\x2d\xae\x2d\xae"
        buf[100] = 0x01  # required constant
        date_rule = bytes(buf)
        inner_header = _make_subexpr_header("AND", 1, len(date_rule))
        data = _BOILERPLATE + inner_header + date_rule
        result = decode_criteria(data)
        assert result[0] == "AND"
        assert "DateAdded not > 700000000" in result[1]

    def test_should_handle_string_rule_with_odd_byte_length(self):
        # Construct a string rule whose str_len byte is odd (5).  The decoder pads
        # the raw bytes to an even length before decoding as UTF-16-LE.
        string_header = bytearray(54)
        string_header[0] = 0x08  # Genre field_id
        string_header[1] = SIGN_STR_POS
        string_header[4] = LRULE_CONT
        string_header[52] = 5  # str_len = 5 (odd)
        # "Jaz" UTF-16-LE = 6 bytes; we supply only 5 to make len(str_bytes) odd
        string_data = b"\x4a\x00\x61\x00\x7a"
        inner_header = _make_subexpr_header("AND", 1, 54 + len(string_data))
        data = _BOILERPLATE + inner_header + bytes(string_header) + string_data
        result = decode_criteria(data)
        assert result[0] == "AND"
        assert "Genre" in result[1]  # decoded despite odd byte count


# ---------------------------------------------------------------------------
# _format_rules helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatRules:
    def test_should_format_empty_rules_list(self):
        assert "<empty>" in _format_rules([])

    def test_should_format_raw_fallback(self):
        result = _format_rules(["RAW", "<unrecognized format: 10 bytes>"])
        assert "RAW" in result
        assert "unrecognized" in result

    def test_should_format_and_group(self):
        result = _format_rules(["AND", "Rating > 3", "Year > 2009"])
        assert "AND:" in result
        assert "Rating > 3" in result
        assert "Year > 2009" in result

    def test_should_indent_nested_groups(self):
        nested = ["OR", 'Genre contains "Jazz"', 'Genre contains "Blues"']
        result = _format_rules(["AND", "Checked is True", nested], indent=0)
        assert "AND:" in result
        assert "OR:" in result
        assert 'Genre contains "Jazz"' in result

    def test_should_apply_indent_prefix(self):
        result = _format_rules(["AND", "Rating > 3"], indent=2)
        assert result.startswith("    AND:")  # 4 spaces = indent 2


# ---------------------------------------------------------------------------
# CLI: main() entry point
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecodeCLI:
    def _make_library_xml(self, path, playlists: list) -> None:
        lib = {"Playlists": playlists}
        with open(path, "wb") as f:
            plistlib.dump(lib, f, fmt=plistlib.FMT_XML)

    def test_should_decode_library_xml_to_stdout(self, tmp_path, monkeypatch, capsys):
        from smart_playlist_io.decode import main

        info, crit = encode(AND([rule("Rating", "greater", 3)]), live=True)
        xml_path = tmp_path / "Library.xml"
        self._make_library_xml(
            xml_path,
            [
                {"Name": "Top Rated", "Smart Info": info, "Smart Criteria": crit},
            ],
        )
        monkeypatch.setattr("sys.argv", ["decode-smart-playlists", str(xml_path)])
        main()
        out = capsys.readouterr().out
        assert "Top Rated" in out
        assert "Rating" in out

    def test_should_write_output_to_file(self, tmp_path, monkeypatch):
        from smart_playlist_io.decode import main

        info, crit = encode(AND([rule("Rating", "greater", 3)]))
        xml_path = tmp_path / "Library.xml"
        self._make_library_xml(
            xml_path,
            [
                {"Name": "Saved", "Smart Info": info, "Smart Criteria": crit},
            ],
        )
        out_path = tmp_path / "output.md"
        monkeypatch.setattr(
            "sys.argv",
            [
                "decode-smart-playlists",
                str(xml_path),
                "--out",
                str(out_path),
            ],
        )
        main()
        assert out_path.exists()
        assert "Saved" in out_path.read_text()

    def test_should_exit_when_file_not_found(self, tmp_path, monkeypatch):
        from smart_playlist_io.decode import main

        monkeypatch.setattr(
            "sys.argv",
            [
                "decode-smart-playlists",
                str(tmp_path / "nonexistent.xml"),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_should_skip_playlists_without_smart_fields(self, tmp_path, monkeypatch, capsys):
        from smart_playlist_io.decode import main

        xml_path = tmp_path / "Library.xml"
        # One non-smart playlist, should produce 0 smart playlists in output
        self._make_library_xml(xml_path, [{"Name": "Manual Playlist"}])
        monkeypatch.setattr("sys.argv", ["decode-smart-playlists", str(xml_path)])
        main()
        out = capsys.readouterr().out
        assert "Playlists: 0" in out


# ---------------------------------------------------------------------------
# Coverage: previously uncovered branches
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecodeCoverage:
    """Tests targeting the 5 uncovered lines in decode.py."""

    # ------------------------------------------------------------------
    # Lines 140-141: UTF-16 decode exception path in _decode_string_rule
    # ------------------------------------------------------------------

    def test_should_fall_back_to_byte_count_when_utf16_decode_raises(self):
        """Force the except branch by injecting bytes whose .decode() raises."""
        from smart_playlist_io.decode import _decode_string_rule

        # BadData intercepts slice operations so that the returned bytes object's
        # .decode() method raises UnicodeDecodeError, triggering the except branch.
        class _FailDecode(bytes):
            def decode(self, *args, **kwargs):
                raise UnicodeDecodeError("utf-16-le", bytes(self), 0, 1, "injected")

        class _BadData(bytes):
            def __getitem__(self, key):
                result = super().__getitem__(key)
                if isinstance(key, slice) and isinstance(result, bytes):
                    return _FailDecode(result)
                return result

        string_header = bytearray(54)
        string_header[0] = 0x08  # Genre field_id (in STRING_FIELD_IDS)
        string_header[1] = SIGN_STR_POS
        string_header[4] = LRULE_CONT
        string_header[52] = 4  # str_len = 4
        string_data = b"\x4a\x00\x61\x00"  # valid bytes, but decode is mocked to fail

        raw = bytes(string_header) + string_data
        data = _BadData(raw)

        result, next_offset = _decode_string_rule(data, 0)
        # Fallback value must be "<N bytes>" where N == str_len
        assert "<4 bytes>" in result
        assert "Genre" in result

    # ------------------------------------------------------------------
    # Lines 285-288: base64 string branch in _load_smart_playlists (CLI path)
    # ------------------------------------------------------------------

    def test_should_decode_library_xml_with_base64_string_values(
        self, tmp_path, monkeypatch, capsys
    ):
        """Smart Info / Smart Criteria stored as <string> (base64) instead of <data>.

        Some plist formats return strings instead of bytes objects.  The CLI path
        (lines 285-288) must base64-decode them before passing to decode_criteria().
        """
        from smart_playlist_io.decode import main

        info_bytes, crit_bytes = encode(AND([rule("Rating", "greater", 3)]), live=True)

        # Build plist XML with <string> tags containing base64-encoded payloads.
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
            ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            "<dict>\n"
            "  <key>Playlists</key>\n"
            "  <array>\n"
            "    <dict>\n"
            "      <key>Name</key>\n"
            "      <string>StringBase64PL</string>\n"
            "      <key>Smart Info</key>\n"
            f"      <string>{base64.b64encode(info_bytes).decode()}</string>\n"
            "      <key>Smart Criteria</key>\n"
            f"      <string>{base64.b64encode(crit_bytes).decode()}</string>\n"
            "    </dict>\n"
            "  </array>\n"
            "</dict>\n"
            "</plist>\n"
        )
        xml_path = tmp_path / "Library.xml"
        xml_path.write_bytes(xml.encode())

        monkeypatch.setattr("sys.argv", ["decode-smart-playlists", str(xml_path)])
        main()
        out = capsys.readouterr().out
        assert "StringBase64PL" in out
        assert "Rating" in out

    # ------------------------------------------------------------------
    # Lines 324-325: __main__ guard
    # ------------------------------------------------------------------

    def test_should_run_as_module_with_help_flag(self):
        """Invoke decode as __main__ via subprocess to hit the if __name__ guard."""
        result = subprocess.run(
            [sys.executable, "-m", "smart_playlist_io.decode", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Library XML" in result.stdout or "library" in result.stdout.lower()


# ---------------------------------------------------------------------------
# SELECT_METHOD decode roundtrip: sign-based disambiguation for colliding pairs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSelectMethodRoundtrip:
    """Guard sign-based disambiguation for SELECT_METHOD byte collisions.

    most_played / least_played share byte 0x19 — direction disambiguated by SELECT_SIGN.
    most_recently_played / least_recently_played share byte 0x1A.
    most_recently_added / least_recently_added share byte 0x15.
    """

    def test_should_distinguish_most_vs_least_played(self):
        most = decoded_info(AND([rule("Rating", "is", 4)]), select_by="most_played", limit=25)
        least = decoded_info(AND([rule("Rating", "is", 4)]), select_by="least_played", limit=25)
        assert "most" in most.lower() or "played" in most.lower()
        assert "least" in least.lower()
        assert most != least

    def test_should_distinguish_most_vs_least_recently_played(self):
        most = decoded_info(
            AND([rule("Rating", "is", 4)]), select_by="most_recently_played", limit=25
        )
        least = decoded_info(
            AND([rule("Rating", "is", 4)]), select_by="least_recently_played", limit=25
        )
        assert most != least

    def test_should_distinguish_most_vs_least_recently_added(self):
        most = decoded_info(
            AND([rule("Rating", "is", 4)]), select_by="most_recently_added", limit=25
        )
        least = decoded_info(
            AND([rule("Rating", "is", 4)]), select_by="least_recently_added", limit=25
        )
        assert most != least

    def test_should_distinguish_highest_vs_lowest_rated(self):
        high = decoded_info(AND([rule("Rating", "is", 4)]), select_by="highest_rated", limit=25)
        low = decoded_info(AND([rule("Rating", "is", 4)]), select_by="lowest_rated", limit=25)
        assert high != low
