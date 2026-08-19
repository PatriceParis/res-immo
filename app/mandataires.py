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


def table_des_communes(index: list) -> dict:
    """slug → (commune, département), construite une fois par passage.

    L'index reste trié du plus long au plus court : à slug identique — deux
    homonymes dans deux départements — c'est donc le premier de l'index qui
    l'emporte, comme avec l'ancienne boucle.
    """
    table: dict = {}
    for rang, (slug, commune, departement) in enumerate(index):
        table.setdefault(slug, (rang, commune, departement))
    return table


def _suites_de_mots(chemin: str) -> list[str]:
    """Les suites de mots contiguës de l'adresse, les plus longues d'abord.

    `normaliser` ne laisse que [a-z0-9-] : une adresse normalisée est donc une
    simple suite de mots séparés par des tirets. Or la frontière
    `(?:^|-)slug(?:-|$)` est vraie exactement quand le slug couvre une suite
    entière de ces mots — jamais une portion de mot. Énumérer les suites et
    les chercher dans une table donne donc le même résultat que d'essayer
    chaque commune.

    « Le même » au sens strict, arbitrages compris. J'avais d'abord tenu la
    différence pour négligeable — à longueur égale entre deux communes sans
    rapport dans la même adresse, l'ancienne boucle tranchait par l'ordre de
    l'index et celle-ci par la position dans l'adresse. Un tirage de deux
    mille adresses a produit le contre-exemple en quelques millisecondes :
    « sancerre-montbard » partait en Côte-d'Or avant, dans le Cher après. On
    conserve donc le rang de l'index dans la table et l'on tranche comme
    avant : la suite la plus longue, puis le plus petit rang.
    """
    mots = [m for m in chemin.split("-") if m]
    suites = []
    for longueur in range(len(mots), 0, -1):
        for debut in range(len(mots) - longueur + 1):
            suite = "-".join(mots[debut:debut + longueur])
            if len(suite) >= LONGUEUR_MINIMALE_COMMUNE:
                suites.append(suite)
    suites.sort(key=lambda s: -len(s))
    return suites


def commune_de_l_adresse(url: str, index: list,
                         table: dict | None = None) -> tuple[str, str] | None:
    """(commune, département) devinés depuis l'adresse, ou None.

    Le nom doit être délimité par des tirets ou par les bords de l'adresse.
    Sans cette frontière, on cherchait une simple sous-chaîne, et n'importe
    quel mot plus long contenant le nom d'une commune la faisait gagner :
    « plai**sance**-du-touch » devenait Sancé (71), « pont**chateau** »
    devenait Château (71). Mesuré sur le catalogue : 572 annonces IAD sur
    1 023 portaient une étiquette de département fausse, et 283 des 474
    annonces dites « IAD France (71) » étaient en réalité en Gironde, en
    Loire-Atlantique ou en Seine-Saint-Denis.

    Le coût n'était pas seulement cosmétique : ces pages ont été téléchargées
    à tort, elles occupaient le budget de collecte du département visé, et le
    site affichait « IAD France (71) » sous une maison de Bordeaux.

    Le prix de cette frontière, non mesuré à l'époque : la recherche essayait
    CHAQUE commune contre CHAQUE adresse, en compilant une expression par
    essai — seize mille communes contre vingt-huit mille adresses, soit
    quatre cent cinquante millions de compilations. Mesuré le 19 août :
    37 ms par adresse, 17,5 minutes pour le seul sitemap de Safti, quand le
    réseau dispose de 400 secondes. Le passage mandataires n'a rien rapporté
    pendant trois jours pour cette seule raison, et j'ai cherché ailleurs
    deux fois avant de le mesurer.

    On énumère donc les suites de mots de l'adresse au lieu des communes du
    pays. C'est le même résultat par construction — voir `_suites_de_mots` —
    au prix du carré du nombre de mots d'une adresse, une dizaine.
    """
    chemin = normaliser(urlparse(url).path)
    if table is None:
        table = table_des_communes(index)
    lieu = longueur = meilleur_rang = None
    for suite in _suites_de_mots(chemin):
        if longueur is not None and len(suite) < longueur:
            break            # plus court que le gagnant : la suite est vaine
        trouve = table.get(suite)
        if trouve is None:
            continue
        rang, commune, departement = trouve
        if longueur is None or rang < meilleur_rang:
            longueur, meilleur_rang = len(suite), rang
            lieu = (commune, departement)
    return lieu


def annonces_a_visiter(urls: list[str], reseau: dict, index: list) -> list[dict]:
    """Trie les adresses du sitemap : ce qu'on garde, et pourquoi.

    Renvoie un dict par annonce retenue, avec la commune et le département
    déduits — ce que la page elle-même ne donne pas toujours.
    """
    # Construite UNE fois, pas une par adresse : c'est tout l'objet du
    # correctif du 19 août.
    table = table_des_communes(index)
    retenues, vues = [], set()
    for url in urls:
        if not reseau["motif_annonce"].search(url):
            continue
        if not TYPES_VOULUS.search(normaliser(urlparse(url).path)):
            continue
        lieu = commune_de_l_adresse(url, index, table)
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


def departement_du_code_postal(code_postal) -> str | None:
    """« 33480 » → « 33 ». Le seul juge du département quand l'adresse ment.

    La Corse et l'outre-mer ne sont pas dans notre périmètre : deux chiffres
    suffisent. On refuse tout ce qui n'est pas cinq chiffres plutôt que de
    tronquer une valeur douteuse — un département inventé serait pire qu'un
    département inconnu.
    """
    code = str(code_postal or "").strip()
    return code[:2] if len(code) == 5 and code.isdigit() else None


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


# Une TENTATIVE de réseau, par opposition à la visite d'un de ses
# départements. Aucun département ne s'appelle « * » : la clé est donc comptée
# par `derniere_visite_du_reseau`, qui balaie le préfixe, et jamais cherchée
# par `ordre_des_departements`, qui n'interroge que des codes réels.
TENTATIVE = "*"


def cle_tentative(cle_reseau: str) -> str:
    """La clé qui dit « on a essayé ce réseau ce jour-là », abouti ou non.

    Sans elle, un réseau qui épuise sa part de budget avant d'avoir terminé un
    seul département ne laisse aucune trace — donc reste éternellement « jamais
    vu », donc repasse en tête au passage suivant, et affame ceux qui, eux,
    produisent. C'est ce qui est arrivé les 17 et 18 août : Safti et Capifrance
    partaient devant à chaque fois, dépensaient leur part à lire des sitemaps
    sans jamais atteindre un département, et IAD — le seul réseau qui
    rapportait — se retrouvait dernier avec un budget déjà vide. Le passage
    entier a fini par ne plus rien rapporter du tout.

    Céder son tour n'est pas être servi : la tentative ne dit pas qu'on a
    collecté, seulement qu'on a eu sa chance.
    """
    return cle_journal(cle_reseau, TENTATIVE)


def derniere_visite_du_reseau(cle_reseau: str, derniere_visite: dict) -> str:
    """La date la plus RÉCENTE parmi les cibles d'un réseau, ou "" s'il n'en a
    aucune.

    La plus récente, et non la plus ancienne : un réseau porte des dizaines de
    cibles départementales, et la plus ancienne d'entre elles le ferait
    paraître délaissé alors qu'on y est passé le matin même — il repasserait
    devant à chaque tour, et les autres n'auraient jamais le leur.
    """
    prefixe = f"{cle_reseau}:"
    dates = [jour for cle, jour in derniere_visite.items() if cle.startswith(prefixe)]
    return max(dates) if dates else ""


def ordre_des_reseaux(reseaux: dict, derniere_visite: dict) -> list[str]:
    """Les réseaux vus il y a le plus longtemps d'abord.

    Ils étaient parcourus dans l'ordre alphabétique, avec une seule échéance
    commune : Capifrance s'abstenait en premier, IAD prenait tout le budget, et
    Safti — dernier de l'alphabet — n'a jamais eu son tour. Zéro annonce Safti
    au catalogue, pour un réseau configuré depuis toujours.

    Troisième apparition de la même forme, après Century 21 et les
    départements : un ordre fixe et un budget partagé, et la queue de liste
    n'est jamais servie.
    """
    return sorted(reseaux,
                  key=lambda cle: (derniere_visite_du_reseau(cle, derniere_visite), cle))


def part_de_budget(restant: float, reseaux_restants: int) -> float:
    """Le temps qu'un réseau peut prendre sans affamer les suivants.

    Recalculée à CHAQUE réseau, sur le temps qui reste : ainsi la part que
    Capifrance rend en s'abstenant au bout de trois secondes revient aux
    autres, au lieu d'être perdue. Un seul réseau demandé garde tout — c'est
    le cas du rattrapage, qui n'est lancé que pour ça.
    """
    if reseaux_restants <= 1:
        return max(restant, 0.0)
    return max(restant, 0.0) / reseaux_restants


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
