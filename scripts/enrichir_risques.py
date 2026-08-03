"""Enrichit les annonces avec les risques officiels Géorisques (nécessite internet).

Interroge l'API publique de l'État pour chaque annonce géolocalisée dont les
risques ne sont pas encore renseignés, puis recalcule le score.

Usage :  python scripts/enrichir_risques.py [--forcer] [--max N]
  --forcer : ré-interroge aussi les annonces déjà renseignées (y compris démo)
  --max N  : limite le nombre d'appels (politesse / tests)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db, georisques, scoring  # noqa: E402


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--forcer", action="store_true")
    parseur.add_argument("--max", type=int, default=200)
    args = parseur.parse_args()

    conn = db.connexion()
    rows = conn.execute(
        "SELECT * FROM annonces WHERE lat IS NOT NULL AND lon IS NOT NULL"
    ).fetchall()

    faits, echecs = 0, 0
    for row in rows:
        if faits + echecs >= args.max:
            break
        annonce = db._row_vers_dict(row)
        risques = annonce.get("risques") or {}
        if not args.forcer and risques.get("source") in ("georisques", "démo"):
            continue

        resultat = georisques.risques_pour(annonce["lat"], annonce["lon"])
        if resultat is None:
            echecs += 1
            print(f"✘ {annonce['commune']}: API injoignable")
            continue

        # On conserve la distance à la centrale déjà calculée localement.
        resultat["nucleaire_km"] = risques.get("nucleaire_km")
        resultat["nucleaire_nom"] = risques.get("nucleaire_nom")
        annonce["risques"] = resultat
        detail = scoring.calculer_score(annonce)

        conn.execute(
            """UPDATE annonces SET risques_json = ?, score_total = ?,
               score_detail_json = ?, badges_json = ?, alertes_json = ?,
               hors_inondation = ? WHERE id = ?""",
            (
                json.dumps(resultat, ensure_ascii=False),
                detail["total"],
                json.dumps(detail, ensure_ascii=False),
                json.dumps(detail["badges"], ensure_ascii=False),
                json.dumps(detail["alertes"], ensure_ascii=False),
                0 if resultat.get("inondation") else 1,
                annonce["id"],
            ),
        )
        faits += 1
        print(f"✔ {annonce['commune']}: risques mis à jour (score {detail['total']})")
        time.sleep(1)  # politesse vis-à-vis de l'API publique

    conn.commit()
    conn.close()
    print(f"\nTerminé : {faits} annonce(s) enrichie(s), {echecs} échec(s).")


if __name__ == "__main__":
    main()
