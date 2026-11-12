"""Convertit des extractions DRIAS « Indicateurs TRACC-2023 » en
data/climat_2050.json, que lit app/climat.py.

Usage :
    python scripts/importer_drias.py FICHIER.txt [FICHIER.txt ...] [--sortie CHEMIN]

Le portail DRIAS (Espace Données et Produits, « Indicateurs annuels
TRACC-2023 moyennés par niveau de réchauffement ») livre, pour UN modèle
climatique et UN niveau de réchauffement, un fichier texte de cette forme,
relevé sur une vraie extraction le 12 novembre 2026 :

    # Modele     : CCLM4-8-17_MPI-ESM
    #     GWL20 (2052-2071) : Niveau de réchauffement Monde 2.0 degrés -> 2050 / France +2.7°C
    # Point;Latitude;Longitude;Niveau;Annee;TMm_yr;...;TX35D_yr;...;ECARTSWI04_yr;...;
    139;41.3373;9.1495;GWL20;2052;16.71;...;

Une ligne par point de la grille SAFRAN (8 981 points) et par année de la
fenêtre de réchauffement (20 ans). On en tire, point par point :

- la valeur vers 2050 : moyenne des 20 années du niveau GWL20 ;
- la valeur de référence (1976-2005) : celle d'une extraction « Période de
  référence » si on en donne une, sinon horizon moins écart quand le fichier
  porte la colonne d'écart (ECART…), sinon rien ;
- avec plusieurs modèles, la MÉDIANE des modèles, comme le fait la TRACC.

Le meilleur produit est la médiane déjà calculée par Météo-France :
« Quantiles des indicateurs annuels TRACC-2023 moyennés par niveau de
réchauffement », modèle « Q50 ». Une ligne par point, sans colonne Annee,
des colonnes NORTX35D_yr (valeur) et ATX35D_yr (écart à la référence) —
écarts compris pour les jours de chaleur, que l'extraction d'un modèle seul
ne donnait pas. Quand ce fichier est fourni, il fait foi seul.

Seuls les points à moins de RAYON_KM de Paris sont gardés : le site ne sert
que des biens à moins de 350 km, et un bien prend la maille la plus proche
à 10 km au plus.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "climat_2050.json"
PARIS = (48.8530, 2.3499)
RAYON_KM = 365

# Code de app/climat.py -> (colonnes de la valeur, colonnes de l'écart à la
# référence, écart relatif ?). Deux écritures selon le produit DRIAS : un
# modèle seul (« TX35D_yr », « ECARTTX35D_yr ») ou la distribution des 17
# modèles (« NORTX35D_yr », « ATX35D_yr »), relevées sur deux extractions
# réelles du 12 novembre 2026.
COLONNES = {
    "tmm": (("TMm_yr", "NORTMm_yr"), ("ECARTTMm_yr", "ATMm_yr"), False),
    "txm_jja": (("TXm_seas_JJA", "NORTXm_seas_JJA"), ("ECARTTXm_seas_JJA", "ATXm_seas_JJA"), False),
    "tx35d": (("TX35D_yr", "NORTX35D_yr"), ("ECARTTX35D_yr", "ATX35D_yr"), False),
    "tx30d": (("TX30D_yr", "NORTX30D_yr"), ("ECARTTX30D_yr", "ATX30D_yr"), False),
    "tr": (("TR_yr", "NORTR_yr"), ("ECARTTR_yr", "ATR_yr"), False),
    "rr_jja": (("RR_seas_JJA", "NORRR_seas_JJA"), ("ECARTRELRR_seas_JJA", "ARRR_seas_JJA"), True),
    "swi04d": (("SWI04_yr", "NORSWI04_yr"), ("ECARTSWI04_yr", "ASWI04_yr"), False),
    "ifm40d": (("IFM40_yr", "NORIFM40_yr"), ("ECARTIFM40_yr", "AIFM40_yr"), False),
}
# La médiane des 17 modèles, calculée par Météo-France (« Quantiles des
# indicateurs annuels TRACC-2023 », modèle « Q50 »). Quand on la donne, elle
# fait foi seule : la mêler à des modèles isolés fausserait la médiane.
MEDIANE = "Q50"
NIVEAU_2050 = "GWL20"


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    x = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    return 6371 * math.hypot(x, math.radians(b[0] - a[0]))


def lire(chemin: Path) -> dict:
    """Un fichier DRIAS : modèle, et par niveau puis par point, la moyenne
    de chaque colonne sur les années présentes."""
    modele, entete = None, None
    sommes = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    nombres = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    positions: dict[str, tuple[float, float]] = {}
    with open(chemin, encoding="utf-8", errors="replace") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()
            if not ligne:
                continue
            if ligne.startswith("#"):
                trouve = re.match(r"#\s*Mod[eè]le\s*:\s*(\S+)", ligne)
                if trouve:
                    modele = trouve.group(1)
                if re.match(r"#\s*Point;", ligne):
                    entete = [c.strip() for c in ligne.lstrip("#").strip().split(";")]
                continue
            if entete is None:
                raise ValueError(f"{chemin} : pas de ligne d'en-tête « # Point;… »")
            champs = ligne.split(";")
            rangee = dict(zip(entete, champs))
            point, niveau = rangee.get("Point"), rangee.get("Niveau")
            try:
                positions[point] = (float(rangee["Latitude"]), float(rangee["Longitude"]))
            except (KeyError, TypeError, ValueError):
                continue
            for colonne, texte in rangee.items():
                if colonne in ("Point", "Latitude", "Longitude", "Niveau", "Annee", ""):
                    continue
                try:
                    valeur = float(texte)
                except (TypeError, ValueError):
                    continue
                if math.isnan(valeur):
                    continue
                sommes[niveau][point][colonne] += valeur
                nombres[niveau][point][colonne] += 1
    moyennes = {
        niveau: {point: {c: sommes[niveau][point][c] / nombres[niveau][point][c]
                         for c in sommes[niveau][point]}
                 for point in sommes[niveau]}
        for niveau in sommes}
    return {"modele": modele or Path(chemin).stem, "positions": positions, "niveaux": moyennes}


def _arrondi(valeur):
    return None if valeur is None else round(valeur, 1)


def convertir(chemins: list[Path], centre=PARIS, rayon_km: float = RAYON_KM) -> dict:
    fichiers = [lire(Path(c)) for c in chemins]
    fichiers = [f for f in fichiers if f["modele"] == MEDIANE] or fichiers
    modeles = sorted({f["modele"] for f in fichiers})
    positions = {}
    for f in fichiers:
        positions.update(f["positions"])
    # Par point et par code : les valeurs 2050 et de référence de chaque modèle.
    horizon = defaultdict(lambda: defaultdict(list))
    reference = defaultdict(lambda: defaultdict(list))
    for f in fichiers:
        futurs = f["niveaux"].get(NIVEAU_2050, {})
        refs = {n: v for n, v in f["niveaux"].items() if not n.upper().startswith("GWL")}
        refs = next(iter(refs.values()), {})
        for point, colonnes in futurs.items():
            for code, (absolues, ecarts, relatif) in COLONNES.items():
                valeur = next((colonnes[c] for c in absolues if c in colonnes), None)
                if valeur is None:
                    continue
                horizon[point][code].append(valeur)
                ecart = next((colonnes[c] for c in ecarts if c in colonnes), None)
                if ecart is None:
                    continue
                if not relatif:
                    reference[point][code].append(valeur - ecart)
                elif ecart > -1:
                    reference[point][code].append(valeur / (1 + ecart))
        for point, colonnes in refs.items():
            for code, (absolues, _, _) in COLONNES.items():
                valeur = next((colonnes[c] for c in absolues if c in colonnes), None)
                if valeur is not None:
                    reference[point][code].append(valeur)
    points = []
    for point in sorted(horizon, key=lambda p: positions.get(p, (0, 0))):
        if point not in positions or _km(centre, positions[point]) > rayon_km:
            continue
        valeurs = {}
        for code in COLONNES:
            futurs = horizon[point].get(code)
            if not futurs:
                continue
            refs = reference[point].get(code)
            valeurs[code] = [_arrondi(statistics.median(refs)) if refs else None,
                             _arrondi(statistics.median(futurs))]
        if valeurs:
            lat, lon = positions[point]
            points.append([round(lat, 4), round(lon, 4), valeurs])
    noms = ", ".join(m.replace("_", " / ") for m in modeles)
    if modeles == [MEDIANE]:
        avertissement = ("Médiane des 17 modèles climatiques de la trajectoire, calculée par "
                         "Météo-France : une moitié des modèles voit plus, l'autre moins.")
    elif len(modeles) == 1:
        avertissement = (f"D'après un seul modèle climatique ({noms}) parmi les 17 de la "
                         "trajectoire : un ordre de grandeur, pas une prévision.")
    else:
        avertissement = (f"Médiane de {len(modeles)} modèles climatiques sur les 17 de la "
                         f"trajectoire ({noms}).")
    return {
        "source": "DRIAS (Météo-France), indicateurs TRACC-2023",
        "horizon": "2050",
        "reference": "1976-2005",
        "avertissement": avertissement,
        "modeles": modeles,
        "points": points,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fichiers", nargs="+", type=Path)
    parser.add_argument("--sortie", type=Path, default=SORTIE)
    args = parser.parse_args(argv)
    resultat = convertir(args.fichiers)
    args.sortie.write_text(json.dumps(resultat, ensure_ascii=False, separators=(",", ":")),
                           encoding="utf-8")
    print(f"{len(resultat['points'])} points, {len(resultat['modeles'])} modèle(s) "
          f"-> {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
