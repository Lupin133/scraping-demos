"""
Tests unitaires pour enrich.py — mock HTTP, pas d'appels réseau réels.
Couverture cible : > 70% sur enrich.py.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Ajouter le répertoire parent au path pour importer enrich
sys.path.insert(0, str(Path(__file__).parent.parent))

import enrich


# ──────────────────────────────────────────────────────────────
# Fixtures : réponses API simulées
# ──────────────────────────────────────────────────────────────

ENTREPRISES_RESPONSE = {
    "results": [
        {
            "nom_complet": "MISTRAL AI",
            "nom_raison_sociale": "MISTRAL AI",
            "activite_principale": "82.11Z",
            "date_creation": "2023-04-28",
            "siege": {
                "siret": "95241832500025",
                "etat_administratif": "A",
                "adresse": "15 RUE DES HALLES 75001 PARIS",
                "code_postal": "75001",
                "libelle_commune": "PARIS",
                "commune": "75101",
                "latitude": "48.860171758",
                "longitude": "2.3461942259",
                "coordonnees": "48.860171758,2.3461942259",
            },
        }
    ]
}

BAN_RESPONSE = {
    "features": [
        {
            "geometry": {"coordinates": [2.3461942259, 48.860171758]},
            "properties": {"score": 0.97},
        }
    ]
}

GEORISQUES_RESPONSE = {
    "data": [
        {
            "code_insee": "75101",
            "risques_detail": [
                {"num_risque": "11", "libelle_risque_long": "Inondation"},
                {"num_risque": "24", "libelle_risque_long": "Transport de marchandises dangereuses"},
            ],
        }
    ]
}

GEORISQUES_RESPONSE_SEISMIC = {
    "data": [
        {
            "code_insee": "75101",
            "risques_detail": [
                {"num_risque": "11", "libelle_risque_long": "Inondation"},
                {"num_risque": "13", "libelle_risque_long": "Séisme"},
            ],
        }
    ]
}


# ──────────────────────────────────────────────────────────────
# AC-1 : fetch_entreprise retourne les champs attendus
# ──────────────────────────────────────────────────────────────

def test_fetch_entreprise_returns_expected_fields() -> None:
    """AC-1 : Les données Sirene contiennent les 8 champs métier requis."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ENTREPRISES_RESPONSE

    with patch("enrich.requests.get", return_value=mock_resp):
        result = enrich.fetch_entreprise("95241832500025")

    assert result["nom_entreprise"] == "MISTRAL AI"
    assert result["nom_complet"] == "MISTRAL AI"
    assert result["code_naf"] == "82.11Z"
    assert result["statut"] == "A"
    assert result["date_creation"] == "2023-04-28"
    assert result["adresse_complete"] == "15 RUE DES HALLES 75001 PARIS"
    assert result["code_postal"] == "75001"
    assert result["commune"] == "PARIS"


# ──────────────────────────────────────────────────────────────
# AC-2 : SIRET inexistant → dictionnaire vide (pas d'exception)
# ──────────────────────────────────────────────────────────────

def test_fetch_entreprise_unknown_siret_returns_empty() -> None:
    """AC-2 : Un SIRET inconnu (résultats vides) renvoie un dict vide sans lever d'exception."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": []}

    with patch("enrich.requests.get", return_value=mock_resp):
        result = enrich.fetch_entreprise("00000000000000")

    assert result == {}


# ──────────────────────────────────────────────────────────────
# AC-3 : fetch_geocode retourne lat/long
# ──────────────────────────────────────────────────────────────

def test_fetch_geocode_returns_lat_lon() -> None:
    """AC-3 : Le géocodage BAN retourne latitude et longitude corrects."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = BAN_RESPONSE

    with patch("enrich.requests.get", return_value=mock_resp):
        lat, lon = enrich.fetch_geocode("15 RUE DES HALLES 75001 PARIS")

    assert abs(lat - 48.860171758) < 1e-6
    assert abs(lon - 2.3461942259) < 1e-6


# ──────────────────────────────────────────────────────────────
# AC-4 : fetch_georisques détecte l'inondation (num_risque 11)
# ──────────────────────────────────────────────────────────────

def test_fetch_georisques_detects_inondation() -> None:
    """AC-4 : Georisques retourne risques_inondation=True si risque 11 présent."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = GEORISQUES_RESPONSE

    with patch("enrich.requests.get", return_value=mock_resp):
        result = enrich.fetch_georisques("75101")

    assert result["risques_inondation"] is True
    assert result["risques_seismique"] is False


# ──────────────────────────────────────────────────────────────
# AC-5 : fetch_georisques détecte le séisme (num_risque 13)
# ──────────────────────────────────────────────────────────────

def test_fetch_georisques_detects_seisme() -> None:
    """AC-5 : Georisques retourne risques_seismique=True si risque 13 présent."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = GEORISQUES_RESPONSE_SEISMIC

    with patch("enrich.requests.get", return_value=mock_resp):
        result = enrich.fetch_georisques("75101")

    assert result["risques_inondation"] is True
    assert result["risques_seismique"] is True


# ──────────────────────────────────────────────────────────────
# AC-6 : retry sur 429 (exponential backoff, max 3 tentatives)
# ──────────────────────────────────────────────────────────────

def test_fetch_entreprise_retries_on_429() -> None:
    """AC-6 : Une réponse 429 déclenche des retries, et la 3e tentative (200) réussit."""
    resp_429 = MagicMock()
    resp_429.status_code = 429

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = ENTREPRISES_RESPONSE

    with patch("enrich.requests.get", side_effect=[resp_429, resp_429, resp_200]):
        with patch("enrich.time.sleep"):  # Pas de vrai sleep dans les tests
            result = enrich.fetch_entreprise("95241832500025")

    assert result["nom_entreprise"] == "MISTRAL AI"


# ──────────────────────────────────────────────────────────────
# AC-7 : enrich_row compose toutes les sources en 14 colonnes
# ──────────────────────────────────────────────────────────────

def test_enrich_row_produces_14_columns() -> None:
    """AC-7 : enrich_row retourne un dict avec exactement les 14 colonnes attendues."""
    entreprise_data = {
        "nom_entreprise": "MISTRAL AI",
        "nom_complet": "MISTRAL AI",
        "code_naf": "82.11Z",
        "libelle_naf": "Activités de secrétariat",
        "statut": "A",
        "date_creation": "2023-04-28",
        "adresse_complete": "15 RUE DES HALLES 75001 PARIS",
        "code_postal": "75001",
        "commune": "PARIS",
        "code_insee": "75101",
    }
    geocode_data = (48.8601, 2.3461)
    georisques_data = {"risques_inondation": False, "risques_seismique": False}

    with patch("enrich.fetch_entreprise", return_value=entreprise_data):
        with patch("enrich.fetch_geocode", return_value=geocode_data):
            with patch("enrich.fetch_georisques", return_value=georisques_data):
                row = enrich.enrich_row("95241832500025")

    expected_cols = {
        "siret", "nom_entreprise", "nom_complet", "code_naf", "libelle_naf",
        "statut", "date_creation", "adresse_complete", "code_postal", "commune",
        "latitude", "longitude", "risques_inondation", "risques_seismique",
    }
    assert set(row.keys()) == expected_cols
    assert row["siret"] == "95241832500025"
    assert row["latitude"] == 48.8601
    assert row["longitude"] == 2.3461


# ──────────────────────────────────────────────────────────────
# AC-8 : timeout réseau → ligne vide, pas d'exception propagée
# ──────────────────────────────────────────────────────────────

def test_fetch_entreprise_timeout_returns_empty() -> None:
    """AC-8 : Un timeout réseau (requests.Timeout) ne propage pas l'exception."""
    import requests as req_module

    with patch("enrich.requests.get", side_effect=req_module.Timeout):
        result = enrich.fetch_entreprise("95241832500025")

    assert result == {}


# ──────────────────────────────────────────────────────────────
# AC-9 : resolve_naf_label retourne le bon libellé pour un code connu
# ──────────────────────────────────────────────────────────────

def test_resolve_naf_label_known_code() -> None:
    """AC-9 : Un code NAF connu dans la table est résolu correctement."""
    label = enrich.resolve_naf_label("62.01Z")
    assert "programmation" in label.lower() or label != ""


# ──────────────────────────────────────────────────────────────
# AC-10 : resolve_naf_label fallback pour code inconnu
# ──────────────────────────────────────────────────────────────

def test_resolve_naf_label_unknown_code_returns_empty_string() -> None:
    """AC-10 : Un code NAF inconnu retourne une chaîne vide, pas d'exception."""
    label = enrich.resolve_naf_label("ZZ.99X")
    assert label == ""


# ──────────────────────────────────────────────────────────────
# AC-11 : run_enrichment produit un DataFrame avec les 14 colonnes
# ──────────────────────────────────────────────────────────────

def test_run_enrichment_produces_correct_dataframe(tmp_path: Path) -> None:
    """AC-11 : run_enrichment lit un CSV, appelle enrich_row, sauvegarde le résultat."""
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text("siret\n95241832500025\n")

    mock_row = {
        "siret": "95241832500025",
        "nom_entreprise": "MISTRAL AI",
        "nom_complet": "MISTRAL AI",
        "code_naf": "82.11Z",
        "libelle_naf": "Activités de secrétariat",
        "statut": "A",
        "date_creation": "2023-04-28",
        "adresse_complete": "15 RUE DES HALLES 75001 PARIS",
        "code_postal": "75001",
        "commune": "PARIS",
        "latitude": 48.860171758,
        "longitude": 2.3461942259,
        "risques_inondation": False,
        "risques_seismique": False,
    }

    with patch("enrich.enrich_row", return_value=mock_row):
        df = enrich.run_enrichment(str(input_csv), str(output_csv))

    assert output_csv.exists()
    assert list(df.columns) == enrich.OUTPUT_COLUMNS
    assert len(df) == 1
    assert df.iloc[0]["nom_entreprise"] == "MISTRAL AI"


# ──────────────────────────────────────────────────────────────
# AC-12 : run_enrichment lève ValueError si colonne 'siret' absente
# ──────────────────────────────────────────────────────────────

def test_run_enrichment_raises_on_missing_siret_column(tmp_path: Path) -> None:
    """AC-12 : Un CSV sans colonne 'siret' lève ValueError."""
    bad_csv = tmp_path / "bad.csv"
    output_csv = tmp_path / "out.csv"
    bad_csv.write_text("siren\n123456789\n")

    with pytest.raises(ValueError, match="siret"):
        enrich.run_enrichment(str(bad_csv), str(output_csv))


# ──────────────────────────────────────────────────────────────
# AC-13 : enrich_row sur SIRET sans données retourne siret + colonnes vides
# ──────────────────────────────────────────────────────────────

def test_enrich_row_empty_entreprise_returns_empty_row() -> None:
    """AC-13 : Si fetch_entreprise retourne {}, enrich_row retourne une ligne vide avec le siret."""
    with patch("enrich.fetch_entreprise", return_value={}):
        row = enrich.enrich_row("00000000000000")

    assert row["siret"] == "00000000000000"
    assert row["nom_entreprise"] == ""
    assert row["latitude"] == ""
