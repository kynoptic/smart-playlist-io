"""Roundtrip tests: encode -> decode -> verify match.

Component: decode
Category: unit
Purpose: Validates that decode_criteria() correctly reverses encode() output
         for all supported rule types.
"""

import pytest

from smart_playlist_io import AND, OR, rule, encode, decode_criteria, decode_info_flags


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
        result = decoded_rules(AND([
            rule("Rating", "greater", 3),
            rule("Year", "greater", 2009),
        ]))
        assert result[0] == "AND"
        assert len(result) == 3  # AND + 2 rules

    def test_should_roundtrip_or_group(self):
        result = decoded_rules(OR([
            rule("Genre", "contains", "Jazz"),
            rule("Genre", "contains", "Blues"),
        ]))
        assert result[0] == "OR"
        assert len(result) == 3

    def test_should_roundtrip_nested_or_in_and(self):
        result = decoded_rules(AND([
            rule("Checked", "is", True),
            OR([
                rule("Genre", "contains", "Jazz"),
                rule("Genre", "contains", "Blues"),
            ]),
        ]))
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
        result = decoded_info(AND([rule("Rating", "greater", 3)]),
                              limit=25, select_by="most_played")
        assert "limit 25 items" in result
        assert "most played" in result

    def test_should_roundtrip_only_checked(self):
        result = decoded_info(AND([rule("Rating", "greater", 3)]), only_checked=True)
        assert "only checked" in result

    def test_should_roundtrip_no_flags(self):
        result = decoded_info(AND([rule("Rating", "greater", 3)]), live=False)
        assert result == "no flags"

    def test_should_roundtrip_least_selection(self):
        result = decoded_info(AND([rule("Rating", "greater", 3)]),
                              limit=50, select_by="least_recently_played")
        assert "least recently_played" in result
