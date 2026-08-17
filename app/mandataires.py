"""Réseaux de mandataires : quelles annonces lire, et sous quelle identité.

Ces réseaux — IAD, Safti, Capifrance — publient leurs propres mandats sur un
national, avec une page par bien et un sitemap à l'intention des robots. Ce
n'est pas un agrégateur qui republie les annonces d'autrui : c'est une agence,
simplement très grande. Mesuré chez IAD : 94 216 annonces, dont 44 318 dans
nos terroirs — quarante-cinq fois notre catalogue d'alors.

Ce module ne fait AUCUNE requête : il décide quoi lire à partir d'une liste
d'adresses déjà récupérée, ce qui le rend testable hors-ligne. Les appels
vivent dans scripts/collecter_mandataires.py.

Deux décisions méritent d'être expliquées.

**Une « agence » par département.** Un réseau entier sous un seul nom aurait
cassé la mémoire des annonces : `historique.fusionner` considère qu'une
agence visitée fait autorité sur SES biens, et supprime ceux qu'elle n'a plus.
Avec 44 000 annonces lues quelques centaines à la fois, chaque passage aurait
donc effacé tout ce qu'il n'avait pas eu le temps de revoir. Découpé par
département, un passage couvre des départements entiers et l'autorité
redevient exacte. Le menu déroulant y gagne aussi : « IAD France (71) » dit
quelque chose, « IAD France » avec 44 000 biens ne dit rien.

**Le tri se fait sur l'adresse, avant toute visite.** L'adresse d'une annonce
porte son type et sa commune (`/annonce/maison-vente-6-pieces-saint-berain-
sur-dheune-245m2/…`). On peut donc écarter les appartements et les
départements hors cible sans ouvrir une seule page — c'est ce qui rend la
chose praticable et courtoise : on ne télécharge que ce qu'on garde.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

# Réseaux retenus. `sitemaps` est vide par défaut : on les découvre dans
# robots.txt, que le réseau tient à jour lui-même.
RESEAUX = {
    "iad": {
        "nom": "IAD France",
        "site": "https://www.iadfrance.fr",
        # robots.txt interdit /liste/annonces* (les pages de recherche) mais
        # laisse les pages d'annonce ouvertes. On s'en tient à celles-ci.
        "motif_annonce": re.compile(r"/annonce/", re.IGNORECASE),
    },
    "capifrance": {
        "nom": "Capifrance",
        "site": "https://www.capifrance.fr",
        "motif_annonce": re.compile(r"/annonce|/bien", re.IGNORECASE),
    },
    "safti": {
        "nom": "Safti",
        "site": "https://www.safti.fr",
        # robots.txt interdit /recherche et /bien-indisponible ; les pages
        # d'annonce (/annonces/achat/…) sont ouvertes.
        "motif_annonce": re.compile(r"/annonces/achat/", re.IGNORECASE),
        # Safti sépare ses sitemaps par TYPE et par DISPONIBILITÉ :
        # sitemap.annonce.maison.disponible.xml, .appartement.vendu.xml…
        # On ne lit donc que les maisons encore à vendre — 28 286 adresses au
        # lieu de 73 626. C'est une économie pour eux comme pour nous, et cela
        # évite d'aller chercher des biens déjà vendus pour les écarter après.
        "sitemaps_voulus": re.compile(r"annonce\.(maison|propriete)\.disponible",
                                      re.IGNORECASE),
    },
}

# Types de biens qu'on veut, tels qu'ils apparaissent dans l'adresse. Un
# appartement n'a ni terrain ni autonomie possible : par construction il ne
# peut pas être un refuge, et le filtre qualité l'écarterait de toute façon —
# autant ne pas le télécharger.
TYPES_VOULUS = re.compile(
    r"\b(maison|longere|ferme|fermette|moulin|chateau|manoir|propriete|"
    r"pavillon|villa|corps-de-ferme|demeure|mas|chaumiere)\b", re.IGNORECASE)

# Un nom de commune plus court que cela produit trop de rapprochements
# fortuits dans une adresse (« Ay », « Bu », « Oz »).
LONGUEUR_MINIMALE_COMMUNE = 5


def normaliser(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFD", texte or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sans_accent.lower()).strip("-")


def index_des_communes(communes_par_departement: dict) -> list[tuple[str, str, str]]:
    """(nom normalisé, nom d'origine, département), les plus longs d'abord.

    L'ordre compte : sans lui, « Bérain » l'emporterait sur « Saint-Bérain-sur-
    Dheune » et l'annonce partirait dans le mauvais département.
    """
    index = []
    for departement, communes in communes_par_departement.items():
        for commune in communes:
            slug = normaliser(commune)
            if len(slug) >= LONGUEUR_MINIMALE_COMMUNE:
                index.append((slug, commune, departement))
    index.sort(key=lambda t: -len(t[0]))
    return index


def commune_de_l_adresse(url: str, index: list) -> tuple[str, str] | None:
    """(commune, département) devinés depuis l'adresse, ou None."""
    chemin = normaliser(urlparse(url).path)
    for slug, commune, departement in index:
        if slug in chemin:
            return commune, departement
    return None


def annonces_a_visiter(urls: list[str], reseau: dict, index: list) -> list[dict]:
    """Trie les adresses du sitemap : ce qu'on garde, et pourquoi.

    Renvoie un dict par annonce retenue, avec la commune et le département
    déduits — ce que la page elle-même ne donne pas toujours.
    """
    retenues, vues = [], set()
    for url in urls:
        if not reseau["motif_annonce"].search(url):
            continue
        if not TYPES_VOULUS.search(normaliser(urlparse(url).path)):
            continue
        lieu = commune_de_l_adresse(url, index)
        if not lieu:
            continue                      # hors des terroirs ciblés
        if url in vues:
            continue
        vues.add(url)
        commune, departement = lieu
        retenues.append({
            "url": url,
            "commune": commune,
            "departement": departement,
            "agence": nom_d_agence(reseau, departement),
        })
    return retenues


def nom_d_agence(reseau: dict, departement: str) -> str:
    """« IAD France (71) » — voir l'en-tête pour le pourquoi du découpage."""
    return f"{reseau['nom']} ({departement})"


def par_departement(annonces: list[dict]) -> dict:
    groupes: dict = {}
    for annonce in annonces:
        groupes.setdefault(annonce["departement"], []).append(annonce)
    return groupes


def ordre_dans_le_departement(annonces: list[dict], deja_vues: dict) -> list[dict]:
    """Les annonces d'un département, les jamais vues d'abord.

    Un passage ne visite que quelques dizaines d'annonces par département,
    et prenait jusqu'ici les PREMIÈRES du sitemap — donc toujours les mêmes.
    La Saône-et-Loire en compte 1 333 : les 1 308 suivantes n'auraient jamais
    été atteintes, et le département aurait paru couvert alors qu'on n'en
    voyait que le premier vingtième.

    On sert donc d'abord ce qu'on ne connaît pas, puis ce qu'on a revu il y a
    le plus longtemps — la même règle que la rotation des agences, appliquée
    un cran plus bas.
    """
    return sorted(annonces, key=lambda a: (deja_vues.get(a["url"], ""), a["url"]))


def cle_journal(cle_reseau: str, departement: str) -> str:
    """La clé d'une cible dans data/mandataires_visites.json.

    Une seule fabrique, pour celui qui écrit comme pour celui qui lit. Les
    deux avaient divergé : le collecteur notait « iad:71 », la rotation
    cherchait « 71 ». Aucune recherche n'aboutissait, tous les départements
    paraissaient neufs, l'égalité était tranchée par le code — donc « 01 »
    d'abord, à chaque passage, jusqu'à épuisement du budget de temps. Le 71
    n'a pas été revu pendant dix jours quand ses voisins l'étaient de la
    veille, et une maison mise en ligne entre temps ne pouvait pas entrer.

    C'est la faute qui avait déjà coûté cinquante-six annonces Century 21 :
    deux copies d'une même règle, séparées, qui s'écartent. Même parade.
    """
    return f"{cle_reseau}:{departement}"


def ordre_des_departements(groupes: dict, derniere_visite: dict,
                           cle_reseau: str) -> list[str]:
    """Les départements vus il y a le plus longtemps d'abord.

    Même raison que la rotation des agences : sans elle, une collecte bornée
    par le temps repasserait éternellement sur les mêmes premiers et ne
    verrait jamais les derniers.

    `cle_reseau` n'a pas de valeur par défaut à dessein : c'est justement son
    absence qui a désarmé la rotation sans rien signaler. Mieux vaut un appel
    qui échoue qu'un tri qui ment.
    """
    return sorted(
        groupes,
        key=lambda d: (derniere_visite.get(cle_journal(cle_reseau, d), ""), d))
