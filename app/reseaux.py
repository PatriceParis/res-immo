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


def extensions_nationales(communes: list) -> dict:
    """{slug → slugs de communes françaises qui le prolongent}.

    « Brétigny » est une commune de l'Oise, « Brétigny-sur-Orge » une commune
    de l'Essonne. L'URL /agence-immobiliere/bretigny-sur-orge contient
    « bretigny » suivi d'un tiret : elle se rattachait donc à l'Oise. Savoir
    qu'un nom plus long existe permet d'exiger un rattachement MAXIMAL.
    """
    tous = []
    for c in communes or []:
        nom = c.get("nom") if isinstance(c, dict) else c
        if nom:
            tous.append(slug(nom))
    par_prefixe: dict = {}
    for s in tous:
        morceaux = s.split("-")
        for i in range(1, len(morceaux)):
            par_prefixe.setdefault("-".join(morceaux[:i]), set()).add(s)
    return {k: sorted(v) for k, v in par_prefixe.items()}


def agences_du_reseau(reseau: dict, urls: list[str], communes_par_slug: dict,
                      extensions: dict | None = None) -> list[dict]:
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
            m = re.search(rf"(?:^|-){re.escape(cs)}(?:-|$)", chemin)
            if m:
                # Rattachement MAXIMAL : si une commune française au nom plus
                # long commence ici, c'est elle que l'URL désigne.
                depuis = chemin[m.start() + (1 if m.group(0)[0] == "-" else 0):]
                if any(re.match(rf"{re.escape(plus_long)}(?:-|$)", depuis)
                       for plus_long in (extensions or {}).get(cs, ())):
                    continue
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


# Un seuil de longueur serait le mauvais outil : « Noyon » fait cinq lettres,
# « Sens » et « Gien » quatre, et ce sont des villes que l'on vise. Trois
# lettres restent trop peu pour distinguer quoi que ce soit.
LONGUEUR_MINIMALE = 4

# Ce qui départage vraiment, ce n'est pas la longueur mais le fait d'être un
# mot courant. « Ville » (Oise) et « Aube » (Orne) sont de vraies communes,
# qu'on lit pourtant dans n'importe quelle adresse : c'est ainsi que
# /immobilier-montlucon-centre-ville-les-forges/ est devenu « Orpi Ville ».
# On n'y met QUE des mots dont l'usage courant l'emporte sur la commune —
# Sens, Tours, Noyon ou Gien n'y ont pas leur place, ce sont nos terroirs.
TROP_COURANTS = {
    "ville", "aube", "bourg", "chapelle", "campagne", "village", "centre",
    "vallee", "coteau", "riviere", "rivieres", "chateau", "abbaye", "foret",
    "montagne", "la-chapelle", "le-bourg", "plage", "port", "pont", "gare",
    "marche", "place", "eglise", "moulin", "ferme", "grange", "maison",
}


def index_des_communes(par_departement: dict, nationales: dict | None = None) -> dict:
    """{slug → (département, nom)} pour les communes utilisables comme repère.

    Trois filtres, chacun né d'un faux positif constaté :

    - **Homonymie nationale.** « Brétigny » existe dans l'Oise et dans
      l'Essonne : /agence-immobiliere/bretigny désignait Brétigny-sur-Orge,
      et l'agence se retrouvait rattachée à l'Oise. `nationales` — l'ensemble
      des communes de France — permet d'écarter tout nom porté par plusieurs
      communes du pays, pas seulement par plusieurs de NOS départements.
    - **Noms trop courts**, sous six lettres : trop de collisions fortuites.
    - **Mots courants** : « Ville », « Aube », « Bourg » sont de vraies
      communes qu'on lit dans n'importe quelle adresse.
    """
    compte: dict = {}
    for dept, noms in (par_departement or {}).items():
        for nom in noms:
            compte.setdefault(slug(nom), set()).add((dept, nom))

    index = {}
    for s, valeurs in compte.items():
        if len(valeurs) > 1 or len(s) < LONGUEUR_MINIMALE or s in TROP_COURANTS:
            continue
        if nationales and nationales.get(s, 0) > 1:
            continue          # le nom existe ailleurs en France : trop risqué
        index[s] = next(iter(valeurs))
    return index


def occurrences_nationales(communes: list) -> dict:
    """{slug → nombre de communes françaises portant ce nom}.

    Sert à écarter les noms ambigus. Une liste vide n'est pas une erreur :
    l'index se rabat alors sur les autres filtres, en le disant.
    """
    compte: dict = {}
    for c in communes or []:
        nom = c.get("nom") if isinstance(c, dict) else c
        if nom:
            s = slug(nom)
            compte[s] = compte.get(s, 0) + 1
    return compte
