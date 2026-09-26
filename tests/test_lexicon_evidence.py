"""Chain-of-custody tests for the hand-typed Santali lexicon.

content/seed.py holds Santali strings a team member typed by hand, and
Ol Chiki has lookalikes in neighbouring scripts that render almost
identically (we have caught two of those in this very repo). The
countermeasure is the evidence record: every lexicon entry names, under
verified_against, the public sources whose machine-extracted token sets
(content/vocabulary/evidence.json, produced by
scripts/collect_lexicon_evidence.py) must contain that entry's sat text,
byte for byte. If a hand-typed glyph drifted, the failure below names the
exact code points that did not match, which makes the fix mechanical.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "content" / "vocabulary" / "evidence.json"
OL_LO, OL_HI = 0x1C50, 0x1C7F


def _load_seed_entries():
    spec = importlib.util.spec_from_file_location(
        "matvani_seed", ROOT / "content" / "seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LEXICON["entries"]


ENTRIES = _load_seed_entries()


@pytest.fixture(scope="module")
def evidence():
    if not EVIDENCE.exists():
        pytest.skip(
            "content/vocabulary/evidence.json is missing - regenerate it "
            "with: python3 scripts/collect_lexicon_evidence.py "
            "(one-time, online; --offline once cached)")
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def _cps(text):
    return " ".join("U+{:04X}".format(ord(ch)) for ch in text)


# --- entry self-descriptions (no evidence file needed) ------------------

def test_entries_declare_evidence_and_modern_spelling():
    for entry in ENTRIES:
        keys = entry.get("verified_against")
        assert isinstance(keys, list) and keys, (
            f"{entry['id']}: verified_against must be a non-empty list")
        # The period-for-GAHARA convention is source-page archaeology, not
        # classroom spelling; the lexicon ships modern forms only.
        assert "." not in entry["sat"], (
            f"{entry['id']}: period-orthography sat {entry['sat']!r} "
            f"[{_cps(entry['sat'])}] - use the GAHARA form")


def test_sat_entries_are_single_runs():
    # Evidence tokens are single Ol Chiki runs. A multi-word entry would
    # need its own verification story before it can claim any source.
    for entry in ENTRIES:
        assert " " not in entry["sat"], f"{entry['id']}: {entry['sat']!r}"


def test_no_duplicate_entries():
    hi = [e["hi"] for e in ENTRIES]
    sat = [e["sat"] for e in ENTRIES]
    assert len(hi) == len(set(hi)), "duplicate Hindi side - lookup collision"
    assert len(sat) == len(set(sat)), "duplicate Santali side"


# --- against the evidence record ------------------------------------------

def test_evidence_tokens_are_pure_olchiki(evidence):
    for key, src in evidence["sources"].items():
        for token in src["tokens"]:
            assert all(OL_LO <= ord(ch) <= OL_HI for ch in token), (
                f"{key}: {token!r} [{_cps(token)}] outside U+1C50..U+1C7F")


def test_verified_against_keys_resolve(evidence):
    for entry in ENTRIES:
        for key in entry["verified_against"]:
            assert key in evidence["sources"], (
                f"{entry['id']}: evidence has no source {key!r} "
                f"(collector and seed.py out of sync?)")


def test_sat_text_found_in_every_claimed_source(evidence):
    missing = []
    for entry in ENTRIES:
        for key in entry["verified_against"]:
            tokens = evidence["sources"][key]["tokens"]
            if entry["sat"] not in tokens:
                missing.append(
                    f"{entry['id']}: sat {entry['sat']!r} "
                    f"[{_cps(entry['sat'])}] not in {key}")
    assert not missing, (
        "hand-typed Santali drifted from the fetched evidence:\n  "
        + "\n  ".join(missing))
