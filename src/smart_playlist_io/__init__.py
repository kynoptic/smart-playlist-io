"""Apple Music Smart Playlist binary format encoder and decoder.

Encode and decode Smart Info + Smart Criteria blobs used in Apple Music
Library XML exports. Format reverse-engineered from itunessmart by cvzi,
based on banshee-itunes-import-plugin by Scott Peterson.

Encoder usage:
    from smart_playlist_io import AND, OR, rule, encode, encode_b64

    rules = AND([
        rule("Rating", "greater", 3),
        rule("Genre", "contains", "Jazz"),
    ])
    info_bytes, criteria_bytes = encode(rules, limit=25, select_by="most_played")

Decoder usage:
    from smart_playlist_io import decode_criteria, decode_info_flags

    rules = decode_criteria(criteria_bytes)
    flags = decode_info_flags(info_bytes)
"""

from .decode import decode_criteria, decode_info_flags
from .encode import AND, OR, RuleNode, encode, encode_b64, rule

__all__ = [
    "AND",
    "OR",
    "rule",
    "encode",
    "encode_b64",
    "RuleNode",
    "decode_criteria",
    "decode_info_flags",
]
