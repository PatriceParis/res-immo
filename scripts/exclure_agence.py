"""Retirer une agence à sa demande — sans délai, et pour de bon.

Les mentions légales le promettent : « le retrait est effectué sans discussion
et sans délai, et le site est ajouté à une liste d'exclusion pour que la
collecte n'y revienne pas. Aucune justification n'est demandée. » Ce script
est la commande qui tient cette promesse en une fois :

    python scripts/exclure_agence.py agence-exemple.fr
    python scripts/exclure_agence.py https://www.agence-exemple.fr/contact --motif "courriel du 1er octobre"

1. le site entre dans data/agences_exclues.json — les collecteurs ne le
   visitent plus, la découverte ne le rebranche jamais (app/exclusions.py) ;
2. ses biens sortent de data/annonces_reel.json tout de suite, sans attendre
   le prochain export ;
3. il reste à committer et pousser : le site se redéploie en quelques minutes.

Rien n'est poussé par le script : on relit ce qu'il a fait, puis on pousse.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import exclusions  # noqa: E402

CATALOGUE = RACINE / "data" / "annonces_reel.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("site", help="domaine ou adresse du site de l'agence")
    ap.add_argument("--motif", default="demande de l'agence",
                    help="pour mémoire : qui a demandé, quand, par quel canal")
    args = ap.parse_args()

    domaine = exclusions.normaliser(args.site)
    if exclusions.exclure(domaine, args.motif):
        print(f"{domaine} ajouté à {exclusions.FICHIER.relative_to(RACINE)}")
    else:
        print(f"{domaine} y figurait déjà")

    retires = 0
    if CATALOGUE.exists():
        retires = exclusions.retirer_du_catalogue(CATALOGUE, exclusions.domaines_exclus())
    print(f"{retires} annonce(s) retirée(s) de {CATALOGUE.relative_to(RACINE)}")
    print("\nReste à publier :\n"
          f"  git add {exclusions.FICHIER.relative_to(RACINE)} {CATALOGUE.relative_to(RACINE)}\n"
          f"  git commit -m \"Retrait de {domaine} à sa demande\" && git push")


if __name__ == "__main__":
    main()
