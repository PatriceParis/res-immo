"""Vérifie que les liens du catalogue mènent encore à leur annonce.

Chaque fiche promet « voir l'annonce d'origine ». Quand le bien est vendu,
beaucoup de sites suppriment ou redirigent la page — et la règle de sortie ne
peut pas s'en apercevoir sur les gros départements, tronqués à chaque passage
(voir app/liens.py). Ce passage-ci regarde le lien lui-même.

Rotation : les suspects d'abord (un constat de mort attend sa confirmation),
puis les plus anciennement vérifiés. Chaque URL est notée dans
data/liens_verifies.json ; les constats de mort dans data/liens_morts.json —
au deuxième, l'export retire l'annonce.

Usage :
    python scripts/verifier_liens.py                    # un lot, en rotation
    python scripts/verifier_liens.py --cibles r1949496  # vérifier une annonce
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import liens  # noqa: E402

REEL = RACINE / "data" / "annonces_reel.json"
JOURNAL_MORTS = RACINE / "data" / "liens_morts.json"
JOURNAL_VERIFIES = RACINE / "data" / "liens_verifies.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def _charger(chemin: Path) -> dict:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ecrire(chemin: Path, donnees: dict) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1,
                                 sort_keys=True) + "\n", encoding="utf-8")


def observer(url: str, timeout: int = 12) -> tuple[int, str, str]:
    """(statut, url finale, texte) — ce que le réseau répond, brut."""
    requete = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            corps = reponse.read(2_000_000)
            return reponse.status, reponse.geturl(), corps.decode("utf-8", "replace")
    except urllib.error.HTTPError as erreur:
        return erreur.code, url, ""
    except Exception:
        # Réseau injoignable ou délai : on ne conclut RIEN. Une panne de
        # notre côté ne doit pas compter comme une mort du leur.
        return 0, url, ""


def main() -> None:
    parametres = argparse.ArgumentParser(description=__doc__)
    parametres.add_argument("--max", type=int, default=150,
                            help="liens vérifiés par passage")
    parametres.add_argument("--delai", type=float, default=1.0,
                            help="secondes entre deux requêtes")
    parametres.add_argument("--minutes", type=float, default=15,
                            help="budget de temps total")
    parametres.add_argument("--cibles", default="",
                            help="ne vérifier que les URL contenant ce texte")
    args = parametres.parse_args()

    biens = json.loads(REEL.read_text(encoding="utf-8"))
    urls_du_fichier = {b.get("url") for b in biens if b.get("url")}
    morts = liens.nettoyer(_charger(JOURNAL_MORTS), urls_du_fichier)
    verifies = {u: j for u, j in _charger(JOURNAL_VERIFIES).items()
                if u in urls_du_fichier}

    candidats = liens.ordre_de_verification(biens, verifies, morts)
    if args.cibles:
        candidats = [b for b in candidats if args.cibles in b["url"]]
    lot = candidats[:args.max]
    print(f"{len(lot)} lien(s) à vérifier sur {len(urls_du_fichier)}"
          f" ({len(morts)} suspect(s) au journal)")

    aujourd_hui = date.today().isoformat()
    fin = time.monotonic() + args.minutes * 60
    vivants = suspects = injoignables = 0
    for bien in lot:
        if time.monotonic() > fin:
            print("  budget de temps atteint — la suite au prochain passage.")
            break
        url = bien["url"]
        statut, url_finale, texte = observer(url)
        time.sleep(args.delai)
        if statut == 0:
            injoignables += 1     # notre panne, pas la leur : aucun constat
            continue
        etat, motif = liens.verdict(statut, url, url_finale, texte)
        liens.noter(morts, url, etat, aujourd_hui, motif)
        verifies[url] = aujourd_hui
        if etat == "vivant":
            vivants += 1
        else:
            suspects += 1
            constat = morts[url]
            print(f"  ✘ {etat} ({motif}) — constat {constat['constats']}"
                  f"/{liens.CONSTATS_REQUIS} : {url[-80:]}")

    confirmes = liens.morts_confirmes(morts)
    print(f"\nvivants : {vivants} · constats de mort : {suspects} · "
          f"injoignables (non comptés) : {injoignables}")
    print(f"retraits confirmés en attente d'export : {len(confirmes)}")
    _ecrire(JOURNAL_MORTS, morts)
    _ecrire(JOURNAL_VERIFIES, verifies)


if __name__ == "__main__":
    main()
