"""Importe le référentiel des gares de voyageurs — SNCF, Licence Ouverte.

`app/gares.py` portait 41 gares saisies à la main, « des 5 régions cibles ».
Le catalogue, lui, a débordé ces régions depuis longtemps : mesuré le 15
novembre 2026, 72 % des biens n'avaient AUCUNE gare à moins de 25 km, et les
départements découverts étaient le Nord, la Meurthe-et-Moselle, la
Seine-Maritime, le Calvados, l'Indre-et-Loire — ceux de Lille, Nancy, Rouen,
Caen et Tours. Ce n'était donc pas une absence de desserte, c'était notre
ignorance, et le filtre « gare la plus proche » écartait les biens sur elle.

Avec le référentiel entier, la couverture passe de 28 % à 95 %.

Ce que le référentiel donne, et ce qu'il ne donne pas : la position et le
segment DRG (A, grandes gares nationales ; B, régionales ; C, haltes), mais
AUCUN temps de trajet. Les 41 gares saisies à la main gardent donc leur rôle,
et il reste entier : elles seules disent « Paris en 42 minutes ». Les deux
listes répondent à deux questions distinctes, et `app/gares.py` les tient
séparées plutôt que d'inventer un temps à partir d'une distance — Vendôme est
à 42 min pour 160 km, Creil à 30 min pour 50 : le rapport varie du simple au
triple selon la ligne.

Usage (réseau requis) :
    python scripts/importer_gares.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "gares_sncf.json"

# Export CSV du jeu « Gares de voyageurs » (SNCF, data.gouv.fr).
SOURCE = ("https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets"
          "/gares-de-voyageurs/exports/csv?use_labels=true")
# Repli : data.gouv.fr sert la même ressource et répond quand l'autre tousse.
RELAIS = "https://www.data.gouv.fr/fr/datasets/r/cbacca02-6925-4a46-aab6-7194debbb9b7"


def telecharger(url: str, timeout: int = 120) -> str:
    requete = urllib.request.Request(url, headers={"User-Agent": "refuge-immo/1.0"})
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        return reponse.read().decode("utf-8-sig", "replace")


def lire(texte: str) -> list[dict]:
    """CSV SNCF → gares exploitables, les illisibles simplement écartées."""
    gares = []
    for ligne in csv.DictReader(io.StringIO(texte), delimiter=";"):
        morceaux = (ligne.get("Position géographique") or "").split(",")
        if len(morceaux) != 2:
            continue
        try:
            lat, lon = float(morceaux[0]), float(morceaux[1])
        except ValueError:
            continue
        nom = (ligne.get("Nom_Gare") or "").strip()
        if not nom:
            continue
        # Une gare peut porter plusieurs segments (« A;B ») : on garde le plus
        # élevé, c'est lui qui décrit ce que la gare offre de mieux.
        segments = (ligne.get("Segment(s) DRG") or "").replace(" ", "").split(";")
        segment = min((s for s in segments if s), default="")
        gares.append({"nom": nom, "lat": round(lat, 5), "lon": round(lon, 5),
                      "segment": segment,
                      "commune": (ligne.get("Code commune") or "").strip()})
    gares.sort(key=lambda g: (g["nom"], g["commune"]))
    return gares


def main() -> None:
    texte = ""
    # Deux adresses, trois essais chacune : le transfert fait 265 Ko et se
    # fait couper en route plus souvent qu'il n'échoue vraiment — observé à
    # l'écriture de ce script, où la même requête passait au second essai.
    for url in (SOURCE, RELAIS):
        for essai in range(1, 4):
            try:
                texte = telecharger(url)
                break
            except Exception as erreur:                 # pragma: no cover
                print(f"  échec {essai}/3 sur {url.split('/')[2]} : {erreur}")
                time.sleep(2 * essai)
        if texte:
            break
    if not texte:
        print("Référentiel injoignable — le fichier existant reste en place.")
        sys.exit(1)

    gares = lire(texte)
    # Un garde-fou, et pas un luxe : une réponse tronquée ou une page d'erreur
    # se lirait comme un CSV vide, et écraserait le référentiel par du vide.
    if len(gares) < 2000:
        print(f"Seulement {len(gares)} gares lues — réponse suspecte, rien n'est écrit.")
        sys.exit(1)

    SORTIE.write_text(json.dumps(gares, ensure_ascii=False, indent=0) + "\n",
                      encoding="utf-8")
    par_segment: dict[str, int] = {}
    for g in gares:
        par_segment[g["segment"]] = par_segment.get(g["segment"], 0) + 1
    print(f"{len(gares)} gares écrites dans {SORTIE.relative_to(RACINE)}")
    print(f"  par segment : {dict(sorted(par_segment.items()))}")


if __name__ == "__main__":
    main()
