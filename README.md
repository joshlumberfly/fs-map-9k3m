# Australian Food Safety Map

A personal Progressive Web App that maps food businesses on Australian government food-safety conviction registers. Tap a marker to see the conviction details.

Not a commercial product. Deployed to a private (non-indexed) GitHub Pages URL and installed on iPhone via Safari → Share → Add to Home Screen.

## Status

- [x] Scraper for Victorian register (single Elasticsearch call — no Playwright needed)
- [x] Geocoding via Nominatim with local cache
- [ ] Frontend (Leaflet map + PWA shell)
- [ ] GitHub Pages deployment

## Layout

```
.
├── scraper/
│   ├── scrape.py         # Fetch records → geocode → write docs/convictions.json
│   ├── requirements.txt  # `requests` only
│   └── .cache/           # Geocode cache (gitignored)
└── docs/
    ├── convictions.json  # Generated; committed so the static site can fetch it
    └── ...               # (frontend lives here once built)
```

## Running the scraper

```bash
cd scraper
python -m venv .venv
. .venv/Scripts/activate     # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scrape.py
```

Output is written to `docs/convictions.json`. Re-running uses the cached geocode results, so subsequent runs only hit Nominatim for new addresses. The Victorian register rolls over a 12-month window, so a weekly cron is a sensible cadence.

### Address overrides

Some entries in the register contain typos in the suburb or street name that
cause Nominatim lookups to fail. The scraper will retry once with the leading
shop-unit prefix stripped (e.g. `12-14/21A Douglas Street` → `21A Douglas
Street`), but it will not silently correct typos.

To work around a typo, add an entry to `scraper/address_overrides.json`:

```json
{
  "7 Barlyn Road, Mount Waverly, Vic 3149": "7 Barlyn Road, Mount Waverley, Vic 3149"
}
```

The key is the address as it appears in the register; the value is the
corrected query sent to Nominatim. The original (typo'd) address is still what
the app displays — only the geocode lookup is corrected. This keeps every
correction explicit, reviewable, and free of fuzzy-matching guesswork.

When you add an override for a previously-failed address, the scraper will
retry it on the next run automatically — you don't need to clear the cache.

## Data source

Victorian Government Food Safety Register of Convictions:
<https://www.health.vic.gov.au/food-safety/food-safety-register-of-convictions>

Public register mandated under s. 53D of the Food Act 1984. Convictions remain on the register for 12 months. Data is published under CC BY 4.0; attribution and a link back to the official register are included in every map popup.

The register page is a Nuxt/Vue SPA backed by a public Elasticsearch endpoint at
`https://2a432d2d6146895f9ad3ce4b94b3ddac.sdp4.elastic.sdp.vic.gov.au/elasticsearch_index_drupal_node/_search`.
The scraper queries it directly for documents of type `conviction_record`.

If the scraper starts returning no records or HTTP 404s in the future, the
hashed subdomain may have rotated. Re-fetch the public register page and
re-extract the value of `elasticsearch:{host:"..."}` from the inline Nuxt
payload.

## Legal posture

Truth is an absolute defence to defamation in Australia. To stay aligned with
that defence, the app displays only what is verbatim on the register, with
attribution and a link to the source entry. No fuzzy-matching of business names
across other data sources.
