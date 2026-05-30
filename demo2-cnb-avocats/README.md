# Demo 2 — CNB Lawyers Directory — Anti-Bot Scraping with Scrapling

![Python 3.13](https://img.shields.io/badge/Python-3.13-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![Scrapling](https://img.shields.io/badge/Scrapling-Fetcher%20%7C%20adaptive-orange)
![Data Etalab 2.0](https://img.shields.io/badge/Data-Etalab%202.0%20Open%20Licence-blue)

Extract French lawyers from the CNB (Conseil National des Barreaux) open directory.  
Filter by city, bar, specialty, or postal code. Output a clean CSV ready for prospecting.

## Why Scrapling instead of requests + BeautifulSoup

Most scrapers break the moment a CDN starts checking the TLS fingerprint of incoming requests.
`requests` sends a JA3 fingerprint that is instantly recognized as a bot — the server returns
a 403 or a Cloudflare challenge page instead of the actual data.

**Scrapling's `Fetcher`** uses `curl_cffi` under the hood, which impersonates a real Chrome
browser at the TLS handshake level. The CDN sees Chrome, not Python. No blocks, no CAPTCHA.

Additionally, Scrapling's **adaptive parsing** (`adaptive=True`) makes selectors resilient:
if the site tweaks its HTML structure, Scrapling finds the closest matching element
automatically — no script maintenance after minor site updates.

For JavaScript-rendered SPAs (where `requests` returns a blank HTML skeleton), Scrapling's
`DynamicFetcher` (Playwright) or `StealthyFetcher` (Camoufox) would be the next step up.
This demo uses `Fetcher` because the CNB publishes its full dataset on data.gouv.fr as a
downloadable CSV — the cleanest possible data access path.

## Anti-bot stack used

| Layer | Tool | Why |
|---|---|---|
| HTTP + TLS fingerprint | `Fetcher` (curl_cffi, Chrome profile) | Bypasses fingerprint-based blocks |
| Adaptive parsing | `Fetcher.configure(adaptive=True)` | Resilient selectors after DOM changes |
| Next tier (JS SPAs) | `DynamicFetcher` (Playwright) | Executes JavaScript, handles XHR |
| Next tier (Cloudflare) | `StealthyFetcher` (Camoufox) | Bypasses Cloudflare Bot Management |

## What the script does

**Input:** One or more search filters (city, bar, specialty, postal code prefix)

**Output:** CSV of matching lawyers with 11 columns:

| Column | Description |
|---|---|
| `nom` | Last name |
| `prenom` | First name |
| `cabinet` | Law firm name |
| `adresse` | Professional address |
| `code_postal` | Postal code |
| `ville` | City |
| `telephone` | Phone (empty — not in CNB open dataset) |
| `email_public` | Public email (empty — not in CNB open dataset) |
| `specialites` | Declared legal specialties (up to 3) |
| `barreau` | Bar of membership |
| `url_profil_cnb` | CNB profile URL (empty — not in open dataset) |

**Dataset:** CNB publishes the full national directory monthly on data.gouv.fr as a CSV (~9MB,
80,000+ lawyers from all 164 French bars). This script fetches the latest version automatically.

## Sample output

| nom | prenom | cabinet | code_postal | ville | specialites | barreau |
|---|---|---|---|---|---|---|
| ANDRIEU | Eric | PECHENARD & Associés | 75017 | PARIS | Droit commercial, des affaires et de la concurrence, Droit de la propriété intellectuelle | PARIS |
| FRIEDEL | Evelyne | SELAS VALSAMIDIS AMSALLEM JONATH FLAICHER et ASSOCIES | 75002 | PARIS | Droit commercial, des affaires et de la concurrence | PARIS |
| MONTERAN | Thierry | UGGC AVOCATS | 75008 | PARIS | Droit commercial, des affaires et de la concurrence, Droit des sociétés | PARIS |
| ERNEWEIN | Julie | CABINET JULIE ERNEWEIN | 75008 | PARIS | Droit commercial, des affaires et de la concurrence | PARIS |
| AADSSI | Bouchra | AADSSI MORIZE AVOCATS | 69006 | LYON | | LYON |
| DURAND | Claire | DURAND CLAIRE | 69007 | LYON | Droit immobilier | LYON |

Full sample with 25 rows available in `sample_output.csv`.

## Installation

```bash
pip install -r requirements.txt
```

Dependencies: `scrapling`, `pandas`. Python 3.13 recommended.

## Usage

```bash
# All lawyers in the Paris bar, specialty "droit des affaires" (first 100 rows)
python scrape_cnb.py --barreau PARIS --specialite "droit des affaires" --limit 100 --output paris_affaires.csv

# All lawyers in Lyon
python scrape_cnb.py --barreau LYON --output lyon.csv

# All lawyers with postal code starting with 75 (all Paris districts)
python scrape_cnb.py --code-postal 75 --output paris_all.csv

# All lawyers in France (full dataset — 80,000+ rows, takes ~10s)
python scrape_cnb.py --output all_avocats.csv
```

## How it works (5 steps)

1. **Discover** — Scrapling `Fetcher` queries the data.gouv.fr API to find the latest CSV URL
2. **Download** — Same `Fetcher` downloads the ~9MB CSV (Chrome TLS fingerprint, no blocks)
3. **Parse** — CSV is parsed with adaptive matching enabled (`Fetcher.configure(adaptive=True)`)
4. **Filter** — DataFrame filtered by the requested criteria (city, bar, specialty, postal code)
5. **Export** — Clean UTF-8 CSV saved to disk

## Data freshness

The CNB updates the dataset monthly on data.gouv.fr. The script always fetches the most recent
version automatically via the data.gouv.fr API. No manual URL updates needed.

## Legal & data attribution

Data source: **Annuaire des avocats de France** — Conseil National des Barreaux (CNB)  
Published on: [data.gouv.fr](https://www.data.gouv.fr/datasets/annuaire-des-avocats-de-france/)  
Licence: **Licence Ouverte Etalab 2.0** — commercial reuse, redistribution, and modification
authorized with source attribution.

The CNB is an établissement d'utilité publique (public utility institution) mandated by law
(article 21-1 of the law of December 31, 1971) to maintain and publish the national lawyers
directory. The data is professional information (bar membership, firm name, address, legal
specialties) — not private personal data.

This script accesses only data already published by the CNB in open data format.

---


**Tom Engels — B2B data extraction**
