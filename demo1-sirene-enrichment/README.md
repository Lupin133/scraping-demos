# Limier — Demo 1 : Enrichissement SIRET

![Python 3.13](https://img.shields.io/badge/Python-3.13-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![APIs FR](https://img.shields.io/badge/APIs-Sirene%20%7C%20BAN%20%7C%20G%C3%A9orisques-orange)

Enrichissez une liste de SIRETs en données entreprise complètes en une commande.
Données publiques, sans authentification, 100% Python.

## Ce que fait le script

**Input** : un CSV avec une colonne `siret` (ex : liste de prospects)

**Output** : CSV enrichi avec 14 colonnes :

| Colonne | Source | Description |
|---|---|---|
| `nom_entreprise` | Sirene | Raison sociale officielle |
| `nom_complet` | Sirene | Nom complet (peut inclure l'enseigne) |
| `code_naf` | Sirene | Code activité principale (APE) |
| `libelle_naf` | Table interne | Libellé lisible du code NAF |
| `statut` | Sirene | A = actif, F = fermé |
| `date_creation` | Sirene | Date de création de l'établissement |
| `adresse_complete` | Sirene | Adresse postale complète |
| `code_postal` | Sirene | Code postal |
| `commune` | Sirene | Commune |
| `latitude` | Sirene / BAN | Latitude WGS84 |
| `longitude` | Sirene / BAN | Longitude WGS84 |
| `risques_inondation` | Géorisques | True si commune exposée au risque inondation |
| `risques_seismique` | Géorisques | True si commune exposée au risque sismique |

## Exemple d'output

```
siret,nom_entreprise,code_naf,libelle_naf,statut,commune,latitude,longitude,risques_inondation,risques_seismique
95241832500025,MISTRAL AI,82.11Z,Services administratifs combinés de bureau,A,PARIS,48.860171758,2.3461942259,True,False
82216804300039,HUGGING FACE,62.01Z,Programmation informatique,A,PARIS,48.869742039,2.339379054,True,False
42476141900045,OVH (OVHCLOUD),63.11Z,"Traitement de données, hébergement",A,ROUBAIX,50.691629331,3.202261085,True,True
33070384400036,CAPGEMINI,70.10Z,Activités des sièges sociaux,A,PARIS,48.874693367,2.2936562012,True,False
```

7 entreprises enrichies en ~4 secondes (parallélisation 4 workers).

## APIs utilisées

Toutes **gratuites et sans authentification** :

- **[Recherche-Entreprises](https://recherche-entreprises.api.gouv.fr/)** — données Sirene (DINUM / data.gouv.fr)
- **[Base Adresse Nationale](https://api-adresse.data.gouv.fr/)** — géocodage officiel France
- **[Géorisques BRGM](https://www.georisques.gouv.fr/api/)** — risques naturels par commune

## Installation

```bash
pip install -r requirements.txt
```

Dépendances : `pandas`, `requests`. Python 3.13 recommandé.

## Usage

```bash
# Enrichir un fichier CSV
python enrich.py sample_input.csv output.csv

# Format du CSV d'entrée (colonne "siret" obligatoire)
# siret
# 95241832500025
# 82216804300039
```

## Fonctionnalités techniques

- **Parallélisation** : ThreadPoolExecutor (4 workers) — appels API simultanés
- **Retry exponentiel** : backoff sur HTTP 429 (rate limit), jusqu'à 3 tentatives
- **Error handling** : SIRET inconnu → ligne vide (pas d'exception), timeout → log + continue
- **Logging structuré** : `logging` stdlib, pas de print debug
- **Code INSEE Paris** : normalisation automatique arrondissements → commune globale (Géorisques)

## Tests

```bash
pip install pytest pytest-cov
pytest tests/ --cov=enrich --cov-report=term-missing
# 13 passed, couverture 76%
```

## Licence

MIT — voir [LICENSE](LICENSE).

---

*Réponse assistée par IA — conforme EU AI Act Article 50*

**Limier — extraction de données B2B | tomengels.dev**
