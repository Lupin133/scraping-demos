"""
Enrichissement SIRET
============================
Prend un CSV de SIRETs (colonne `siret`), retourne un CSV enrichi avec :
  - Données entreprise : Recherche-Entreprises (api.gouv.fr)
  - Géocodage : Base Adresse Nationale (api-adresse.data.gouv.fr)
  - Risques naturels : Géorisques BRGM (georisques.gouv.fr)

Toutes les APIs sont gratuites et sans authentification.

Usage :
    python enrich.py sample_input.csv sample_output.csv

Tom Engels
"""
from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import requests

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

API_ENTREPRISES = "https://recherche-entreprises.api.gouv.fr/search"
API_BAN = "https://api-adresse.data.gouv.fr/search/"
API_GEORISQUES = "https://www.georisques.gouv.fr/api/v1/gaspar/risques"

TIMEOUT = 10          # secondes par requête HTTP
MAX_RETRIES = 3
WORKERS = 4           # threads pour parallélisation

OUTPUT_COLUMNS = [
    "siret", "nom_entreprise", "nom_complet", "code_naf", "libelle_naf",
    "statut", "date_creation", "adresse_complete", "code_postal", "commune",
    "latitude", "longitude", "risques_inondation", "risques_seismique",
]

# Table NAF partielle — codes fréquents dans le B2B tech/services.
# Suffisant pour une démo ; les codes inconnus retournent "".
NAF_LABELS: dict[str, str] = {
    "62.01Z": "Programmation informatique",
    "62.02A": "Conseil en systèmes et logiciels informatiques",
    "62.02B": "Tierce maintenance de systèmes et d'applications informatiques",
    "62.03Z": "Gestion d'installations informatiques",
    "62.09Z": "Autres activités informatiques",
    "63.11Z": "Traitement de données, hébergement et activités connexes",
    "63.12Z": "Portails internet",
    "64.19Z": "Autres intermédiations monétaires",
    "70.10Z": "Activités des sièges sociaux",
    "70.21Z": "Conseil en relations publiques et communication",
    "70.22Z": "Conseil pour les affaires et autres conseils de gestion",
    "73.11Z": "Activités des agences de publicité",
    "73.20Z": "Études de marché et sondages",
    "74.90B": "Activités spécialisées, scientifiques et techniques diverses",
    "82.11Z": "Services administratifs combinés de bureau",
    "82.19Z": "Photocopie, préparation de documents et autres activités spécialisées",
    "82.99Z": "Autres activités de soutien aux entreprises",
    "46.51Z": "Commerce de gros d'ordinateurs, d'équipements informatiques périphériques et de logiciels",
    "58.29A": "Édition de logiciels systèmes et de réseau",
    "58.29B": "Édition de logiciels outils de développement et de langages",
    "58.29C": "Édition de logiciels applicatifs",
    "61.10Z": "Télécommunications filaires",
    "61.20Z": "Télécommunications sans fil",
    "61.90Z": "Autres activités de télécommunication",
    "72.19Z": "Autre recherche-développement en sciences physiques et naturelles",
    "72.20Z": "Recherche-développement en sciences humaines et sociales",
    "85.59B": "Autres formations",
}


# ──────────────────────────────────────────────────────────────
# Utilitaires HTTP
# ──────────────────────────────────────────────────────────────

def _get_with_retry(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET HTTP avec retry exponentiel sur 429 et timeout. Retourne {} en cas d'échec."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json()  # type: ignore[no-any-return]
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning("Rate limit 429 sur %s, retry dans %ss", url, wait)
                time.sleep(wait)
                continue
            logger.warning("HTTP %s sur %s", resp.status_code, url)
            return {}
        except requests.Timeout:
            logger.warning("Timeout sur %s (tentative %d/%d)", url, attempt + 1, MAX_RETRIES)
            return {}
        except requests.RequestException as exc:
            logger.warning("Erreur réseau %s : %s", url, exc)
            return {}
    logger.error("Échec après %d tentatives sur %s", MAX_RETRIES, url)
    return {}


def resolve_naf_label(code_naf: str) -> str:
    """Retourne le libellé NAF pour un code donné, ou '' si inconnu."""
    return NAF_LABELS.get(code_naf, "")


# ──────────────────────────────────────────────────────────────
# Appels API métier
# ──────────────────────────────────────────────────────────────

def fetch_entreprise(siret: str) -> dict[str, Any]:
    """Appelle Recherche-Entreprises et retourne les champs métier.

    Retourne un dict vide si le SIRET est inconnu ou si l'API échoue.
    """
    data = _get_with_retry(API_ENTREPRISES, {"q": siret, "limit": 1})
    results = data.get("results", [])
    if not results:
        logger.info("SIRET %s : aucun résultat Entreprises", siret)
        return {}

    hit = results[0]
    siege = hit.get("siege", {})

    # Extraction coordonnées depuis le champ siege ou coordonnees
    lat_str = siege.get("latitude") or ""
    lon_str = siege.get("longitude") or ""
    if not lat_str and siege.get("coordonnees"):
        parts = siege["coordonnees"].split(",")
        lat_str, lon_str = (parts[0], parts[1]) if len(parts) == 2 else ("", "")

    code_naf = hit.get("activite_principale") or siege.get("activite_principale") or ""

    return {
        "nom_entreprise": hit.get("nom_raison_sociale") or hit.get("nom_complet") or "",
        "nom_complet": hit.get("nom_complet") or "",
        "code_naf": code_naf,
        "libelle_naf": resolve_naf_label(code_naf),
        "statut": siege.get("etat_administratif") or "",
        "date_creation": hit.get("date_creation") or "",
        "adresse_complete": siege.get("adresse") or "",
        "code_postal": siege.get("code_postal") or "",
        "commune": siege.get("libelle_commune") or "",
        "code_insee": siege.get("commune") or "",
        "_lat_siege": lat_str,
        "_lon_siege": lon_str,
    }


def fetch_geocode(adresse: str) -> tuple[float, float]:
    """Géocode une adresse via la BAN. Retourne (lat, lon) ou (0.0, 0.0)."""
    if not adresse:
        return (0.0, 0.0)
    data = _get_with_retry(API_BAN, {"q": adresse, "limit": 1})
    features = data.get("features", [])
    if not features:
        logger.info("BAN : aucun résultat pour %r", adresse)
        return (0.0, 0.0)
    coords = features[0].get("geometry", {}).get("coordinates", [])
    if len(coords) < 2:
        return (0.0, 0.0)
    lon, lat = coords[0], coords[1]
    return (float(lat), float(lon))


def _normalize_code_insee(code_insee: str) -> str:
    """Normalise les codes INSEE des arrondissements parisiens vers la commune mère.

    Paris (75101-75120), Lyon (69381-69389), Marseille (13201-13216)
    utilisent des codes d'arrondissement dans Sirene, mais Géorisques
    n'indexe que la commune globale.
    """
    if code_insee.startswith("751") and len(code_insee) == 5:
        return "75056"
    if code_insee.startswith("693") and len(code_insee) == 5:
        return "69123"
    if code_insee.startswith("132") and len(code_insee) == 5:
        return "13055"
    return code_insee


def fetch_georisques(code_insee: str) -> dict[str, bool]:
    """Interroge Géorisques pour une commune INSEE. Retourne les flags de risque."""
    empty: dict[str, bool] = {"risques_inondation": False, "risques_seismique": False}
    if not code_insee:
        return empty

    normalized = _normalize_code_insee(code_insee)
    data = _get_with_retry(API_GEORISQUES, {"code_insee": normalized})
    items = data.get("data", [])
    if not items:
        logger.info("Géorisques : aucun résultat pour code_insee=%s", code_insee)
        return empty

    risques = items[0].get("risques_detail", [])
    nums = {r.get("num_risque") for r in risques}
    return {
        "risques_inondation": "11" in nums,
        "risques_seismique": "13" in nums,
    }


# ──────────────────────────────────────────────────────────────
# Enrichissement d'une ligne
# ──────────────────────────────────────────────────────────────

def enrich_row(siret: str) -> dict[str, Any]:
    """Enrichit un SIRET en appelant les 3 APIs. Retourne un dict avec 14 colonnes."""
    logger.info("Enrichissement SIRET %s", siret)

    entreprise = fetch_entreprise(siret)
    if not entreprise:
        return {col: "" for col in OUTPUT_COLUMNS} | {"siret": siret}

    adresse = entreprise.get("adresse_complete", "")
    lat_siege = entreprise.get("_lat_siege", "")
    lon_siege = entreprise.get("_lon_siege", "")

    # Géocodage : on préfère les coordonnées siège si disponibles, sinon BAN
    if lat_siege and lon_siege:
        lat = float(lat_siege)
        lon = float(lon_siege)
    else:
        lat, lon = fetch_geocode(adresse)

    code_insee = entreprise.get("code_insee", "")
    georisques = fetch_georisques(code_insee)

    return {
        "siret": siret,
        "nom_entreprise": entreprise.get("nom_entreprise", ""),
        "nom_complet": entreprise.get("nom_complet", ""),
        "code_naf": entreprise.get("code_naf", ""),
        "libelle_naf": entreprise.get("libelle_naf", ""),
        "statut": entreprise.get("statut", ""),
        "date_creation": entreprise.get("date_creation", ""),
        "adresse_complete": adresse,
        "code_postal": entreprise.get("code_postal", ""),
        "commune": entreprise.get("commune", ""),
        "latitude": lat,
        "longitude": lon,
        "risques_inondation": georisques["risques_inondation"],
        "risques_seismique": georisques["risques_seismique"],
    }


# ──────────────────────────────────────────────────────────────
# Pipeline principal
# ──────────────────────────────────────────────────────────────

def run_enrichment(input_path: str, output_path: str) -> pd.DataFrame:
    """Charge le CSV d'entrée, enrichit en parallèle, sauvegarde le résultat."""
    df_in = pd.read_csv(input_path, dtype=str)
    if "siret" not in df_in.columns:
        raise ValueError("Le CSV d'entrée doit contenir une colonne 'siret'.")

    sirets = df_in["siret"].dropna().str.strip().tolist()
    logger.info("Début enrichissement — %d SIRETs, %d workers", len(sirets), WORKERS)

    rows: list[dict[str, Any]] = [{}] * len(sirets)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(enrich_row, s): i for i, s in enumerate(sirets)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                rows[idx] = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.error("Erreur inattendue pour index %d : %s", idx, exc)
                rows[idx] = {"siret": sirets[idx]}

    df_out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df_out.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Fichier enrichi sauvegardé : %s (%d lignes)", output_path, len(df_out))
    return df_out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrichissement SIRET (Sirene + BAN + Géorisques)"
    )
    parser.add_argument("input", help="CSV d'entrée avec colonne 'siret'")
    parser.add_argument("output", help="CSV de sortie enrichi (14 colonnes)")
    args = parser.parse_args()

    run_enrichment(args.input, args.output)


if __name__ == "__main__":
    main()
