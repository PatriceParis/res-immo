"""Exporte les annonces RÉELLES (hors démo) de la base vers data/annonces_reel.json.

L'application charge ce fichier au démarrage (y compris sur Vercel), en plus du
jeu de démonstration. C'est l'étape finale de la collecte automatisée
(voir .github/workflows/collecte.yml) : collecter → exporter → committer.

Usage :  python scripts/exporter_reel.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db  # noqa: E402

# Champs « bruts » réinjectés dans l'app (elle recalcule score, features, distance).
# `risques` vient de Géorisques : on le conserve, l'app ne saurait pas le refaire
# sans réseau. Le train, lui, est recalculé au chargement (table locale des gares).
CHAMPS = [
    "id", "source", "url", "titre", "description", "type_bien", "prix",
    "surface_m2", "terrain_m2", "pieces", "commune", "code_postal",
    "departement", "region", "agence", "agence_url", "photo", "texte",
    "lat", "lon", "altitude", "densite_hab_km2", "dpe", "risques",
]


def _bien(row) -> dict:
    """Une ligne de base → dict exportable.

    `_row_vers_dict` décode les colonnes JSON (risques_json → risques) mais
    **retire `texte`**, réservé à l'usage interne de l'API. Or c'est ce texte
    qui permet de détecter cave, puits, poêle… au rechargement : on le remet
    depuis la ligne brute, sinon le scoring repart d'une description de
    quelques lignes et tous les critères disparaissent.
    """
    bien = db._row_vers_dict(row)
    bien["texte"] = dict(row).get("texte") or ""
    return {cle: bien.get(cle) for cle in CHAMPS}


def main() -> None:
    conn = db.connexion()
    rows = conn.execute(
        "SELECT * FROM annonces WHERE source IS NOT NULL AND source <> 'démo' "
        "ORDER BY score_total DESC"
    ).fetchall()
    biens = [_bien(r) for r in rows]
    conn.close()

    sortie = RACINE / "data" / "annonces_reel.json"
    sortie.parent.mkdir(exist_ok=True)
    sortie.write_text(json.dumps(biens, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(biens)} annonce(s) réelle(s) exportée(s) vers {sortie}")


if __name__ == "__main__":
    main()
