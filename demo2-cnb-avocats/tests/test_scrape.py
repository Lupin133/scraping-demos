"""
Tests for scrape_cnb.py — Limier Demo 2: CNB Avocats scraping.

Uses mocks to avoid live HTTP calls during CI.
Coverage target: > 60% on scrape_cnb.py
"""
from __future__ import annotations

import csv
import io
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import scrape_cnb


# ──────────────────────────────────────────────────────────────
# Fixtures & helpers
# ──────────────────────────────────────────────────────────────

SAMPLE_CSV_CONTENT = textwrap.dedent("""\
    NomBarreau;avNom;avPrenom;cbRaisonSociale;cbSiretSiren;cbAdresse1;cbAdresse2;cbCp;cbVille;spLibelle1;spLibelle2;spLibelle3;acDateSerment;spLibelle4;
    PARIS;DUPONT;Marie;CABINET DUPONT;123456789;8 rue de Rivoli;;75001;PARIS;Droit des affaires;;; 20010115;Français;
    PARIS;MARTIN;Jean-Pierre;MARTIN AVOCATS;987654321;12 avenue de la Paix;;75008;PARIS;Droit social;Droit pénal;;19950310;Anglais;
    PARIS;BERNARD;Sophie;BERNARD & ASSOC;555333111;5 place Vendôme;;75001;PARIS;;;; 20100601;Français;
    LYON;DURAND;Claire;DURAND CLAIRE;444222888;45 avenue Jean Jaurès;;69007;LYON;Droit immobilier;;; 20051120;Français;
    LYON;LEBLANC;Thomas;LEBLANC THOMAS;111777444;8 place Bellecour;;69002;LYON;Droit des sociétés;Droit commercial;;20000801;Français;
""")


def make_sample_df() -> pd.DataFrame:
    """Return a small parsed DataFrame matching SAMPLE_CSV_CONTENT."""
    return scrape_cnb.parse_csv_content(SAMPLE_CSV_CONTENT)


# ──────────────────────────────────────────────────────────────
# AC1 — parse_csv_content returns correct columns
# ──────────────────────────────────────────────────────────────

def test_parse_csv_content_returns_expected_columns():
    """parse_csv_content maps raw CNB columns to the 11 output columns."""
    df = make_sample_df()
    expected_cols = {
        "nom", "prenom", "cabinet", "adresse", "code_postal", "ville",
        "telephone", "email_public", "specialites", "barreau", "url_profil_cnb",
    }
    assert expected_cols.issubset(set(df.columns))


def test_parse_csv_content_row_count():
    """parse_csv_content returns one row per non-header line."""
    df = make_sample_df()
    assert len(df) == 5


def test_parse_csv_content_barreau_mapping():
    """NomBarreau maps to 'barreau' column."""
    df = make_sample_df()
    assert df["barreau"].iloc[0] == "PARIS"
    assert df["barreau"].iloc[3] == "LYON"


# ──────────────────────────────────────────────────────────────
# AC2 — filter_by_criteria filters correctly
# ──────────────────────────────────────────────────────────────

def test_filter_by_ville_returns_only_matching_rows():
    """filter_by_criteria with ville=PARIS returns only Paris rows."""
    df = make_sample_df()
    result = scrape_cnb.filter_by_criteria(df, ville="PARIS")
    assert len(result) == 3
    assert (result["ville"] == "PARIS").all()


def test_filter_by_barreau_case_insensitive():
    """filter_by_criteria barreau matching is case-insensitive."""
    df = make_sample_df()
    result = scrape_cnb.filter_by_criteria(df, barreau="paris")
    assert len(result) == 3


def test_filter_by_specialite_returns_matching_rows():
    """filter_by_criteria with specialite='social' matches substring."""
    df = make_sample_df()
    result = scrape_cnb.filter_by_criteria(df, specialite="social")
    assert len(result) >= 1
    assert result["specialites"].str.contains("social", case=False, na=False).any()


def test_filter_no_criteria_returns_all():
    """filter_by_criteria with no criteria returns original DataFrame unchanged."""
    df = make_sample_df()
    result = scrape_cnb.filter_by_criteria(df)
    assert len(result) == len(df)


def test_filter_by_code_postal():
    """filter_by_criteria with code_postal=75001 returns 2 rows."""
    df = make_sample_df()
    result = scrape_cnb.filter_by_criteria(df, code_postal="75001")
    assert len(result) == 2


# ──────────────────────────────────────────────────────────────
# AC3 — missing optional fields handled gracefully
# ──────────────────────────────────────────────────────────────

def test_missing_telephone_and_email_are_empty_strings():
    """telephone and email_public columns exist and are empty strings when absent."""
    df = make_sample_df()
    assert "telephone" in df.columns
    assert "email_public" in df.columns
    # CNB CSV does not include phone/email — should default to ""
    assert (df["telephone"] == "").all()
    assert (df["email_public"] == "").all()


# ──────────────────────────────────────────────────────────────
# AC4 — specialites combines spLibelle1..4
# ──────────────────────────────────────────────────────────────

def test_specialites_combines_multiple_splibelleN():
    """Rows with multiple spLibelle columns have them joined in 'specialites'."""
    df = make_sample_df()
    # MARTIN row has spLibelle1='Droit social' and spLibelle2='Droit pénal'
    martin_row = df[df["nom"] == "MARTIN"].iloc[0]
    assert "Droit social" in martin_row["specialites"]
    assert "Droit pénal" in martin_row["specialites"]


def test_specialites_empty_when_no_specialite():
    """Row with no spLibelle entries has empty string for specialites."""
    df = make_sample_df()
    bernard_row = df[df["nom"] == "BERNARD"].iloc[0]
    assert bernard_row["specialites"] == ""


# ──────────────────────────────────────────────────────────────
# AC5 — url_profil_cnb is constructed or left empty
# ──────────────────────────────────────────────────────────────

def test_url_profil_cnb_column_exists():
    """url_profil_cnb column exists in parsed output."""
    df = make_sample_df()
    assert "url_profil_cnb" in df.columns


# ──────────────────────────────────────────────────────────────
# AC6 — fetch_dataset_url returns the latest CSV URL
# ──────────────────────────────────────────────────────────────

def test_fetch_dataset_url_returns_string():
    """fetch_dataset_url returns a non-empty string URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "resources": [
            {"title": "annuaire-avocats-20260420.csv",
             "url": "https://static.data.gouv.fr/resources/annuaire-avocats-20260420.csv",
             "format": "csv"},
            {"title": "other.json", "url": "https://example.com/other.json", "format": "json"},
        ]
    }
    mock_response.status_code = 200

    with patch("scrape_cnb.Fetcher") as mock_fetcher_cls:
        mock_fetcher_instance = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher_instance
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.json.return_value = mock_response.json.return_value
        mock_fetcher_instance.get.return_value = mock_page

        url = scrape_cnb.fetch_dataset_url()

    assert isinstance(url, str)
    assert url.startswith("https://")
    assert url.endswith(".csv")


# ──────────────────────────────────────────────────────────────
# AC7 — download_and_parse mocks Fetcher, returns DataFrame
# ──────────────────────────────────────────────────────────────

def test_download_and_parse_returns_dataframe():
    """download_and_parse calls Fetcher.get and returns a raw DataFrame with CNB columns.

    download_and_parse returns the raw DataFrame (original CNB column names).
    The transform step (_transform) is separate and maps to output schema.
    """
    csv_url = "https://static.data.gouv.fr/resources/annuaire-avocats-20260420.csv"

    mock_page = MagicMock()
    mock_page.status = 200
    # Scrapling Response uses .body (bytes), not .content
    mock_page.body = SAMPLE_CSV_CONTENT.encode("utf-8-sig")

    with patch("scrape_cnb.Fetcher") as mock_fetcher_cls:
        mock_fetcher_instance = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher_instance
        mock_fetcher_instance.get.return_value = mock_page

        df = scrape_cnb.download_and_parse(csv_url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    # Raw CNB columns (not yet transformed)
    assert "NomBarreau" in df.columns
    assert "avNom" in df.columns


# ──────────────────────────────────────────────────────────────
# AC8 — save_csv writes correct number of rows
# ──────────────────────────────────────────────────────────────

def test_save_csv_writes_correct_rows(tmp_path: Path):
    """save_csv writes a valid CSV with header + N data rows."""
    df = make_sample_df()
    output_path = tmp_path / "output.csv"
    scrape_cnb.save_csv(df, str(output_path))

    assert output_path.exists()
    written = pd.read_csv(output_path)
    assert len(written) == len(df)
    assert "barreau" in written.columns


# ──────────────────────────────────────────────────────────────
# AC9 — error on Fetcher HTTP failure returns empty DataFrame
# ──────────────────────────────────────────────────────────────

def test_download_and_parse_on_http_error_returns_empty_df():
    """download_and_parse returns an empty DataFrame when Fetcher returns non-200."""
    mock_page = MagicMock()
    mock_page.status = 503
    mock_page.body = b""

    with patch("scrape_cnb.Fetcher") as mock_fetcher_cls:
        mock_fetcher_instance = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher_instance
        mock_fetcher_instance.get.return_value = mock_page

        df = scrape_cnb.download_and_parse("https://example.com/fake.csv")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
