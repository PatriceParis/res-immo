# Refuge Immo — notes pour le développement

POC de recherche immobilière « résilience climatique » autour de Paris.
Public cible : utilisateur non technique — garder les messages, l'interface
et la documentation en français simple, et le démarrage en un clic.

## Commandes

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-local.txt   # requirements.txt = serveur seul (Vercel)
python scripts/generer_demo.py      # régénère data/annonces_demo.json (seed fixe)
python scripts/charger_demo.py      # (re)charge la base + recalcule les scores
python -m pytest tests/ -q          # 14 tests
python -m uvicorn app.main:app      # http://localhost:8000
bash scripts/collecter.sh pap       # robot Scrapy (réseau requis)
python scripts/enrichir_risques.py  # API Géorisques (réseau requis)
```

## Architecture

- `app/scoring.py` — cœur métier : détection de mots-clés (`MOTIFS`) +
  barème 6 piliers = 100 pts (`_pilier_*`). Toute modification du barème
  impose de recharger les annonces pour recalculer les scores stockés.
- `app/chargement.py` — enrichissement commun à toutes les sources
  (démo + robots) : géo, features, centrale nucléaire, score, drapeaux
  `has_*` pour les filtres SQL.
- `app/db.py` — SQLite, schéma auto-créé, `chercher()` construit le SQL
  filtré (liste blanche `TRIS` pour le tri).
- `app/main.py` — FastAPI ; charge la démo au démarrage si la base est vide ;
  sert `app/static/` (interface vanilla JS + Leaflet vendorisé dans
  `app/static/vendor/`, pas de CDN).
- `app/extraction.py` — extracteur schema.org (JSON-LD) + OpenGraph + repères
  texte : HTML d'une page d'agence → annonce brute. Sans dépendance, testé
  hors-ligne (`tests/test_extraction.py`). Réutilisé par le robot `agence`.
- `scraper/` — Scrapy poli (robots.txt, 1 req/2,5 s, UA honnête). Robots :
  `agence` (générique, sitemap + `app.extraction`, lit `agences.json`) =
  stratégie principale (voir docs/STRATEGIE_COLLECTE.md) ; `bienici` (API
  JSON) ; `pap`/`iep` (héritent de `spiders/base.py`, parsing heuristique).
  Découverte d'agences : `scripts/decouvrir_agences.py`. Pipeline → géocodage
  BAN (si pas de GPS) → `preparer_annonce()` → même base SQLite.
- Attribution agence : colonnes `agence`/`agence_url` (migration auto dans
  `db.connexion`), endpoint `/api/agences`, filtre `agence`, affichage
  « 🏢 via l'agence » + lien « voir chez l'agence » dans la fiche.
- Base de données : `data/refuge.db` (gitignorée), surchargeable via
  la variable d'environnement `REFUGE_DB` (utilisée par les tests).

## Contraintes

- Pas de scraping des grands portails (CGU + anti-bot) : voir docs/LEGAL.md
  avant d'ajouter une source.
- Temps de route = estimation haversine × 1,25 (app/geo.py) — assumé.
- Palette de score (app/static/style.css `--n1…--n4`) validée
  daltonisme/contraste : garder le chiffre à côté de la couleur.
