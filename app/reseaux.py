"""Recensement des agences de RÉSEAU (franchises) sur les terroirs ciblés.

Pourquoi cette piste
--------------------
OpenStreetMap ne connaît qu'une partie des agences, et n'a de site web que
pour une minorité d'entre elles. Or une grande part du tissu immobilier
français appartient à des réseaux — Laforêt, Century 21, Orpi, Guy Hoquet,
Nestenn, ERA… — qui publient TOUS l'annuaire de leurs agences sur leur site
national, avec une page par agence. C'est une liste exhaustive, tenue à jour
par le réseau lui-même, et accessible par sitemap.

Deux familles à ne pas confondre
--------------------------------
- Les **franchises** (Laforêt, Century 21, Orpi…) : chaque agence est une
  entreprise indépendante, avec sa vitrine et souvent son propre site. C'est
  ce qu'on cherche.
- Les **réseaux de mandataires** (IAD, Safti, Capifrance, Optimhome…) : pas
  d'agence physique, pas de site local — les mandats sont publiés sur le
  site national. Il n'y a donc rien à « brancher » comme pour une agence :
  on ne peut que lire le site national, qui est un portail. Ils sont listés
  ici pour mémoire, avec `mandataires: True`, et écartés de la collecte.

Ce module ne contient AUCUNE requête réseau : il transforme des données déjà
récupérées. Les appels vivent dans scripts/decouvrir_reseaux.py, ce qui rend
la logique testable hors-ligne.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

# Réseaux à annuaire d'agences. `site` sert de base au sitemap.
RESEAUX = [
    {"nom": "Laforêt", "site": "https://www.laforet.com"},
    {"nom": "Century 21", "site": "https://www.century21.fr"},
    {"nom": "Orpi", "site": "https://www.orpi.com"},
    {"nom": "Guy Hoquet", "site": "https://www.guy-hoquet.com"},
    {"nom": "Nestenn", "site": "https://www.nestenn.com"},
    {"nom": "ERA Immobilier", "site": "https://www.erafrance.com"},
    {"nom": "L'Adresse", "site": "https://www.ladresse.com"},
    {"nom": "Arthurimmo", "site": "https://www.arthurimmo.com"},
    {"nom": "Human Immobilier", "site": "https://www.humanimmobilier.fr"},
    {"nom": "Stéphane Plaza Immobilier",
     "site": "https://www.stephaneplazaimmobilier.com"},
    {"nom": "Square Habitat", "site": "https://www.squarehabitat.fr"},
    {"nom": "Immo de France", "site": "https://www.immodefrance.com"},
    {"nom": "Agences de France", "site": "https://www.agencesdefrance.com"},
    {"nom": "Foncia", "site": "https://fr.foncia.com"},
    # Réseaux de mandataires : aucun site d'agence à brancher (voir en-tête).
    {"nom": "IAD France", "site": "https://www.iadfrance.fr", "mandataires": True},
    {"nom": "Safti", "site": "https://www.safti.fr", "mandataires": True},
    {"nom": "Capifrance", "site": "https://www.capifrance.fr", "mandataires": True},
    {"nom": "Optimhome", "site": "https://www.optimhome.com", "mandataires": True},
    {"nom": "Propriétés Privées", "site": "https://www.proprietes-privees.com",
     "mandataires": True},
]

# Chemin d'une page d'agence dans l'annuaire d'un réseau. Volontairement large :
# on ne devine pas le schéma d'URL de chaque site — c'est le nom de commune qui
# fait le vrai tri juste après.
MOTIF_PAGE_AGENCE = re.compile(
    r"/(?:agences?|nos-agences|trouver-une-agence|agence-immobiliere|immobilier)"
    r"[-/]", re.IGNORECASE)

# Pages de l'annuaire qui ne désignent PAS une agence précise.
MOTIF_PAGE_GENERIQUE = re.compile(
    r"/(?:recherche|search|annonces?|biens?|vente|location|estimation|actualites?"
    r"|blog|conseils?|recrutement|franchise|mentions|contact|plan-du-site)"
    r"(?:[-/]|$)", re.IGNORECASE)


def slug(texte: str) -> str:
    """Forme comparable d'un nom de commune : sans accents, en tirets."""
    sans = unicodedata.normalize("NFD", texte or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sans.lower()).strip("-")


def _segments(url: str) -> str:
    return slug(urlparse(url or "").path)


def agences_du_reseau(reseau: dict, urls: list[str],
                      communes_par_slug: dict) -> list[dict]:
    """Pages d'agence du réseau situées dans une commune ciblée.

    `communes_par_slug` : {slug de commune → code département}. C'est lui qui
    restreint au périmètre ; sans cela on ramènerait les 800 agences d'un
    réseau national, dont 95 % hors de portée de Paris.
    """
    if reseau.get("mandataires"):
        return []
    hote = urlparse(reseau["site"]).netloc.lower()
    trouvees, vues = [], set()
    for url in urls or []:
        if urlparse(url).netloc.lower() != hote:
            continue
        if not MOTIF_PAGE_AGENCE.search(url) or MOTIF_PAGE_GENERIQUE.search(url):
            continue
        chemin = _segments(url)
        # On teste les communes les plus longues d'abord : « saint-jean » ne
        # doit pas l'emporter sur « saint-jean-de-braye » quand les deux
        # figurent dans le chemin.
        for cs in sorted(communes_par_slug, key=len, reverse=True):
            if len(cs) < 4:
                continue
            if re.search(rf"(?:^|-){re.escape(cs)}(?:-|$)", chemin):
                if url in vues:
                    break
                vues.add(url)
                trouvees.append({
                    "nom": f"{reseau['nom']} {communes_par_slug[cs][1]}",
                    "site": url,
                    "zone": f"{communes_par_slug[cs][1]} ({communes_par_slug[cs][0]})",
                    "reseau": reseau["nom"],
                    "departement": communes_par_slug[cs][0],
                })
                break
    return trouvees


def index_des_communes(par_departement: dict) -> dict:
    """{slug → (département, nom)} à partir de {département: [noms de communes]}.

    Les homonymes entre départements sont écartés : « Sainte-Marie » existe
    partout, et rattacherait des agences au mauvais terroir.
    """
    compte: dict = {}
    for dept, noms in (par_departement or {}).items():
        for nom in noms:
            compte.setdefault(slug(nom), set()).add((dept, nom))
    return {s: next(iter(v)) for s, v in compte.items() if len(v) == 1}
