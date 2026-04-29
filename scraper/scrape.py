"""Fetch Victorian food-safety conviction records and emit web/convictions.json.

Source: the public Elasticsearch endpoint that backs
https://www.health.vic.gov.au/food-safety/food-safety-register-of-convictions

Run: python scrape.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

import requests

ES_HOST = "https://2a432d2d6146895f9ad3ce4b94b3ddac.sdp4.elastic.sdp.vic.gov.au"
ES_INDEX = "elasticsearch_index_drupal_node"
ES_URL = f"{ES_HOST}/{ES_INDEX}/_search"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "FoodSafetyMap/0.1 (personal project; contact: github.com/joshhh)"
NOMINATIM_DELAY_S = 1.1  # Nominatim TOS: 1 req/sec max

PUBLIC_HOST = "https://www.health.vic.gov.au"
REGISTER_URL = f"{PUBLIC_HOST}/food-safety/food-safety-register-of-convictions"

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / ".cache" / "geocode.json"
OVERRIDES_PATH = ROOT / "address_overrides.json"
OUTPUT_PATH = ROOT.parent / "web" / "convictions.json"


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def html_to_text(html: str) -> str:
    if not html:
        return ""
    parser = _HTMLStripper()
    parser.feed(html)
    text = parser.text()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def first(seq, default=""):
    """Drupal ES fields are arrays; take the first element or default."""
    if isinstance(seq, list) and seq:
        return seq[0]
    if isinstance(seq, str):
        return seq
    return default


def fetch_records() -> list[dict]:
    body = {
        "size": 200,
        "query": {"term": {"type": "conviction_record"}},
    }
    r = requests.post(
        ES_URL,
        json=body,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    return [hit["_source"] for hit in payload["hits"]["hits"]]


def load_cache() -> dict[str, dict]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def geocode_query(query: str) -> dict | None:
    """One Nominatim hit. Returns {'lat': float, 'lng': float} or None."""
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": "au"}
    r = requests.get(
        NOMINATIM_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    results = r.json()
    if not results:
        return None
    return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}


def strip_shop_prefix(address: str) -> str | None:
    """`12-14/21A Douglas Street, ...` -> `21A Douglas Street, ...`.

    Australian shop addresses use `<unit>/<street-number>` before the street.
    Returns the simplified form, or None if no slash is present in the
    portion before the first comma.
    """
    head, sep, tail = address.partition(",")
    if "/" not in head:
        return None
    _, _, after_slash = head.partition("/")
    return after_slash.strip() + (sep + tail if sep else "")


def geocode(address: str) -> dict | None:
    """Geocode with one fallback: strip a leading shop-unit prefix on retry."""
    coords = geocode_query(address)
    if coords:
        return coords
    simplified = strip_shop_prefix(address)
    if simplified and simplified != address:
        time.sleep(NOMINATIM_DELAY_S)
        return geocode_query(simplified)
    return None


def load_overrides() -> dict[str, str]:
    """Manual corrections for register typos.

    Map: original-address-string-as-it-appears-in-register -> corrected-query.
    The corrected query is sent to Nominatim; the original address is still
    what the app displays. Bypasses fuzzy-matching concerns by making every
    correction an explicit, reviewable human decision.
    """
    if not OVERRIDES_PATH.exists():
        return {}
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def build_record(src: dict, coords: dict) -> dict:
    return {
        "name": first(src.get("field_trading_name")) or first(src.get("title")),
        "convicted": first(src.get("field_name_of_convicted")),
        "address": first(src.get("field_address")),
        "lat": coords["lat"],
        "lng": coords["lng"],
        "date": first(src.get("field_date_of_conviction")),
        "court": first(src.get("field_node_court")),
        "decision": first(src.get("field_node_court_decision")),
        "sentence": first(src.get("field_sentence_imposed")),
        "prosecutor": first(src.get("field_prosecution_brought_by")),
        "conviction_number": first(src.get("field_conviction_number")),
        "offence": html_to_text(first(src.get("body"))),
        "source_url": PUBLIC_HOST + first(src.get("url")),
        "register_url": REGISTER_URL,
    }


def main() -> int:
    print(f"Fetching records from {ES_URL} ...", flush=True)
    sources = fetch_records()
    print(f"  found {len(sources)} conviction records", flush=True)

    cache = load_cache()
    overrides = load_overrides()
    cache_hits = 0
    cache_misses = 0
    skipped: list[str] = []
    output: list[dict] = []

    for src in sources:
        address = first(src.get("field_address"))
        if not address:
            skipped.append(f"(no address) {first(src.get('title'))}")
            continue

        # The cache key is always the original register address so corrections
        # via overrides remain visible and reviewable in the cache file.
        # A cached null miss is retried only when an override has since been
        # added — otherwise we'd hammer Nominatim every run for known-typo
        # addresses with no chance of success.
        cached = cache.get(address, "MISSING")
        retry_with_override = cached is None and address in overrides
        if cached != "MISSING" and not retry_with_override:
            coords = cached
            cache_hits += 1
        else:
            query = overrides.get(address, address)
            label = address if query == address else f"{address}  ->  {query}"
            print(f"  geocoding: {label}", flush=True)
            try:
                coords = geocode(query)
            except requests.RequestException as e:
                print(f"    ERROR: {e}", file=sys.stderr)
                coords = None
            time.sleep(NOMINATIM_DELAY_S)
            cache_misses += 1
            cache[address] = coords  # may be None — caches the miss
            save_cache(cache)

        if coords is None:
            skipped.append(f"(no geocode) {address}")
            continue

        output.append(build_record(src, coords))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nWrote {len(output)} records to {OUTPUT_PATH}")
    print(f"  geocode cache: {cache_hits} hits, {cache_misses} misses")
    if skipped:
        print(f"  skipped {len(skipped)}:")
        for s in skipped:
            print(f"    - {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
