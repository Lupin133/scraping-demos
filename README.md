# Limier — B2B Data Extraction Demos

> **Limier** is a data extraction practice operating under the **Kairos** project. Public demos showcasing the toolchain used in client missions.

## Why this repo

Most freelance "scraping" portfolios are a copy of `requests + BeautifulSoup` glue. Limier's missions rely on:

- **Scrapling** (`Fetcher` / `StealthyFetcher` Camoufox / `DynamicFetcher` Playwright) for anti-bot resilience
- **French official APIs** (Sirene INSEE, BAN, Géorisques, Recherche-entreprises) — first-party data, no licensing risk
- **RGPD-compliant defaults** — B2B / open-data only, never personal data of private individuals

These demos run end-to-end on real public data, including sample outputs committed for verification.

## Demos

### `demo1-sirene-enrichment/` — SIRET → enriched B2B record

Input a CSV of SIRETs (French company IDs), get back a CSV enriched with company name, NAF code, address, geocoded lat/long, and natural risk flags (flood, seismic).

- **Stack** : `pandas` + `requests` + `concurrent.futures` (4-thread parallel)
- **APIs used** : Recherche-entreprises, BAN (data.gouv.fr), Géorisques (BRGM)
- **Performance** : 7 SIRETs enriched in ~4 seconds
- **Sample output** : included (Mistral AI, OVH, etc. — public companies)
- **Tests** : 13 unit tests, 76% coverage

### `demo2-cnb-avocats/` — French lawyers directory snapshot

Pull the full national directory of registered French lawyers (~70k entries) from the official monthly data.gouv.fr export. TLS-fingerprinted via Scrapling `Fetcher` to bypass CDN protections. Filterable by city / specialty / bar.

- **Stack** : `scrapling` (Fetcher with curl_cffi Chrome TLS fingerprint) + `pandas`
- **Source** : CNB monthly CSV on data.gouv.fr — Licence Ouverte Etalab 2.0
- **Output** : 11 normalized columns per lawyer (name, firm, address, specialties, bar)
- **Sample output** : included (25 lawyers Paris business law + Lyon)
- **Tests** : 16 unit tests, 70% coverage

## Anti-bot tier reference

Each demo documents which Scrapling tier was needed. As a prospect, you can match your target site to the right tier:

| Tier | Scrapling fetcher | When to use | Demo example |
|---|---|---|---|
| 1 | `Fetcher` (curl_cffi, browser TLS fingerprint) | CDN with TLS fingerprinting (Cloudflare basic, AWS, static.data.gouv.fr) | Demo 2 |
| 2 | `DynamicFetcher` (hardened Playwright) | SPA with JS-rendered content, lazy loading | Available on request |
| 3 | `StealthyFetcher` (Camoufox real browser) | Cloudflare full / Distil / Imperva / Akamai bot detection | Available on request |

## Usage

Each demo is self-contained:

```bash
cd demo1-sirene-enrichment   # or demo2-cnb-avocats
pip install -r requirements.txt
python enrich.py --help       # or scrape_cnb.py --help
pytest tests/                 # run unit tests
```

## Contact

- **Upwork** : Tom Engels — `Python Scraping Expert — Anti-Bot, B2B Data & French Gov APIs`
- **GitHub** : [@Lupin133](https://github.com/Lupin133)
- **Free demo** : 10 sample rows on your target before commit — DM with the URL

## License

MIT for the demo code. The datasets retrieved from data.gouv.fr remain under their original Licence Ouverte 2.0 (Etalab) and CC BY 4.0 terms — attribution preserved in output files when applicable.
