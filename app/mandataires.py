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
        # L'adresse porte le code postal : « /maison/givry-71640/1480990 ». Il
        # sert à ORDONNER, jamais à écarter — voir `ordre_dans_le_departement`.
        "cp_dans_l_adresse": re.compile(r"-(\d{5})/\d+/?$"),
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


def reseaux_autorises(reseaux: dict, exclus: set) -> dict:
    """Les réseaux dont le site n'a pas demandé son retrait.

    Pure et séparée du collecteur pour être testée sans réseau : exclure
    « iadfrance.fr » doit retirer IAD du passage, et rien d'autre.
    """
    from .exclusions import est_exclu
    return {cle: reseau for cle, reseau in reseaux.items()
            if not est_exclu(reseau.get("site", ""), exclus)}


def index_des_communes(communes_par_departement: dict,
                       cibles: set | None = None,
                       anciennes: dict | None = None) -> list[tuple[str, str, str]]:
    """(nom normalisé, nom d'origine, département), les plus longs d'abord.

    L'ordre compte : sans lui, « Bérain » l'emporterait sur « Saint-Bérain-sur-
    Dheune » et l'annonce partirait dans le mauvais département.

    L'index peut porter les communes de toute la France : `cibles` dit alors
    lesquelles sont chez nous. À nom égal, les nôtres passent devant — un
    Beaulieu reste celui de Côte-d'Or, comme lorsque l'index ne connaissait
    que nos terroirs.

    `anciennes` : les communes déléguées et associées, par département. Fondues
    dans une commune nouvelle, elles ont quitté la liste des communes, mais les
    annonces les nomment toujours : Pierrefitte-sur-Seine appartient à
    Saint-Denis depuis le 1er janvier 2025, et « pierrefitte-sur-seine » se
    lisait « Pierrefitte », commune des Vosges. Une ancienne commune ne
    l'emporte que par la longueur : à longueur égale, celle d'aujourd'hui passe
    devant, d'où qu'elle soit — La Colombe de la Manche reste devant celle,
    fondue, du Loir-et-Cher.
    """
    index = []
    for ancienne, source in enumerate((communes_par_departement, anciennes or {})):
        for departement, communes in source.items():
            for commune in communes:
                slug = normaliser(commune)
                if len(slug) >= LONGUEUR_MINIMALE_COMMUNE:
                    index.append((slug, commune, departement, ancienne))
    index.sort(key=lambda t: (-len(t[0]), t[3], bool(cibles) and t[2] not in cibles))
    return [t[:3] for t in index]


# Combien de fois plus peuplé doit être un homonyme d'ailleurs pour qu'une
# adresse à ce nom soit plus probablement la sienne que la nôtre.
HOMONYME_ECRASANT = 10


def homonymes_ecrases(populations: dict, cibles: set,
                      rapport: int = HOMONYME_ECRASANT) -> set:
    """Les noms de nos communes que porte aussi une commune bien plus peuplée.

    `populations` : {(département, nom): habitants}, pour toute la France. À
    nom égal, nos communes passent devant (voir `index_des_communes`), et
    c'est juste quand les homonymes se valent. Mais la Haute-Saône a sa
    Rochelle, d'une quarantaine d'habitants : mesuré le 26 octobre 2026 au
    passage de 8 h 36, 16 des 44 pages IAD ouvertes pour ce département étaient
    des maisons de La Rochelle en Charente-Maritime, et des Saint-Gilles
    d'ailleurs en faisaient autant dans l'Indre. Ces adresses sont traitées
    comme celles que Safti place ailleurs : en dernier, et quelques-unes par
    passage — la maison du hameau finit par être lue.
    """
    chez_nous: dict = {}
    ailleurs: dict = {}
    for (departement, nom), habitants in (populations or {}).items():
        slug = normaliser(nom)
        groupe = chez_nous if departement in cibles else ailleurs
        groupe[slug] = max(groupe.get(slug, 0), habitants or 0)
    return {slug for slug, habitants in chez_nous.items()
            if ailleurs.get(slug, 0) >= rapport * max(habitants, 1)}


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


def annonces_a_visiter(urls: list[str], reseau: dict, index: list,
                       cibles: set | None = None, ecrases: set | None = None) -> list[dict]:
    """Trie les adresses du sitemap : ce qu'on garde, et pourquoi.

    Renvoie un dict par annonce retenue, avec la commune et le département
    déduits — ce que la page elle-même ne donne pas toujours.

    Avec un index de toute la France, `cibles` dit quels départements sont les
    nôtres : le nom le plus long lu dans l'adresse peut désigner une commune
    d'ailleurs, et l'annonce n'est alors pas ouverte. Mesuré le 19 octobre
    2026 au passage de 20 h 24 : 151 des 262 pages IAD ouvertes étaient « hors
    périmètre ». Au fichier, parmi les annonces IAD d'ailleurs que la lecture
    actuelle a fait ouvrir, 186 le devaient à un nom tronqué — Saint-Laurent-
    le-Minier (30) lu « Saint-Laurent », Oloron-Sainte-Marie (64) lu « Sainte-
    Marie » —, contre 65 à un vrai homonyme : l'index ne connaissait que nos
    communes, et ne pouvait savoir qu'un nom plus long existait ailleurs.

    `ecrases` : les noms de nos communes qu'une commune d'ailleurs, bien plus
    peuplée, porte aussi (voir `homonymes_ecrases`).
    """
    # Construite UNE fois, pas une par adresse : c'est tout l'objet du
    # correctif du 19 août.
    table = table_des_communes(index)
    cp_dans_l_adresse = reseau.get("cp_dans_l_adresse")
    departements_cibles = (set(cibles) if cibles
                           else {departement for _, _, departement in index})
    retenues, vues = [], set()
    for url in urls:
        if not reseau["motif_annonce"].search(url):
            continue
        if not TYPES_VOULUS.search(normaliser(urlparse(url).path)):
            continue
        lieu = commune_de_l_adresse(url, index, table)
        if not lieu or lieu[1] not in departements_cibles:
            continue                      # hors des terroirs ciblés
        if url in vues:
            continue
        vues.add(url)
        commune, departement = lieu
        # Le code postal de l'adresse, quand le réseau l'y met, dit si le nom
        # de commune a trompé le tri : « antezant-la-chapelle-17400 » n'est pas
        # La Chapelle des Ardennes. Le bien n'est pas écarté pour autant —
        # l'adresse peut se tromper aussi, une maison de Pacy-sur-Eure est
        # publiée sous un code des Yvelines —, il passe seulement après les
        # autres (voir `ordre_dans_le_departement`).
        code = cp_dans_l_adresse.search(urlparse(url).path) if cp_dans_l_adresse else None
        retenues.append({
            "url": url,
            "commune": commune,
            "departement": departement,
            "agence": nom_d_agence(reseau, departement),
            "hors_cible_selon_l_adresse": bool(
                code and departement_du_code_postal(code.group(1)) not in departements_cibles)
                or normaliser(commune) in (ecrases or ()),
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


def code_postal_confirme(url: str, reseau: dict, titre_de_page: str) -> str | None:
    """Le code postal de l'adresse, quand le titre de la page le donne aussi.

    Sans données structurées, le code postal d'une fiche est deviné : celui qui
    revient le plus dans le texte (voir extraction._code_postal). Or Safti finit
    chaque fiche par des « biens similaires », chacun suivi de son code postal.
    Sur la fiche d'Houlbec-Cocherel, le 78270 de Bennecourt et de ses voisines
    revenait au moins cinq fois, le 27120 de la maison une seule : elle a été
    écartée, le 28 octobre 2026, comme hors de nos terroirs. Mesuré ce jour-là au fichier : 25 des 418 fiches Safti dont le
    titre lu ne porte pas de code postal en avaient un faux, et ces fiches
    sont de plus en plus nombreuses — 351 vues pour la première fois en
    octobre. Le titre de la page, lui, dit « Vente de maison 6 pièces à
    Houlbec-Cocherel 27120 ».

    Les deux sources doivent concorder : une adresse peut garder le nom d'une
    commune que l'annonce a quittée — Chaufour-lès-Bonnières (78270) pour une
    maison de Pacy-sur-Eure.
    """
    motif = reseau.get("cp_dans_l_adresse")
    trouve = motif.search(urlparse(url).path) if motif else None
    if not trouve:
        return None
    code = trouve.group(1)
    return code if code in re.findall(r"(?<!\d)\d{5}(?!\d)", titre_de_page or "") else None


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
    un cran plus bas. « Vue » veut dire OUVERTE, gardée ou non : voir
    `dates_de_derniere_visite`.

    Parmi les jamais vues, celles dont l'adresse dit un code postal hors de
    nos terroirs passent en dernier. Mesuré le 17 octobre 2026 au passage de
    17 h 46 : chez Safti, 92 des 104 pages ouvertes dans l'Aisne, les Ardennes
    et l'Aube étaient des biens d'ailleurs — Bagneux (92), Antezant-la-
    Chapelle (17), Aubeterre-sur-Dronne (16) —, et leur adresse le disait. On
    ne les écarte pas : au fichier, une maison de Pacy-sur-Eure est publiée
    sous un code des Yvelines. Elles attendent seulement leur tour — et
    `lot_du_passage` n'en prend que quelques-unes à chaque passage.
    """
    return sorted(annonces, key=lambda a: (deja_vues.get(a["url"], ""),
                                           bool(a.get("hors_cible_selon_l_adresse")),
                                           a["url"]))


# Pages qu'un passage ouvre, par département, alors que leur adresse les place
# hors de nos terroirs.
HORS_CIBLE_PAR_PASSAGE = 5


def lot_du_passage(candidats: list[dict], maximum: int) -> list[dict]:
    """Les pages qu'un passage ouvre dans un département, dans l'ordre donné.

    Passer en dernier ne suffisait pas : quand un département compte moins de
    pages chez nous que de pages par passage, le reste du lot allait aux
    homonymes. Mesuré le 18 octobre 2026 au passage de 7 h 50 : chez Safti en
    Haute-Marne, 42 des 50 pages ouvertes étaient « hors périmètre » —
    Aigremont (30) pour celui de la Haute-Marne. Leur adresse le disait, comme
    pour les 134 pages Safti refusées pour ce motif depuis la veille, sans une
    exception. Une seule fois sur les 4 890 biens Safti du fichier, l'adresse
    a menti : la maison de Pacy-sur-Eure.

    On en ouvre donc quelques-unes par passage, assez pour que la menteuse
    finisse par être lue, et le reste du lot revient aux pages de chez nous.
    Une page sautée laisse le département « tronqué » : la règle de sortie ne
    retire rien de ce qu'on n'a pas relu.
    """
    lot: list[dict] = []
    hors_cible = 0
    for annonce in candidats:
        if len(lot) >= maximum:
            break
        if annonce.get("hors_cible_selon_l_adresse"):
            if hors_cible >= HORS_CIBLE_PAR_PASSAGE:
                continue
            hors_cible += 1
        lot.append(annonce)
    return lot


def dates_de_derniere_visite(catalogue: dict, ecartees: dict) -> dict:
    """{adresse: dernier jour où on l'a OUVERTE}, gardée ou refusée.

    Le catalogue seul ne connaît que les pages gardées. Une page ouverte et
    refusée — vendue, ou d'une autre région que son nom de commune trompait —
    restait donc « jamais vue », et repassait en tête au passage suivant, par
    ordre alphabétique d'adresse. Mesuré le 17 octobre 2026 en Côte-d'Or :
    50 pages ouvertes, 2 gardées, 9 vendues, 39 « hors périmètre » — des
    Beaulieu du Maine-et-Loire pris pour celui de Côte-d'Or. Les mêmes 48
    pages revenaient à chaque passage, le département n'avançait que de deux
    annonces, et les biens IAD du fichier s'arrêtaient partout à une
    frontière alphabétique : « maison-vente-4-pieces-binges » en Côte-d'Or,
    « 3-pieces-saint-maur » dans l'Indre. Une maison de campagne de cinq
    pièces à Quemigny-sur-Seine, en ligne depuis le 13 août, n'aurait jamais
    été atteinte. La plus récente des deux dates fait foi.
    """
    dates = dict(catalogue)
    for url, constat in (ecartees or {}).items():
        jour = (constat or {}).get("jour", "") if isinstance(constat, dict) else str(constat or "")
        if jour > dates.get(url, ""):
            dates[url] = jour
    return dates


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
