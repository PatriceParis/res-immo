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

from datetime import date  # noqa: E402

from app import db, historique  # noqa: E402

# Champs « bruts » réinjectés dans l'app (elle recalcule score, features, distance).
# `risques` vient de Géorisques : on le conserve, l'app ne saurait pas le refaire
# sans réseau. Le train, lui, est recalculé au chargement (table locale des gares).
CHAMPS = [
    "id", "source", "url", "titre", "description", "type_bien", "prix",
    "surface_m2", "terrain_m2", "pieces", "commune", "code_postal",
    "departement", "region", "agence", "agence_url", "photo", "texte",
    "lat", "lon", "altitude", "densite_hab_km2", "dpe", "risques",
    # Mémoire d'une collecte à l'autre (voir app/historique.py) : c'est ce
    # fichier, versionné, qui traverse le temps — pas la base, recréée à
    # chaque exécution.
    "vue_le", "revue_le", "absences", "prix_precedent", "prix_baisse_le",
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

    # On reporte l'historique du fichier précédent : date de première vue,
    # baisses de prix, et retrait des annonces que l'agence a enlevées.
    precedentes = []
    if sortie.exists():
        try:
            precedentes = json.loads(sortie.read_text(encoding="utf-8"))
        except ValueError:
            precedentes = []
    # Seules les agences réellement parcourues cette fois font autorité : une
    # collecte écourtée ne doit pas faire disparaître les biens des autres.
    visitees = {b.get("agence") for b in biens if b.get("agence")}
    fusionnees = historique.fusionner(precedentes, biens, visitees,
                                      date.today().isoformat())

    # Ordre STABLE, par identifiant. Le fichier est committé six fois par jour
    # et pèse un méga-octet : sans ordre fixe, chaque export réécrit tout et
    # git stocke une copie entière à chaque fois — plus de deux gigaoctets par
    # an pour un catalogue qui bouge à la marge. Trié, seules les lignes des
    # biens réellement modifiés changent, et le dépôt ne grossit que de ce
    # qui a bougé.
    fusionnees.sort(key=lambda b: b.get("id") or "")
    sortie.write_text(json.dumps(fusionnees, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    nouveaux = sum(1 for b in fusionnees if b.get("vue_le") == date.today().isoformat()
                   and b.get("revue_le") == date.today().isoformat()
                   and b.get("id") in {x.get("id") for x in biens}
                   and b.get("id") not in {x.get("id") for x in precedentes})
    baisses = sum(1 for b in fusionnees
                  if b.get("prix_baisse_le") == date.today().isoformat())
    retirees = len(precedentes) + len(biens) - len(fusionnees) - (len(biens) - nouveaux)
    print(f"{len(fusionnees)} annonce(s) exportée(s) vers {sortie}")
    print(f"  dont {nouveaux} nouvelle(s), {baisses} baisse(s) de prix, "
          f"{max(retirees, 0)} retirée(s) par l'agence")


if __name__ == "__main__":
    main()
