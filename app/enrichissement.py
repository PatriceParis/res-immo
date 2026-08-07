"""Enrichissement d'une annonce à partir de services publics.

Position (Base Adresse Nationale), densité de population (geo.api.gouv.fr) et
altitude : trois informations que les sites d'agences ne donnent presque
jamais, et dont dépend la moitié du score de résilience — distance de Paris,
densité, altitude.

Ce module a d'abord vécu dans le collecteur par navigateur. Il en est sorti
le jour où un second collecteur en a eu besoin : les réseaux de mandataires
publient le code postal mais ni la commune ni les coordonnées, et sans elles
leurs biens n'auraient ni carte, ni terroir, ni score.
"""

from __future__ import annotations

try:
    import requests
except ImportError:                                   # collecte non installée
    requests = None


def _ban(params: dict):
    """Base Adresse Nationale ; renvoie (lat, lon, ville, cp, codeINSEE) ou None."""
    if requests is None:
        return None
    try:
        r = requests.get("https://api-adresse.data.gouv.fr/search/", params=params,
                         timeout=8, headers={"User-Agent": "RefugeImmo-POC"})
        r.raise_for_status()
        feats = r.json().get("features") or []
    except Exception:
        return None
    if not feats:
        return None
    pr = feats[0]["properties"]
    lon, lat = feats[0]["geometry"]["coordinates"]
    return lat, lon, (pr.get("city") or pr.get("name")), pr.get("postcode"), pr.get("citycode")


def _densite(citycode):
    """Densité de population (hab/km²) de la commune via geo.api.gouv.fr."""
    if not citycode or requests is None:
        return None
    try:
        r = requests.get(f"https://geo.api.gouv.fr/communes/{citycode}",
                         params={"fields": "population,surface"}, timeout=8,
                         headers={"User-Agent": "RefugeImmo-POC"})
        r.raise_for_status()
        d = r.json()
    except Exception:
        return None
    pop, surf = d.get("population"), d.get("surface")  # surface en hectares
    return round(pop / (surf / 100.0), 1) if pop and surf else None


def _altitude(lat, lon):
    """Altitude (m) de la position, avec repli et réessai.

    Une seule tentative sur un seul service ne renseignait l'altitude que pour
    la moitié des biens — or elle vaut jusqu'à 3 points du pilier Situation.
    On interroge donc deux services successivement, avec un second essai.
    """
    if lat is None or lon is None or requests is None:
        return None
    services = (
        ("https://api.open-meteo.com/v1/elevation",
         {"latitude": lat, "longitude": lon},
         lambda d: (d.get("elevation") or [None])[0]),
        # Repli : service d'élévation d'OpenTopoData (jeu SRTM 30 m).
        ("https://api.opentopodata.org/v1/srtm30m",
         {"locations": f"{lat},{lon}"},
         lambda d: ((d.get("results") or [{}])[0]).get("elevation")),
    )
    # Deux services, un seul passage : l'altitude ne vaut pas qu'on retarde
    # toute la collecte. Le budget de temps est plus précieux que ces 3 points.
    for url, params, lire in services:
        try:
            r = requests.get(url, params=params, timeout=6,
                             headers={"User-Agent": "RefugeImmo-POC"})
            r.raise_for_status()
            valeur = lire(r.json())
            if isinstance(valeur, (int, float)):
                return round(valeur)
        except Exception:
            continue
    return None


def _geocoder(commune, cp):
    if not commune:
        return None
    return _ban({"q": f"{commune} {cp or ''}".strip(), "type": "municipality", "limit": 1})


def _geocoder_cp(cp):
    """Géocode par code postal (fiable) : renvoie la commune principale du CP."""
    if not cp:
        return None
    return _ban({"q": str(cp), "type": "municipality", "limit": 1})


def _geocoder_texte(texte):
    """Repli : cherche une COMMUNE citée dans le titre (type=municipality pour
    ne jamais tomber sur une adresse au hasard, ex. un titre vague → Orléans)."""
    if not texte:
        return None
    return _ban({"q": texte[:80], "type": "municipality", "limit": 1})
