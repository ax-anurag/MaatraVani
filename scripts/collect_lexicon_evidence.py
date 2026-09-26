#!/usr/bin/env python3
"""Build the lexicon evidence record (content/vocabulary/evidence.json).

Why this exists: the Santali strings in content/seed.py are typed by hand,
and hand-typing Ol Chiki is precisely how a lookalike character from a
neighbouring script sneaks into a project. So a lexicon word is only
allowed to ship if its exact bytes were seen in a fetched public source.
This script is the fetching half:

  * download each source once (cached under .cache/lexicon-evidence/),
  * pull out every run of Ol Chiki characters from the raw text,
  * record the token sets in content/vocabulary/evidence.json.

tests/test_lexicon_evidence.py is the enforcement half: a seed.py entry
fails the suite unless its sat text appears in the token set of every
source the entry names under verified_against.

Requests are throttled to one every 2 s - a handful in total, far below
the project-wide 25 req/min cap. After the first run, --offline rebuilds
the evidence file from the cache with the network unplugged.

Usage:
  python3 scripts/collect_lexicon_evidence.py             # fetch + write
  python3 scripts/collect_lexicon_evidence.py --offline   # cache only
  python3 scripts/collect_lexicon_evidence.py --refresh   # ignore cache
"""

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "lexicon-evidence"
OUT = ROOT / "content" / "vocabulary" / "evidence.json"

# cache files this run actually used - everything else matching the
# sat.wiktionary prefixes is an orphan from an earlier candidate list
USED = set()

# Ol Chiki block, U+1C50..U+1C7F. Tokens are single runs of these.
OLCHIKI = re.compile("[\U00001C50-\U00001C7F]+")
GAHARA = "\U00001C79"

# sat.wikipedia article titles we treat as canonical modern Santali, via
# the Wikidata sitelinks. The English labels were checked when this list
# was put together: dog, cat, cattle, goat, horse, bird, water, school,
# food, and the digit articles for 1, 2, 3, 4, 5 and 0. Wrong QID guesses
# (a prime number, a Norwegian hockey player...) simply had no satwiki
# article and were dropped - that is why the labels get fetched too.
QIDS = ["Q144", "Q146", "Q830", "Q2934", "Q726", "Q5113",
        "Q283", "Q3914", "Q2095",
        "Q199", "Q200", "Q201", "Q202", "Q203", "Q204"]

PAGES = {
    "omniglot_numbers": "https://www.omniglot.com/language/numbers/santali.htm",
    "countbylanguage": "https://countbylanguage.github.io/austroasiatic/santali.html",
    "wikibooks_animals": "https://en.wikibooks.org/wiki/Santali/Animals",
}
PAGE_NOTES = {
    "omniglot_numbers": (
        "Omniglot, 'Numbers in Santali'. The page stores the GAHARA vowel "
        "sign as a numeric character reference, so the text is entity-"
        "decoded before extraction."
    ),
    "countbylanguage": (
        "countbylanguage, Santali numbers table. Agreed byte-for-byte with "
        "Omniglot on all ten numbers when both were checked."
    ),
    "wikibooks_animals": (
        "Wikibooks, 'Santali/Animals' vocabulary table. Some entries use "
        "the older period-for-GAHARA orthography; the bytes are kept as "
        "the page writes them."
    ),
}

HEADERS = {"User-Agent": "MaatraVaniPoC/0.2 lexicon evidence collector (hackathon project)"}
THROTTLE_SECONDS = 2.0
BATCH = 20  # wikitext fetches per API call; keeps responses small


def _curl(url):
    out = subprocess.run(["curl", "-fsSL", "--max-time", "30", url],
                         capture_output=True, check=True)
    return out.stdout


def _urllib(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch(url, name, refresh=False, offline=False):
    """Fetch url into the cache, or serve it from there. Returns bytes.

    curl is the preferred fetcher: some of the vocabulary sites sit behind
    a WAF that 403s Python's urllib with any custom User-Agent outright
    (Omniglot does exactly that) while plain curl passes. urllib stays as
    the fallback so the script needs nothing beyond a normal Linux box."""
    path = CACHE / name
    if not refresh and path.exists():
        USED.add(name)
        return path.read_bytes()
    if offline:
        raise RuntimeError(f"cache miss in --offline mode: {name} ({url})")
    time.sleep(THROTTLE_SECONDS)
    data = _curl(url) if shutil.which("curl") else _urllib(url)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    USED.add(name)
    return data


def cache_date(pattern):
    """Fetch date of the newest cached file matching the pattern (mtime,
    not 'now' - the honest moment the bytes arrived)."""
    files = sorted(CACHE.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        return "unknown"
    return date.fromtimestamp(files[-1].stat().st_mtime).isoformat()


def tokens_from(text):
    """Every Ol Chiki run in text, unique and codepoint-sorted."""
    return sorted(set(OLCHIKI.findall(html.unescape(text))))


def satw_api(params):
    return "https://sat.wiktionary.org/w/api.php?" + urllib.parse.urlencode(params)


def collect_sitelinks(refresh=False, offline=False):
    """sat.wikipedia article titles for the QID list, plus their labels."""
    url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&ids="
           + "|".join(QIDS)
           + "&props=labels%7Csitelinks&languages=en&sitefilter=satwiki&format=json")
    raw = fetch(url, "wikidata_sitelinks.json", refresh, offline)
    titles, checked = [], []
    for qid, ent in sorted(json.loads(raw)["entities"].items()):
        label = ent.get("labels", {}).get("en", {}).get("value", qid)
        link = ent.get("sitelinks", {}).get("satwiki")
        if link:
            titles.append(link["title"])
            checked.append(f"{label}: {link['title']}")
    return tokens_from(" ".join(titles)), checked


def _batch_name(prefix, titles):
    """Cache files are named by the *content* of the batch: if the
    candidate list changes, the filename changes with it, so a stale
    cached response can never be served for a different query."""
    digest = hashlib.sha1("|".join(titles).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}.json"


def probe_candidates(texts, token_sets):
    """Titles worth probing on sat.wiktionary.

    Two kinds of candidate:
      * every pure Ol Chiki run seen so far;
      * period-joined words. The older orthography writes GAHARA as a
        plain '.' inside a word (e.g. kula.y for rabbit), so the full
        word never appears as a pure run - probing runs alone misses
        exactly those pages. Both the period spelling and the modern
        GAHARA spelling go in, since either can be the page title."""
    cands = set()
    for tokens in token_sets.values():
        cands.update(tokens)
    # ([.] not \. : this is a normal string so the \U escapes work, and a
    # bare \. is an invalid escape there)
    joined = re.compile("[\U00001C50-\U00001C7F]+(?:[.][\U00001C50-\U00001C7F]+)+")
    for text in texts.values():
        for chunk in joined.findall(html.unescape(text)):
            cands.add(chunk)                       # as the source writes it
            cands.add(chunk.replace(".", GAHARA))  # modern spelling
    return cands


def collect_satwiktionary(candidates, refresh=False, offline=False):
    """Probe candidate titles, then pull the wikitext of every live page.
    The probe goes in batches of 50 - the MediaWiki API's per-request cap
    on the titles parameter (overflow makes it return an error document,
    which is how we found out). Redirects are followed server-side, so an
    older spelling still lands on the live entry. Tokens come from both
    titles and bodies."""
    live = set()
    cands = sorted(candidates)
    for i in range(0, len(cands), 50):
        batch = cands[i:i + 50]
        raw = fetch(satw_api({"action": "query", "format": "json",
                              "formatversion": "2", "redirects": "1",
                              "titles": "|".join(batch)}),
                    _batch_name("satw_probe", batch), refresh, offline)
        pages = json.loads(raw)["query"]["pages"]
        live.update(p["title"] for p in pages if "missing" not in p)
    live = sorted(live)

    chunks = []
    for i in range(0, len(live), BATCH):
        batch = live[i:i + BATCH]
        raw = fetch(satw_api({"action": "query", "format": "json",
                              "formatversion": "2", "redirects": "1",
                              "prop": "revisions", "rvprop": "content",
                              "rvslots": "main",
                              "titles": "|".join(batch)}),
                    _batch_name("satw_content", batch), refresh, offline)
        for p in json.loads(raw)["query"]["pages"]:
            revs = p.get("revisions") or []
            if revs:
                chunks.append(revs[0]["slots"]["main"]["content"])
    return tokens_from(" ".join(live) + " " + " ".join(chunks)), live


def main():
    ap = argparse.ArgumentParser(description="Collect Ol Chiki lexicon evidence")
    ap.add_argument("--offline", action="store_true",
                    help="rebuild from the cache only; no network")
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch sources even if cached")
    args = ap.parse_args()

    sources = {}
    texts = {}

    print("==> number and animal pages")
    for key, url in PAGES.items():
        raw = fetch(url, key + ".html", args.refresh, args.offline)
        texts[key] = raw.decode("utf-8", "replace")
        sources[key] = {
            "url": url,
            "retrieved": cache_date(key + ".html"),
            "note": PAGE_NOTES[key],
            "tokens": tokens_from(texts[key]),
        }
        print(f"    {key}: {len(sources[key]['tokens'])} tokens")

    print("==> sat.wikipedia titles via Wikidata")
    sitelink_tokens, checked = collect_sitelinks(args.refresh, args.offline)
    sources["satwiki_sitelinks"] = {
        "url": ("https://www.wikidata.org/w/api.php "
                "(wbgetentities: labels + satwiki sitelinks)"),
        "retrieved": cache_date("wikidata_sitelinks.json"),
        "note": ("sat.wikipedia article titles, treated as canonical modern "
                 "spelling. Articles verified: " + "; ".join(checked)),
        "tokens": sitelink_tokens,
    }
    print(f"    satwiki_sitelinks: {len(sitelink_tokens)} tokens")

    print("==> sat.wiktionary probe + entries")
    cands = probe_candidates(texts, {k: v["tokens"] for k, v in sources.items()})
    satw_tokens, live = collect_satwiktionary(cands, args.refresh, args.offline)
    sources["satwiktionary"] = {
        "url": ("https://sat.wiktionary.org/w/api.php "
                "(existence probe, then wikitext of every page found)"),
        "retrieved": cache_date("satw_probe_*.json"),
        "note": (f"{len(cands)} candidate titles probed, {len(live)} exist; "
                 "tokens come from the live titles and the wikitext bodies. "
                 "Some titles use the older period-for-GAHARA spelling; "
                 "bodies usually carry the modern form."),
        "tokens": satw_tokens,
    }
    print(f"    satwiktionary: {len(satw_tokens)} tokens from {len(live)} pages")

    record = {
        "meta": {
            "name": "MaatraVani lexicon evidence record",
            "note": (
                "Machine-extracted token lists. No Santali text in this "
                "file was typed by a person: every token is a run of Ol "
                "Chiki characters (U+1C50..U+1C7F) pulled out of the raw "
                "page or API bytes named in each source. "
                "scripts/collect_lexicon_evidence.py regenerates this file; "
                "tests/test_lexicon_evidence.py requires each content/"
                "seed.py entry's sat text to appear in every source the "
                "entry lists under verified_against."
            ),
            "extracted": date.today().isoformat(),
            "extracted_by": "scripts/collect_lexicon_evidence.py",
            "token_pattern": "one or more characters in U+1C50..U+1C7F, after html.unescape",
            "request_throttle_seconds": THROTTLE_SECONDS,
        },
        "sources": sources,
    }
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    # sat.wiktionary cache files whose names did not come up this run are
    # responses to an older candidate list - drop them so .cache stays
    # legible (the content-addressed names make them unreachable anyway).
    for stale in CACHE.glob("satw_*.json"):
        if stale.name not in USED:
            stale.unlink()

    total = sum(len(s["tokens"]) for s in sources.values())
    print(f"==> wrote {OUT.relative_to(ROOT)} "
          f"({len(sources)} sources, {total} tokens)")
    print("    next: .venv/bin/python -m pytest tests/test_lexicon_evidence.py -v")


if __name__ == "__main__":
    main()
