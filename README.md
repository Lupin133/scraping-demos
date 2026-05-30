# Python Scraping & B2B Data Extraction — Demos

Public demos of the toolchain I use on client scraping and data-extraction work. Each one runs end-to-end on real public data, with sample outputs committed so you can verify them yourself.

## Approach

Most freelance "scraping" portfolios are a thin wrapper over `requests + BeautifulSoup`. These demos lean on:

- **Scrapling** (`Fetcher` / `StealthyFetcher` Camoufox / `DynamicFetcher` Playwright) for anti-bot resilience
- **French official APIs** (Sirene INSEE, BAN, Géorisques, Recherche-entreprises) — first-party data, no licensing risk
- **RGPD-compliant defaults** — B2B and open data only, never personal data of private individuals

## Demos

### `demo1-sirene-enrichment/` — SIRET to enriched B2B record

Input a CSV of SIRETs (French company IDs), get back a CSV enriched with company name, NAF code, address, geocoded lat/long, and natural risk flags (flood, seismic).

- **Stack**: `pandas` + `requests` + `concurrent.futures` (4-thread parallel)
- **APIs**: Recherche-entreprises, BAN (data.gouv.fr), Géorisques (BRGM)
- **Performance**: 7 SIRETs enriched in ~4 seconds
- **Sample output**: included (Mistral AI, OVH, and other public companies)
- **Tests**: 13 unit tests, 76% coverage

### `demo2-cnb-avocats/` — French lawyers directory snapshot

Pull the full national directory of registered French lawyers (~70k entries) from the official monthly data.gouv.fr export. TLS-fingerprinted via Scrapling `Fetcher` to get past CDN protections. Filterable by city / specialty / bar.

- **Stack**: `scrapling` (Fetcher with curl_cffi Chrome TLS fingerprint) + `pandas`
- **Source**: CNB monthly CSV on data.gouv.fr — Licence Ouverte Etalab 2.0
- **Output**: 11 normalized columns per lawyer (name, firm, address, specialties, bar)
- **Sample output**: included (25 lawyers, Paris business law + Lyon)
- **Tests**: 16 unit tests, 70% coverage

## Anti-bot tier reference

Each demo notes which Scrapling tier it needed. Match your target site to the right tier:

| Tier | Scrapling fetcher | When to use | Demo |
|---|---|---|---|
| 1 | `Fetcher` (curl_cffi, browser TLS fingerprint) | CDN with TLS fingerprinting (Cloudflare basic, AWS, static.data.gouv.fr) | Demo 2 |
| 2 | `DynamicFetcher` (hardened Playwright) | SPA with JS-rendered content, lazy loading | On request |
| 3 | `StealthyFetcher` (Camoufox real browser) | Cloudflare full / Distil / Imperva / Akamai bot detection | On request |

## Usage

Each demo is self-contained:

```bash
cd demo1-sirene-enrichment   # or demo2-cnb-avocats
pip install -r requirements.txt
python enrich.py --help       # or scrape_cnb.py --help
pytest tests/
```

## Contact

Tom Engels — Python scraping & B2B data extraction. Available on Upwork.
