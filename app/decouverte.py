"""Découverte automatique d'agences immobilières par zone géographique.

Pourquoi pas un annuaire de réseau (IAD, Orpi, FNAIM…) ? Parce qu'il faudrait
deviner et suivre la structure HTML de chaque annuaire, qui change sans
prévenir. **OpenStreetMap** recense les agences immobilières comme n'importe
quel commerce (`office=estate_agent`, `shop=estate_agent`) avec leur nom et
souvent leur **site web** : c'est de l'open data, interrogeable par rayon
autour d'une ville via l'API Overpass, sans anti-bot ni structure fragile.

Le chemin est donc :
  1. Overpass → agences (nom + site) autour de chaque ville visée ;
  2. sondage de chaque site : est-il joignable ? publie-t-il un sitemap avec
     des pages de biens ? des données schema.org ?
  3. les sites exploitables sont ajoutés à la liste de collecte.

Ce module ne contient que des fonctions pures (parsing, filtrage, score),
testables hors ligne ; les appels réseau sont dans
scripts/decouvrir_agences_osm.py.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Villes visées, avec le rayon de recherche. Ce sont les bassins accessibles
# en train depuis Paris, plus ceux déjà couverts qu'on veut densifier.
ZONES = [
    {"nom": "Château-Thierry", "lat": 49.0450, "lon": 3.4028, "rayon_km": 30},
    {"nom": "Soissons",        "lat": 49.3817, "lon": 3.3236, "rayon_km": 25},
    {"nom": "Noyon",           "lat": 49.5836, "lon": 3.0000, "rayon_km": 25},
    {"nom": "Compiègne",       "lat": 49.4179, "lon": 2.8261, "rayon_km": 25},
    {"nom": "Beauvais",        "lat": 49.4295, "lon": 2.0807, "rayon_km": 30},
    {"nom": "Vendôme",         "lat": 47.7931, "lon": 1.0656, "rayon_km": 30},
    {"nom": "Nogent-le-Rotrou", "lat": 48.3230, "lon": 0.8175, "rayon_km": 25},
    {"nom": "Sens",            "lat": 48.1977, "lon": 3.2836, "rayon_km": 25},
]

# Portails nationaux et réseaux sociaux : ce ne sont pas des sites d'agence
# locale, et la plupart bloquent la collecte automatisée.
PORTAILS_EXCLUS = {
    "seloger.com", "bienici.com", "leboncoin.fr", "pap.fr", "logic-immo.com",
    "avendrealouer.fr", "figaro.fr", "ouestfrance-immo.com", "paruvendu.fr",
    "facebook.com", "google.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "youtube.com", "wa.me", "immobilier.notaires.fr", "meilleursagents.com",
}

# Indices d'une page de bien dans une URL (mêmes repères que le collecteur).
MOTIF_BIEN = re.compile(
    r"/(annonces?|biens?|vente|vendre|a-vendre|property|properties|nos-biens"
    r"|detail|ref|maison|propriete|achat)[-/]",
    re.IGNORECASE,
)


def requete_overpass(zone: dict) -> str:
    """Requête Overpass QL : les agences immobilières autour d'une ville."""
    rayon = int(zone["rayon_km"] * 1000)
    autour = f"(around:{rayon},{zone['lat']},{zone['lon']})"
    return (
        "[out:json][timeout:90];("
        f'node["office"="estate_agent"]{autour};'
        f'way["office"="estate_agent"]{autour};'
        f'node["shop"="estate_agent"]{autour};'
        f'way["shop"="estate_agent"]{autour};'
        ");out center tags;"
    )


def domaine(url: str) -> str:
    """Domaine nu, sans www ni sous-chemin ('https://www.a.fr/x' → 'a.fr')."""
    if not url:
        return ""
    if "//" not in url:
        url = "https://" + url
    hote = (urlparse(url).netloc or "").lower().strip()
    return hote[4:] if hote.startswith("www.") else hote


def est_portail_exclu(url: str) -> bool:
    """True pour un portail national, un réseau social ou un domaine vide."""
    d = domaine(url)
    if not d or "." not in d:
        return True
    return any(d == p or d.endswith("." + p) for p in PORTAILS_EXCLUS)


def agences_depuis_overpass(reponse: dict, zone_nom: str) -> list[dict]:
    """Réponse Overpass → agences {nom, site, zone}, dédoublonnées par domaine."""
    vues, agences = set(), []
    for element in (reponse or {}).get("elements", []):
        tags = element.get("tags") or {}
        site = (tags.get("website") or tags.get("contact:website")
                or tags.get("url") or "").strip()
        nom = (tags.get("name") or "").strip()
        if not site or not nom or est_portail_exclu(site):
            continue
        d = domaine(site)
        if d in vues:
            continue
        vues.add(d)
        agences.append({"nom": nom, "site": f"https://{d}", "zone": zone_nom})
    return agences


def urls_de_biens(urls: list[str], hote: str) -> list[str]:
    """Parmi des URLs de sitemap, celles qui ressemblent à une page de bien."""
    gardees, vues = [], set()
    for u in urls or []:
        if not u or domaine(u) != domaine(hote):
            continue
        if MOTIF_BIEN.search(u) and u not in vues:
            vues.add(u)
            gardees.append(u)
    return gardees


def score_candidat(sonde: dict) -> int:
    """Note un site sondé : plus il expose de biens proprement, mieux c'est.

    Sert à trier les candidats — on branche d'abord ceux qui rapporteront le
    plus de biens exploitables, pas ceux dont le nom sonne bien.
    """
    if not sonde.get("joignable"):
        return 0
    note = min(sonde.get("nb_biens", 0), 60)          # jusqu'à 60 points
    if sonde.get("sitemap"):
        note += 20        # un sitemap = collecte fiable et peu coûteuse
    if sonde.get("schema_org"):
        note += 20        # données structurées = extraction propre
    return note


def fusionner(existantes: list[dict], candidates: list[dict],
              note_mini: int = 25) -> tuple[list[dict], list[dict]]:
    """Ajoute les candidates retenues aux agences déjà configurées.

    Renvoie (liste complète, nouvelles ajoutées). Le dédoublonnage se fait sur
    le domaine : une agence déjà suivie n'est jamais ajoutée deux fois.
    """
    connus = {domaine(a.get("site", "")) for a in existantes}
    ajoutees = []
    for c in sorted(candidates, key=lambda x: -x.get("note", 0)):
        d = domaine(c.get("site", ""))
        if not d or d in connus or c.get("note", 0) < note_mini:
            continue
        connus.add(d)
        ajoutees.append({
            "nom": c["nom"],
            "site": c["site"],
            "zone": c.get("zone", ""),
            "index": [],
            "max": 8,
            "pages": 45,
        })
    return existantes + ajoutees, ajoutees
