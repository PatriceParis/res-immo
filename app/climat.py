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

Les valeurs vivent dans data/climat_2050.json, construit par
scripts/importer_drias.py à partir d'une extraction DRIAS :

    {"source": "...", "horizon": "2050", "reference": "1976-2005",
     "avertissement": "...",
     "points": [[lat, lon, {"tx35d": [reference, horizon], ...}], ...]}

La référence vaut null quand l'extraction ne la fournit pas : la fiche
donne alors la seule valeur de 2050. Fichier absent ou illisible : aucune
fiche n'affiche de climat — un chiffre manquant vaut mieux qu'un chiffre
inventé.
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

# Ce que la fiche montre, dans cet ordre : (thème, code, libellé, unité,
# décimales). Les codes sont ceux des indicateurs TRACC du portail DRIAS
# (TMm, TXm été, TX35D, TX30D, TR, SWI04, IFM40), en minuscules. Un
# indicateur absent du fichier est simplement omis.
INDICATEURS = (
    ("chaleur", "tmm", "Température moyenne annuelle", "°C", 1),
    ("chaleur", "txm_jja", "Température maximale moyenne en été", "°C", 1),
    ("chaleur", "tx35d", "Journées au-delà de 35 °C", "par an", 0),
    ("chaleur", "tx30d", "Journées au-delà de 30 °C", "par an", 0),
    ("chaleur", "tr", "Nuits à plus de 20 °C", "par an", 0),
    ("secheresse", "rr_jja", "Pluie en été (juin à août)", "mm", 0),
    ("secheresse", "swi04d", "Jours de sol sec", "par an", 0),
    ("secheresse", "ifm40d", "Jours à fort risque de feu de forêt", "par an", 0),
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


# Pour la pluie d'été, c'est la BAISSE qui inquiète ; pour tout le reste, la
# hausse.
BAISSE_INQUIETANTE = {"rr_jja"}


@lru_cache(maxsize=4)
def _reperes(chemin: str) -> dict:
    """Par indicateur : les valeurs de 2050 de toutes les mailles de la zone,
    triées, et l'échelle commune des barres (la plus haute valeur, référence
    comprise). Une échelle commune à la zone, et non propre à chaque fiche :
    deux maisons se comparent d'un coup d'œil."""
    grille = _grille(chemin) or {}
    valeurs: dict[str, list[float]] = {}
    echelles: dict[str, float] = {}
    for point in grille.get("points", []):
        if len(point) < 3 or not isinstance(point[2], dict):
            continue
        for code, paire in point[2].items():
            if not isinstance(paire, (list, tuple)) or len(paire) != 2 or paire[1] is None:
                continue
            valeurs.setdefault(code, []).append(float(paire[1]))
            echelles[code] = max(echelles.get(code, 0.0),
                                 *(float(v) for v in paire if v is not None))
    return {code: {"tries": sorted(v), "echelle": echelles.get(code) or 1.0}
            for code, v in valeurs.items()}


def _centile(tries: list[float], valeur: float, baisse: bool) -> tuple[int, int]:
    """(part des mailles de la zone moins exposées que celle-ci, part des
    plus exposées), en %. Les ex æquo ne sont ni l'un ni l'autre."""
    import bisect
    if not tries:
        return 0, 0
    dessous = bisect.bisect_left(tries, valeur)
    dessus = len(tries) - bisect.bisect_right(tries, valeur)
    if baisse:   # moins de pluie = plus exposé
        dessous, dessus = dessus, dessous
    return round(100 * dessous / len(tries)), round(100 * dessus / len(tries))


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
    reperes = _reperes(str(chemin or FICHIER))
    indicateurs = []
    for theme, code, libelle, unite, decimales in INDICATEURS:
        paire = valeurs.get(code)
        if not isinstance(paire, (list, tuple)) or len(paire) != 2 or paire[1] is None:
            continue
        reference, horizon = paire
        baisse = code in BAISSE_INQUIETANTE
        repere = reperes.get(code, {})
        indicateurs.append({
            "theme": theme, "code": code, "libelle": libelle, "unite": unite,
            "decimales": decimales, "reference": reference, "horizon": horizon,
            "ecart": None if reference is None else round(horizon - reference, 1),
            "baisse_inquietante": baisse,
            "echelle": repere.get("echelle") or max(horizon, reference or 0, 1),
            # Les températures moyennes ne se classent pas : elles suivent la
            # latitude, et la fiche dit déjà l'écart.
            "centile": (None if unite == "°C"
                        else _centile(repere.get("tries", []), horizon, baisse)),
        })
    if not indicateurs:
        return None
    return {"source": grille.get("source") or "DRIAS, Météo-France",
            "horizon": grille.get("horizon") or "2050",
            "reference": grille.get("reference") or "1976-2005",
            "avertissement": grille.get("avertissement") or "",
            "distance_km": round(distance, 1),
            "indicateurs": indicateurs}


def _nombre(valeur, decimales: int = 0) -> str:
    valeur = float(valeur)
    if decimales:
        return f"{valeur:.{decimales}f}".replace(".", ",")
    arrondi = round(valeur)
    return str(arrondi) if arrondi or valeur == 0 else "moins de 1"


def phrases(climat: dict | None) -> list[str]:
    """« Jours de sol sec : 41 par an sur la période 1976-2005, 63 vers
    2050. », ou « Journées au-delà de 35 °C : 3 par an vers 2050. » quand la
    référence manque."""
    if not climat:
        return []
    lignes = []
    for i in climat["indicateurs"]:
        futur = f"{_nombre(i['horizon'], i['decimales'])} {i['unite']}"
        if i["reference"] is None:
            lignes.append(f"{i['libelle']} : {futur} vers {climat['horizon']}.")
        else:
            lignes.append(f"{i['libelle']} : {_nombre(i['reference'], i['decimales'])} "
                          f"{i['unite']} sur la période {climat['reference']}, "
                          f"{futur} vers {climat['horizon']}.")
    return lignes


# ---------------------------------------------------------------- affichage

THEMES = (("chaleur", "Chaleur", "🌡️"), ("secheresse", "Sécheresse", "💧"))


def _signe(valeur: float, decimales: int) -> str:
    texte = _nombre(abs(valeur), decimales) if decimales else str(round(abs(valeur)))
    return ("+" if valeur > 0 else "−" if valeur < 0 else "±") + texte


def _ecart(i: dict) -> tuple[str, str]:
    """(écart lisible, sens) — sens « pire », « mieux » ou « stable »."""
    if i["ecart"] is None:
        return "", "stable"
    if i["unite"] == "mm":
        relatif = 100 * i["ecart"] / i["reference"] if i["reference"] else 0
        texte, valeur = f"{_signe(relatif, 0)} %", relatif
        seuil = 2
    # L'écart se calcule sur les valeurs AFFICHÉES : « 1 → 6 » doit dire +5,
    # pas le +4 qu'arrondirait l'écart brut de 4,5.
    elif i["unite"] == "°C":
        valeur = round(round(i["horizon"], 1) - round(i["reference"], 1), 1)
        texte, seuil = f"{_signe(valeur, 1)} °C", 0.05
    else:
        valeur = round(i["horizon"]) - round(i["reference"])
        texte, seuil = f"{_signe(valeur, 0)} j", 0.5
    if abs(valeur) < seuil:
        return texte, "stable"
    pire = valeur < 0 if i["baisse_inquietante"] else valeur > 0
    return texte, "pire" if pire else "mieux"


def _rang(i: dict) -> str:
    """La maille parmi celles de la zone, dans le sens où elle se distingue."""
    if i["centile"] is None:
        return ""
    dessous, dessus = i["centile"]
    # Beaucoup d'ex æquo (le feu de forêt compte souvent 2 ou 4 jours partout)
    # : ni nettement au-dessus ni nettement en dessous de la moitié du
    # territoire, « plus exposé que 43 % » se lirait comme un mauvais point.
    if max(dessous, dessus) < 50:
        return "Dans la moyenne du territoire couvert"
    if i["baisse_inquietante"]:
        return (f"Été plus sec que {dessous} % du territoire couvert" if dessous >= dessus
                else f"Été plus arrosé que {dessus} % du territoire couvert")
    return (f"Plus exposé que {dessous} % du territoire couvert" if dessous >= dessus
            else f"Moins exposé que {dessus} % du territoire couvert")


def vue(climat: dict | None) -> dict | None:
    """Ce que la fiche dessine, déjà rédigé : chiffres clés, lignes par
    thème avec leurs barres (en % de l'échelle commune à la zone), légende
    et note. La carte (app.js) et la page du bien (pages.py) dessinent ce
    même contenu : une seule rédaction, deux dessins qui ne peuvent pas
    diverger."""
    if not climat:
        return None
    par_code = {i["code"]: i for i in climat["indicateurs"]}
    cles = []
    tmm = par_code.get("tmm")
    if tmm and tmm["ecart"] is not None:
        cles.append({"theme": "chaleur", "valeur": _signe(tmm["ecart"], 1) + " °C",
                     "titre": "de température moyenne",
                     "detail": f"{_nombre(tmm['reference'], 1)} → {_nombre(tmm['horizon'], 1)} °C"})
    for code, titre in (("tx35d", "au-delà de 35 °C par an"), ("swi04d", "de sol sec par an")):
        i = par_code.get(code)
        if not i:
            continue
        cles.append({"theme": i["theme"], "valeur": f"{_nombre(i['horizon'])} j", "titre": titre,
                     "detail": ("" if i["reference"] is None
                                else f"contre {_nombre(i['reference'])} sur "
                                     f"{climat['reference'].replace('-', chr(0x2011))}")})
    themes = []
    for theme, nom, icone in THEMES:
        lignes = []
        for i in climat["indicateurs"]:
            if i["theme"] != theme or i["code"] == "tmm":
                continue
            ecart, sens = _ecart(i)
            barres = i["unite"] != "°C"
            echelle = i["echelle"] or 1
            lignes.append({
                "code": i["code"], "libelle": i["libelle"],
                "unite": "" if i["unite"] in ("°C", "mm") else i["unite"],
                "reference": "" if i["reference"] is None else
                             _nombre(i["reference"], i["decimales"]),
                "horizon": _nombre(i["horizon"], i["decimales"])
                           + (" °C" if i["unite"] == "°C" else " mm" if i["unite"] == "mm" else ""),
                "ecart": ecart, "sens": sens,
                "barre_reference": (None if not barres or i["reference"] is None
                                    else round(100 * i["reference"] / echelle, 1)),
                "barre_horizon": round(100 * i["horizon"] / echelle, 1) if barres else None,
                "rang": _rang(i),
            })
        if lignes:
            themes.append({"code": theme, "nom": nom, "icone": icone, "lignes": lignes})
    return {
        "titre": f"Le climat de la commune vers {climat['horizon']}",
        "cles": cles, "themes": themes,
        "legende": [climat["reference"], f"vers {climat['horizon']}"],
        "note": (f"Projections {climat['source']}, trajectoire de référence pour "
                 f"l’adaptation (TRACC) : +2,7 °C en France vers 2050. Valeurs de la "
                 f"maille de 8 km la plus proche de la commune, et non de la parcelle ; "
                 f"barres sur une échelle commune à tout le territoire couvert par le site. "
                 f"{climat.get('avertissement') or ''}").strip(),
    }
