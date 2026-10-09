"""Rattrape les risques Géorisques des biens déjà publiés (nécessite internet).

L'enrichissement de la collecte (scripts/enrichir_risques.py) ne regarde que
la base du jour, c'est-à-dire les biens que CE passage vient de collecter. Un
bien dont l'enrichissement a échoué ce jour-là n'est jamais retenté : la base
est recréée à chaque passage. Résultat, mesuré le 9 octobre 2026 : 6 139 des
9 396 biens servis — 65 % — n'ont aucune donnée de risque, et la note de
résilience leur donne le maximum du pilier par défaut. Pendant quinze jours
l'API était hors de portée du runner ; le 9 octobre à 17 h, elle a répondu
pour 39 biens.

Ce script lit le fichier publié, prend les biens SERVIS sans risques officiels
— les plus récemment revus d'abord, ceux qui ont le plus de chances d'être
encore en vente — et interroge l'API pour chacun, dans la limite d'un nombre
et d'un temps. Il s'arrête de lui-même après cinq échecs d'affilée : une API
qui ne répond pas ne mérite pas qu'on l'attende. Il récrit le fichier ; c'est
l'export suivant, par `historique.fusionner`, qui porte les risques acquis.

Usage :  python scripts/enrichir_fichier.py [--max N] [--minutes-max M]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement, georisques  # noqa: E402

CATALOGUE = RACINE / "data" / "annonces_reel.json"
ECHECS_D_AFFILEE_MAX = 5


def a_rattraper(biens: list[dict]) -> list[dict]:
    """Les biens servis, géolocalisés, sans risques officiels — les plus
    récemment revus d'abord."""
    servis = chargement.biens_servis(biens)
    ids = {b["id"] for b in servis}
    candidats = [b for b in biens
                 if b.get("id") in ids and b.get("lat") is not None and b.get("lon") is not None
                 and (b.get("risques") or {}).get("source") not in ("georisques", "démo")]
    candidats.sort(key=lambda b: (b.get("revue_le") or "", b.get("vue_le") or ""), reverse=True)
    return candidats


def enrichir(biens: list[dict], maxi: int, minutes_max: float,
             interroger=None, argile=None, dormir=time.sleep) -> tuple[int, int]:
    """Enrichit `biens` en place. Renvoie (réussis, échecs)."""
    interroger = interroger or georisques.risques_pour
    argile = argile or georisques.exposition_argile
    fin_prevue = time.monotonic() + minutes_max * 60
    faits, echecs, d_affilee = 0, 0, 0
    for bien in a_rattraper(biens):
        if faits + echecs >= maxi:
            break
        if time.monotonic() > fin_prevue:
            print("⏱ Budget atteint : on s'arrête là pour ce passage.")
            break
        resultat = interroger(bien["lat"], bien["lon"])
        if resultat is None:
            echecs += 1
            d_affilee += 1
            raison = georisques.DERNIERE_ERREUR or "raison inconnue"
            print(f"✘ {bien.get('commune')}: API injoignable ({raison})")
            if d_affilee >= ECHECS_D_AFFILEE_MAX:
                print(f"⛔ {d_affilee} échecs d'affilée ({raison}) : l'API ne répond pas, "
                      "on n'attend pas les autres.")
                break
            continue
        d_affilee = 0
        resultat["argile"] = argile(bien["lat"], bien["lon"])
        # Les valeurs calculées chez nous — la centrale la plus proche — restent.
        bien["risques"] = {**(bien.get("risques") or {}), **resultat}
        faits += 1
        print(f"✔ {bien.get('commune')}: risques rattrapés")
        dormir(0.4)                      # politesse vis-à-vis de l'API publique
    return faits, echecs


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parseur.add_argument("--max", type=int, default=150)
    parseur.add_argument("--minutes-max", type=float, default=5.0)
    parseur.add_argument("--fichier", type=Path, default=CATALOGUE)
    args = parseur.parse_args()

    biens = json.loads(args.fichier.read_text(encoding="utf-8"))
    restants = len(a_rattraper(biens))
    print(f"{restants} bien(s) servi(s) sans risques officiels à rattraper.")
    faits, echecs = enrichir(biens, args.max, args.minutes_max)
    if faits:
        args.fichier.write_text(json.dumps(biens, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
    print(f"\nTerminé : {faits} bien(s) rattrapé(s), {echecs} échec(s), "
          f"{restants - faits} restant(s).")


if __name__ == "__main__":
    main()
