"""Le climat de 2050 autour d'un bien : projections DRIAS de Météo-France.

Demandé le 12 novembre 2026 : savoir, commune par commune, combien de
journées caniculaires et de jours de sol sec attendre vers 2050. La
référence française est le portail DRIAS, et l'horizon celui de la
trajectoire nationale d'adaptation (TRACC) : +2,7 °C en France en 2050.

Les indicateurs DRIAS sont calculés sur la grille SAFRAN, des mailles de
8 km. Un bien est donc rattaché au point de grille le plus proche de sa
position — qui est celle de sa COMMUNE, l'adresse n'étant presque jamais
publiée (voir pages._carte_aerienne). À 8 km près, c'est le climat de la
commune que l'on décrit, et la fiche le dit.

Les valeurs vivent dans data/climat_2050.json, sous cette forme :

    {"source": "...", "horizon": "...", "reference": "1976-2005",
     "points": [[lat, lon, {"tx35d": [reference, horizon], ...}], ...]}

Le fichier est construit à partir d'un export DRIAS. Absent ou illisible,
aucune fiche n'affiche de climat : un chiffre manquant vaut mieux qu'un
chiffre inventé.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

FICHIER = Path(__file__).resolve().parent.parent / "data" / "climat_2050.json"

# Une maille SAFRAN mesure 8 km de côté : un bien en est au plus à 5,7 km du
# centre. Au-delà de 10 km, le point le plus proche est celui d'une autre
# commune, voire d'un autre pays : on se tait.
DISTANCE_MAX_KM = 10

# Ce que la fiche montre, dans cet ordre. Un indicateur absent du fichier
# est simplement omis.
# Les codes sont ceux des indicateurs TRACC du portail DRIAS (TX35D, TX30D,
# TR, SWI04D, IFM40D), en minuscules.
INDICATEURS = (
    ("chaleur", "tx35d", "Journées au-delà de 35 °C", "par an"),
    ("chaleur", "tx30d", "Journées au-delà de 30 °C", "par an"),
    ("chaleur", "tr", "Nuits à plus de 20 °C", "par an"),
    ("secheresse", "swi04d", "Jours de sol sec", "par an"),
    ("secheresse", "ifm40d", "Jours à fort risque de feu de forêt", "par an"),
)


def _lire(chemin: Path) -> dict | None:
    try:
        donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(donnees, dict) or not isinstance(donnees.get("points"), list):
        return None
    return donnees


@lru_cache(maxsize=4)
def _grille(chemin: str) -> dict | None:
    return _lire(Path(chemin))


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance approchée, largement assez juste à l'échelle d'une maille."""
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371 * math.hypot(x, y)


def au_point(lat, lon, chemin: Path | str | None = None) -> dict | None:
    """Les indicateurs de la maille la plus proche, ou None.

    None si le bien n'est pas géolocalisé, si le fichier manque, ou si aucun
    point ne tombe à moins de DISTANCE_MAX_KM.
    """
    if lat is None or lon is None:
        return None
    grille = _grille(str(chemin or FICHIER))
    if not grille:
        return None
    meilleur, distance = None, DISTANCE_MAX_KM
    for point in grille["points"]:
        try:
            d = _km(lat, lon, point[0], point[1])
        except (TypeError, IndexError):
            continue
        if d <= distance:
            meilleur, distance = point, d
    if meilleur is None:
        return None
    valeurs = meilleur[2] if len(meilleur) > 2 and isinstance(meilleur[2], dict) else {}
    indicateurs = []
    for theme, code, libelle, unite in INDICATEURS:
        paire = valeurs.get(code)
        if not isinstance(paire, (list, tuple)) or len(paire) != 2 or None in paire:
            continue
        indicateurs.append({"theme": theme, "code": code, "libelle": libelle, "unite": unite,
                            "reference": paire[0], "horizon": paire[1]})
    if not indicateurs:
        return None
    return {"source": grille.get("source") or "DRIAS, Météo-France",
            "horizon": grille.get("horizon") or "2050",
            "reference": grille.get("reference") or "1976-2005",
            "distance_km": round(distance, 1),
            "indicateurs": indicateurs}


def _nombre(valeur) -> str:
    arrondi = round(float(valeur))
    return str(arrondi) if arrondi or float(valeur) == 0 else "moins de 1"


def phrases(climat: dict | None) -> list[str]:
    """« Journées au-delà de 35 °C : 2 par an sur la période 1976-2005,
    9 vers 2050. »"""
    if not climat:
        return []
    return [f"{i['libelle']} : {_nombre(i['reference'])} {i['unite']} sur la période "
            f"{climat['reference']}, {_nombre(i['horizon'])} vers {climat['horizon']}."
            for i in climat["indicateurs"]]
