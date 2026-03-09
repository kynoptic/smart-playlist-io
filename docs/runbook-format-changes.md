# Runbook: Responding to Apple Music Format Changes

**Diátaxis type**: How-to

The binary format encoded by this library is reverse-engineered from `Library.xml` exports and is not documented by Apple. When Apple ships a new macOS version, one or more empirically-derived constants may silently change, causing imports to fail or be ignored.

---

## Symptoms

You may be facing a format change if you observe:

- Music.app shows a `-609 Connection invalid` error on playlist import
- An imported playlist appears in the sidebar but contains no tracks and no rules
- Music.app accepts the import silently but the playlist is missing from the smart playlist list
- Previously working playlists stop matching any tracks after a macOS update

---

## Triage

Check these constants in `src/smart_playlist_io/constants.py` first, in order:

1. **`_SUBEXPR_SKIP_BASE` (currently 139)** — Most likely culprit for `-609` crash codes. This is a BE uint16 skip-length base added to each subexpression header. The theoretical value is 136; the empirically correct value is 139. If Apple changes their parser, this offset shifts.

2. **`_BOILERPLATE` (579 bytes)** — The fixed outer `SLst` frame plus a `MediaKind` filter block. If Apple changes the outer container structure, this entire block must be re-extracted from a fresh export.

3. **`_DATE_FILL`** — The fixed byte sequence used as padding in date-type rule blocks. Verify it matches the pattern in a fresh export.

4. **Rating scale upper-bound offset (+9)** — The `between` operator for `Rating` stores the upper bound as `hi * 20 + 9`. Check whether this offset has changed if range rules misbehave while other rule types work.

---

## Re-extraction procedure

Use this procedure to re-derive `_BOILERPLATE` from a fresh Music.app library export.

### Step 1 — Export Library XML

In Music.app: **File > Library > Export Library...**

Save as `Library.xml`. This file contains all playlist data in Apple's plist XML format.

### Step 2 — Locate a known simple playlist

Find a smart playlist in `Library.xml` that you know contains a single rule (e.g., Genre is "Rock"). Look for its `<dict>` entry under the `<key>Playlists</key>` section. It will contain:

```xml
<key>Smart Info</key>
<data>AAEC...</data>
<key>Smart Criteria</key>
<data>gAAAAAA...</data>
```

### Step 3 — Decode the base64 blobs

```bash
python -c "
import base64
smart_info = 'PASTE_SMART_INFO_BASE64_HERE'
smart_criteria = 'PASTE_SMART_CRITERIA_BASE64_HERE'
print('Smart Info hex:')
print(base64.b64decode(smart_info).hex())
print()
print('Smart Criteria hex:')
print(base64.b64decode(smart_criteria).hex())
"
```

### Step 4 — Identify the boilerplate prefix

The `Smart Criteria` blob begins with the fixed outer container. The current structure is:

- Bytes 0–3: magic header `SLst`
- Bytes 4–7: version/flags (currently `00000001`)
- Bytes 8–11: child count (changes with rule count)
- Bytes 12 onward: the fixed `MediaKind = Music` filter block

To isolate the fixed prefix, compare two exports with different rule counts. The bytes that stay constant across both exports form the new `_BOILERPLATE`.

### Step 5 — Compute the new constant

Paste the hex of the fixed prefix into a Python session:

```python
new_boilerplate = bytes.fromhex("YOUR_HEX_HERE")
print(len(new_boilerplate))  # Should be 579 or close to it
```

Update `_BOILERPLATE` in `constants.py` with the new value and note the new length.

---

## Validation

After updating any constant:

1. Run the test suite to confirm no regressions:

   ```bash
   make test
   ```

2. Encode a minimal test playlist:

   ```python
   from smart_playlist_io import AND, rule, encode_b64
   info_b64, criteria_b64 = encode_b64(AND([rule("Genre", "is", "Rock")]))
   print(info_b64)
   print(criteria_b64)
   ```

3. Construct a minimal `Library.xml` with the new blobs (use any existing playlist entry as a template) and import it via **File > Library > Import Playlist...** in Music.app.

4. Confirm the playlist appears in the sidebar and that its rules are displayed correctly in the smart playlist editor (**File > New Smart Playlist...** and then check the existing playlist).

---

## When to file an issue

If you have confirmed a format change and have a working fix, please open a GitHub issue:

- <https://github.com/kynoptic/smart-playlist-io/issues/new>

Include:
- The macOS version that broke imports
- The old and new constant values
- The output of `make test` with the new constant
- Whether you verified the fix with a real Music.app import
