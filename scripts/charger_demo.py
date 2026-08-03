"""Charge le jeu de démonstration dans la base locale (data/refuge.db).

Usage :  python scripts/charger_demo.py [--remplacer]
  --remplacer : vide d'abord les annonces « démo » existantes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db  # noqa: E402
from app.chargement import charger_annonces_json  # noqa: E402


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--fichier", default=RACINE / "data" / "annonces_demo.json")
    parseur.add_argument("--remplacer", action="store_true")
    args = parseur.parse_args()

    conn = db.connexion()
    if args.remplacer:
        conn.execute("DELETE FROM annonces WHERE source = 'démo'")
    n = charger_annonces_json(conn, args.fichier)
    print(f"✔ {n} annonces chargées dans {db.chemin_db()}")

    meilleurs = conn.execute(
        "SELECT score_total, titre FROM annonces ORDER BY score_total DESC LIMIT 5"
    ).fetchall()
    print("\nMeilleurs scores de résilience :")
    for score, titre in meilleurs:
        print(f"  {score:>3.0f}/100  {titre}")
    conn.close()


if __name__ == "__main__":
    main()
