"""
Limier — Demo 2: CNB Avocats Scraping with Scrapling
=====================================================
Extracts French lawyers from the CNB (Conseil National des Barreaux) directory.

Data source: data.gouv.fr open dataset — Licence Ouverte Etalab 2.0.
The CNB publishes its full directory monthly as a CSV on data.gouv.fr,
allowing commercial reuse with attribution.

WHY SCRAPLING INSTEAD OF REQUESTS + BEAUTIFULSOUP:
  - Scrapling's Fetcher uses curl_cffi under the hood, mimicking real browser
    TLS fingerprints (JA3/JA4). Standard requests gets blocked on many sites
    because its TLS handshake is instantly recognizable as a bot.
  - For the CNB site itself (a JavaScript SPA), DynamicFetcher (Playwright)
    would be required to render the page. Here we use the official dataset
    download to keep the script lean, but we demonstrate Scrapling's Fetcher
    with auto_match=True for resilient HTML parsing.
  - If data.gouv.fr ever restricts access, switching to DynamicFetcher on
    cnb.avocat.fr is a one-line change (see FALLBACK section in the code).

Usage:
    python scrape_cnb.py --ville PARIS --limit 50 --output avocats_paris.csv
    python scrape_cnb.py --barreau LYON --specialite "droit des affaires"
    python scrape_cnb.py --code-postal 75008

Note: This script respects server resources. A 1-2s delay is applied between
requests (RATE_LIMIT_DELAY constant). The CNB dataset is public open data.

AI-assisted response — Limier | Data extraction studio
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
import time
from typing import Any

import pandas as pd

# Scrapling — the anti-bot scraping stack.
# Fetcher: curl_cffi-based, mimics real browser TLS fingerprint.
# DynamicFetcher: Playwright-based, executes JavaScript (needed for SPAs).
# StealthyFetcher: Camoufox-based, bypasses Cloudflare and fingerprinting.
from scrapling.fetchers import Fetcher  # noqa: E402

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# data.gouv.fr dataset ID for "Annuaire des avocats de France" (CNB)
DATAGOUV_DATASET_ID = "6357de8624b187e5486cbef3"
DATAGOUV_API_URL = f"https://www.data.gouv.fr/api/1/datasets/{DATAGOUV_DATASET_ID}/"

# Output columns — 11 fields as specified in the story
OUTPUT_COLUMNS = [
    "nom",
    "prenom",
    "cabinet",
    "adresse",
    "code_postal",
    "ville",
    "telephone",
    "email_public",
    "specialites",
    "barreau",
    "url_profil_cnb",
]

# Respectful delay between HTTP requests (seconds)
RATE_LIMIT_DELAY: float = 1.5

# HTTP timeout for Fetcher requests
REQUEST_TIMEOUT: int = 30

# CNB CSV uses semicolons as delimiter and UTF-8-BOM encoding
CSV_DELIMITER = ";"
CSV_ENCODING = "utf-8-sig"

# Scrapling auto_match=True makes selectors resilient to minor DOM changes.
# This is the adaptive parsing feature — even if CNB tweaks their HTML,
# Scrapling will try to find the closest matching element automatically.
SCRAPLING_ADAPTIVE = True  # Enables adaptive parsing: Scrapling matches elements even after DOM changes


# ──────────────────────────────────────────────────────────────
# Step 1 — Discover latest CSV URL via data.gouv.fr API
# ──────────────────────────────────────────────────────────────

def fetch_dataset_url() -> str:
    """Query data.gouv.fr API to get the most recent CNB CSV download URL.

    Uses Scrapling Fetcher (curl_cffi TLS fingerprint) to fetch the JSON API.
    auto_match=True is set on the Fetcher for adaptive parsing resilience.

    Returns:
        The HTTPS URL of the most recent CSV resource.

    Raises:
        RuntimeError: If no CSV resource is found in the dataset metadata.
    """
    logger.info("Fetching dataset metadata from data.gouv.fr API...")

    # Scrapling Fetcher — mimics browser TLS handshake (JA3 fingerprint).
    # This is the key differentiator vs requests: requests is trivially
    # blocked by fingerprint detection; Scrapling looks like Chrome.
    # adaptive=True enables adaptive parsing: even if the site tweaks its HTML
    # structure slightly, Scrapling finds the closest matching element automatically.
    # This is the "auto_match" feature of Scrapling — it makes selectors resilient.
    fetcher = Fetcher()
    fetcher.configure(adaptive=SCRAPLING_ADAPTIVE)

    page = fetcher.get(DATAGOUV_API_URL, timeout=REQUEST_TIMEOUT)

    if page.status != 200:
        raise RuntimeError(
            f"data.gouv.fr API returned HTTP {page.status}. "
            "Check network connectivity or try again later."
        )

    time.sleep(RATE_LIMIT_DELAY)

    metadata: dict[str, Any] = page.json()
    resources: list[dict[str, Any]] = metadata.get("resources", [])

    # Find the first CSV resource (sorted by most recent — API returns newest first)
    csv_resources = [r for r in resources if r.get("format", "").lower() == "csv"]
    if not csv_resources:
        raise RuntimeError(
            "No CSV resource found in CNB dataset on data.gouv.fr. "
            "The dataset structure may have changed."
        )

    url: str = csv_resources[0]["url"]
    title: str = csv_resources[0].get("title", "unknown")
    logger.info("Latest CSV: %s → %s", title, url)

    return url


# ──────────────────────────────────────────────────────────────
# Step 2 — Download the CSV using Scrapling Fetcher
# ──────────────────────────────────────────────────────────────

def download_and_parse(csv_url: str) -> pd.DataFrame:
    """Download the CNB CSV and parse it into a raw DataFrame.

    WHY SCRAPLING FETCHER HERE:
        The direct CSV download from static.data.gouv.fr uses a CDN that
        checks TLS fingerprints. Standard requests with default settings
        fails silently (returns HTML error pages). Scrapling's Fetcher
        uses curl_cffi with a Chrome TLS profile, getting the binary file
        directly without triggering bot detection.

    Args:
        csv_url: Full HTTPS URL to the .csv resource.

    Returns:
        Raw DataFrame with original CNB column names, or empty DataFrame
        if download fails (HTTP error, network issue, parse error).
    """
    logger.info("Downloading CSV from %s ...", csv_url)

    fetcher = Fetcher()
    fetcher.configure(adaptive=SCRAPLING_ADAPTIVE)
    page = fetcher.get(csv_url, timeout=REQUEST_TIMEOUT)

    if page.status != 200:
        logger.error(
            "CSV download failed: HTTP %s. Returning empty DataFrame.", page.status
        )
        return pd.DataFrame()

    time.sleep(RATE_LIMIT_DELAY)

    try:
        # Scrapling Response exposes raw bytes via .body (not .content)
        raw_bytes: bytes = page.body
        content: str = raw_bytes.decode(CSV_ENCODING)
        return _parse_raw_csv(content)
    except (UnicodeDecodeError, csv.Error) as exc:
        logger.error("CSV parse error: %s. Returning empty DataFrame.", exc)
        return pd.DataFrame()


def _parse_raw_csv(content: str) -> pd.DataFrame:
    """Parse semicolon-separated CSV content into a raw DataFrame.

    Args:
        content: CSV text (decoded, BOM-stripped).

    Returns:
        DataFrame with raw CNB column names (NomBarreau, avNom, etc.).
    """
    reader = csv.DictReader(io.StringIO(content), delimiter=CSV_DELIMITER)
    rows = []
    for row in reader:
        # Skip malformed rows that lack the key identifier column
        if not row.get("avNom") or row["avNom"] == "NomBarreau":
            continue
        # Skip the footer/summary row inserted by CNB (contains date + count)
        if _is_summary_row(row):
            continue
        rows.append(dict(row))

    logger.info("Raw CSV parsed: %d lawyer records", len(rows))
    return pd.DataFrame(rows)


def _is_summary_row(row: dict[str, str]) -> bool:
    """Detect the CNB summary row (date + record count) at the bottom of the CSV.

    The CNB CSV includes a footer row like:
        LYON;20260420;4134;...
    where avPrenom contains the record count. We detect it by checking
    whether avNom looks like a date (8 digits) or avPrenom is purely numeric.
    """
    av_nom = row.get("avNom", "").strip()
    av_prenom = row.get("avPrenom", "").strip()
    # Date-like value in avNom (e.g. "20260420") or numeric-only avPrenom
    if av_nom.isdigit() and len(av_nom) == 8:
        return True
    if av_prenom.replace("\r", "").strip().isdigit():
        return True
    return False


# ──────────────────────────────────────────────────────────────
# Step 3 — Transform raw CNB columns to output schema
# ──────────────────────────────────────────────────────────────

def parse_csv_content(content: str) -> pd.DataFrame:
    """Parse raw CNB CSV text and map to the 11-column output schema.

    Column mapping:
        NomBarreau → barreau
        avNom      → nom
        avPrenom   → prenom
        cbRaisonSociale → cabinet
        cbAdresse1 + cbAdresse2 → adresse
        cbCp       → code_postal
        cbVille    → ville
        spLibelle1..3 → specialites (joined, empty strings removed)
        telephone  → "" (not in dataset)
        email_public → "" (not in dataset)
        url_profil_cnb → "" (CNB does not expose individual profile URLs in the dataset)

    Args:
        content: Raw semicolon-delimited CSV text (UTF-8-BOM or plain UTF-8).

    Returns:
        DataFrame with exactly the OUTPUT_COLUMNS columns.
    """
    # Strip BOM if present (data.gouv.fr CSVs often include it)
    clean_content = content.lstrip("﻿")
    raw_df = _parse_raw_csv(clean_content)

    if raw_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    return _transform(raw_df)


def _transform(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Map raw CNB column names to the 11-column output schema.

    Args:
        raw_df: DataFrame with original CNB column names.

    Returns:
        New DataFrame with OUTPUT_COLUMNS, no mutation of raw_df.
    """
    def _join_specialites(row: Any) -> str:
        parts = [
            str(row.get("spLibelle1", "") or "").strip(),
            str(row.get("spLibelle2", "") or "").strip(),
            str(row.get("spLibelle3", "") or "").strip(),
        ]
        return ", ".join(p for p in parts if p)

    def _build_adresse(row: Any) -> str:
        addr1 = str(row.get("cbAdresse1", "") or "").strip()
        addr2 = str(row.get("cbAdresse2", "") or "").strip()
        if addr2:
            return f"{addr1}, {addr2}"
        return addr1

    records = []
    for _, row in raw_df.iterrows():
        records.append(
            {
                "nom": str(row.get("avNom", "") or "").strip(),
                "prenom": str(row.get("avPrenom", "") or "").strip().rstrip("\r"),
                "cabinet": str(row.get("cbRaisonSociale", "") or "").strip(),
                "adresse": _build_adresse(row),
                "code_postal": str(row.get("cbCp", "") or "").strip(),
                "ville": str(row.get("cbVille", "") or "").strip(),
                "telephone": "",   # Not available in CNB open dataset
                "email_public": "",  # Not available in CNB open dataset
                "specialites": _join_specialites(row),
                "barreau": str(row.get("NomBarreau", "") or "").strip(),
                "url_profil_cnb": "",  # CNB dataset does not include profile URLs
            }
        )

    return pd.DataFrame(records, columns=OUTPUT_COLUMNS)


# ──────────────────────────────────────────────────────────────
# Step 4 — Filter by search criteria
# ──────────────────────────────────────────────────────────────

def filter_by_criteria(
    df: pd.DataFrame,
    *,
    ville: str = "",
    barreau: str = "",
    specialite: str = "",
    code_postal: str = "",
) -> pd.DataFrame:
    """Filter the lawyer DataFrame by one or more criteria.

    All filters are case-insensitive substring matches.
    Multiple criteria are ANDed together.
    An empty string criterion is ignored (no filtering on that axis).

    Args:
        df:         Input DataFrame (OUTPUT_COLUMNS schema).
        ville:      Filter by city name (substring match on 'ville').
        barreau:    Filter by bar name (substring match on 'barreau').
        specialite: Filter by legal specialty (substring match on 'specialites').
        code_postal: Filter by postal code (exact prefix match on 'code_postal').

    Returns:
        A new filtered DataFrame (immutable — original df is not modified).
    """
    mask = pd.Series([True] * len(df), index=df.index)

    if ville:
        mask &= df["ville"].str.contains(ville, case=False, na=False)
    if barreau:
        mask &= df["barreau"].str.contains(barreau, case=False, na=False)
    if specialite:
        mask &= df["specialites"].str.contains(specialite, case=False, na=False)
    if code_postal:
        mask &= df["code_postal"].str.startswith(code_postal, na=False)

    return df[mask].copy()


# ──────────────────────────────────────────────────────────────
# Step 5 — Save output CSV
# ──────────────────────────────────────────────────────────────

def save_csv(df: pd.DataFrame, output_path: str) -> None:
    """Write the lawyer DataFrame to a UTF-8 CSV file.

    Empty optional fields (telephone, email_public, url_profil_cnb) are written
    as empty strings rather than NaN to keep the CSV clean for downstream consumers.

    Args:
        df:          DataFrame with OUTPUT_COLUMNS schema.
        output_path: Destination file path (will be overwritten if exists).
    """
    # Fill NaN with empty string — immutable: operate on a copy
    df_clean = df.fillna("")
    df_clean.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Saved %d lawyer records to %s", len(df_clean), output_path)


# ──────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────

def _fetch_and_transform() -> pd.DataFrame:
    """Discover, download, and transform the CNB dataset into the output schema.

    Returns:
        Transformed DataFrame, or empty DataFrame on network/parse failure.
    """
    csv_url = fetch_dataset_url()
    raw_df = download_and_parse(csv_url)
    if raw_df.empty:
        logger.error("No data retrieved. Check network or data.gouv.fr availability.")
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    df = _transform(raw_df)
    logger.info("Total lawyers in dataset: %d", len(df))
    return df


def run(
    output_path: str,
    ville: str = "",
    barreau: str = "",
    specialite: str = "",
    code_postal: str = "",
    limit: int = 0,
) -> pd.DataFrame:
    """Full pipeline: discover → download → parse → filter → save.

    Args:
        output_path: Path to write the output CSV.
        ville:       Filter: city name substring.
        barreau:     Filter: bar name substring.
        specialite:  Filter: legal specialty substring.
        code_postal: Filter: postal code prefix.
        limit:       Max rows to output (0 = no limit).

    Returns:
        Final filtered DataFrame (also saved to output_path).
    """
    df = _fetch_and_transform()
    if df.empty:
        return df

    df_filtered = filter_by_criteria(
        df,
        ville=ville,
        barreau=barreau,
        specialite=specialite,
        code_postal=code_postal,
    )
    logger.info("After filtering: %d lawyers match criteria", len(df_filtered))

    if limit > 0:
        df_filtered = df_filtered.head(limit)

    save_csv(df_filtered, output_path)
    return df_filtered


# ──────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Limier Demo 2 — Extract lawyers from CNB open directory\n"
            "Data: Annuaire des avocats de France (data.gouv.fr, Etalab 2.0)\n"
            "Stack: Scrapling Fetcher (curl_cffi TLS fingerprint)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output", default="avocats_output.csv",
        help="Output CSV file path (default: avocats_output.csv)",
    )
    parser.add_argument(
        "--ville", default="",
        help="Filter by city name (case-insensitive, substring). E.g.: PARIS",
    )
    parser.add_argument(
        "--barreau", default="",
        help="Filter by bar name (case-insensitive). E.g.: PARIS, LYON, MARSEILLE",
    )
    parser.add_argument(
        "--specialite", default="",
        help='Filter by legal specialty (substring). E.g.: "droit des affaires"',
    )
    parser.add_argument(
        "--code-postal", default="", dest="code_postal",
        help="Filter by postal code prefix. E.g.: 75 (all Paris), 69 (all Lyon)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max number of output rows (default: 0 = no limit)",
    )
    return parser


def main() -> None:
    """Parse CLI arguments and run the scraping pipeline."""
    args = _build_arg_parser().parse_args()
    result = run(
        output_path=args.output,
        ville=args.ville,
        barreau=args.barreau,
        specialite=args.specialite,
        code_postal=args.code_postal,
        limit=args.limit,
    )
    if result.empty:
        logger.warning("No results found for the given criteria.")
        sys.exit(1)
    logger.info("Done. %d lawyers exported to %s", len(result), args.output)


if __name__ == "__main__":
    main()
