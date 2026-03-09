#!/usr/bin/env python3
"""Regenerate golden binary fixtures. Run after a confirmed format change.

Usage: python tests/fixtures/regenerate.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "src"))

from smart_playlist_io.encode import AND, OR, encode, rule

TREE = AND(
    [
        rule("Rating", "greater", 3),
        rule("Artist", "contains", "Rock"),
        rule("Checked", "is", True),
        OR(
            [
                rule("Genre", "is", "Jazz"),
                rule("Plays", "greater", 10),
            ]
        ),
    ]
)

fixtures = pathlib.Path(__file__).parent
info, crit = encode(TREE)
(fixtures / "golden_criteria.bin").write_bytes(crit)
(fixtures / "golden_info.bin").write_bytes(info)
print(f"Written {len(info)} info bytes and {len(crit)} crit bytes to {fixtures}")
