"""Retrouver le site d'une agence que le registre nomme sans l'adresser.

L'étape qui manquait
--------------------
Le recensement connaît 26 452 agences du registre dans notre périmètre, et
**pas une seule** avec un site web : SIRENE donne un nom, une commune et un
SIRET, jamais une adresse en ligne. Ces agences étaient donc parfaitement
connues et parfaitement injoignables. CBF Conseils, à Chalon-sur-Saône, était
dans nos données depuis le recensement — nous n'avions simplement aucun moyen
d'en faire une cible de collecte.

OpenStreetMap, lui, donne le site mais ne recense que ce que quelqu'un a bien
voulu y déclarer : 577 agences sur 30 432. Chercher là seulement, c'était
conclure de ce qu'on n'avait pas cherché — la faute de l'année, sous sa
énième forme.

Ce module fabrique le chaînon : nom d'agence → adresses plausibles, puis
page → est-ce bien elle ? Il ne fait aucun appel réseau (le sondage vit dans
scripts/resoudre_sites.py), ce qui le rend vérifiable hors ligne.

Pourquoi la confirmation compte plus que la génération
------------------------------------------------------
Deviner « cbfconseils.fr » est facile ; se tromper est bien pire que ne rien
trouver. Attribuer à une agence le site d'une autre ferait entrer au catalogue
des biens qu'elle ne vend pas, sous son nom, avec un lien qui trompe le
visiteur — et la règle de sortie, qui croit les cibles visitées, effacerait
ensuite de vraies annonces. Un domaine non trouvé ne coûte qu'une absence ;
un domaine mal attribué corrompt.

La confirmation exige donc le nom DISTINCTIF **et** une seconde concordance
indépendante — la commune ou le SIRET. Le vocabulaire immobilier seul ne
suffit jamais : il y a des milliers de sites d'agences, et celui qu'on tient
doit être celui-là.
"""

from __future__ import annotations

import re
import unicodedata

from .decouverte import PORTAILS_EXCLUS, RESEAUX_NATIONAUX

# Formes juridiques : elles n'entrent jamais dans un nom de domaine.
# « Cabinet » n'y est pas — « Cabinet Ray » s'appelle ainsi en vitrine.
FORMES_JURIDIQUES = re.compile(
    r"\b(sarl|sasu|sas|eurl|sci|scp|snc|selarl|sarlu|eirl|ei|sa)\b", re.IGNORECASE)

# Mots trop répandus pour identifier qui que ce soit. « CBF Conseils » est
# reconnaissable par « cbf », jamais par « conseils » : exiger le mot générique
# ferait correspondre n'importe quelle page d'agence.
MOTS_GENERIQUES = {
    "immobilier", "immobiliere", "immo", "agence", "agences", "conseil",
    "conseils", "gestion", "transaction", "transactions", "cabinet", "groupe",
    "france", "habitat", "patrimoine", "expertise", "services", "et", "de",
    "du", "des", "la", "le", "les", "l", "d",
}

# Vocabulaire d'une vitrine d'agence. Indice d'appoint, jamais une preuve.
VOCABULAIRE_AGENCE = re.compile(
    r"\bnos biens\b|\bnos annonces\b|a vendre\b|\bvente\b|\bestimation\b"
    r"|\bmandat\b|\bhonoraires\b|\bcarte professionnelle\b|\bmaison\b"
    r"|\bappartement\b|\bviager\b|\bbiens? a vendre\b")

# Une page de domaine en vente répète le domaine — donc le nom qui a servi à
# le fabriquer. Sans ce garde-fou, elle se confirmerait toute seule.
DOMAINE_PARQUE = re.compile(
    r"ce domaine est a vendre|domain (is )?for sale|domaine a vendre"
    r"|acheter ce domaine|buy this domain|parkingcrew|sedo\b|afternic"
    r"|cette page est en construction|site en cours de construction")

EXTENSIONS = (".fr", ".com")


def _sans_accents(texte: str) -> str:
    sans = unicodedata.normalize("NFD", texte or "").encode("ascii", "ignore").decode()
    return sans.lower()


def _mots(texte: str) -> list[str]:
    return [m for m in re.split(r"[^a-z0-9]+", _sans_accents(texte)) if m]


def variantes_de_nom(nom: str) -> list[str]:
    """Les appellations d'une même agence, dans l'ordre du plus probable.

    Le registre livre la dénomination légale suivie des noms commerciaux entre
    parenthèses : « JANUS IMMOBILIER (GUY HOQUET L'IMMOBILIER) », « C & M
    GESTION (CIMM GESTION - GEST'IN) ». C'est souvent le nom commercial qui
    porte le domaine, pas le légal — il faut donc essayer les deux.
    """
    brut = nom or ""
    variantes = [re.sub(r"\(.*?\)", " ", brut)]
    for entre in re.findall(r"\((.*?)\)", brut):
        variantes.extend(entre.split(" - "))
    propres = []
    for v in variantes:
        v = FORMES_JURIDIQUES.sub(" ", v)
        v = re.sub(r"\s+", " ", v).strip(" -'")
        if v and v.lower() not in (p.lower() for p in propres):
            propres.append(v)
    return propres


def mots_distinctifs(nom: str) -> list[str]:
    """Ce qui, dans un nom, désigne CETTE agence et pas une autre.

    Les mots d'une lettre sont écartés : « L » de « L'Immobilier » se
    retrouverait dans n'importe quel texte.
    """
    return [m for m in _mots(nom) if m not in MOTS_GENERIQUES and len(m) > 1]


def domaines_plausibles(nom: str, maxi: int = 8) -> list[str]:
    """Adresses à sonder pour cette agence, les plus probables d'abord.

    Deux écritures par variante — collée et à tirets — sur .fr puis .com : ce
    sont, de loin, les formes les plus répandues chez les agences françaises.
    Les têtes de réseau et les portails sont retirés : « JANUS IMMOBILIER
    (GUY HOQUET L'IMMOBILIER) » ne doit pas nous envoyer sur guy-hoquet.com,
    où l'on collecterait les biens de toute la France.
    """
    vus, sortie = set(), []
    for variante in variantes_de_nom(nom):
        mots = [m for m in _mots(variante) if len(m) > 1]
        # Une variante qui ne garde que du générique ne désigne personne :
        # « C & M GESTION » perd ses initiales d'une lettre et produirait
        # « gestion.fr », qui n'est pas plus son domaine que celui de mille
        # autres. On sonde alors les autres variantes du même nom.
        if not mots or not mots_distinctifs(variante):
            continue
        for forme in ("".join(mots), "-".join(mots)):
            for extension in EXTENSIONS:
                candidat = forme + extension
                if (candidat in vus or candidat in RESEAUX_NATIONAUX
                        or candidat in PORTAILS_EXCLUS):
                    continue
                vus.add(candidat)
                sortie.append(candidat)
    return sortie[:maxi]


def confiance(agence: dict, page: str) -> int:
    """Points de concordance entre une page et une agence du registre.

    Le nom distinctif est ÉLIMINATOIRE : sans lui, zéro, quelles que soient
    les autres correspondances. Le reste se cumule, et il en faut une seconde
    au-delà du nom — le vocabulaire immobilier ne vaut qu'un point, jamais le
    seuil à lui seul.
    """
    texte = _sans_accents(page)
    if DOMAINE_PARQUE.search(texte):
        return 0
    distinctifs = mots_distinctifs(agence.get("nom", ""))
    if not distinctifs or not any(m in texte for m in distinctifs):
        return 0
    points = 0
    commune = _sans_accents(agence.get("commune", "")).strip()
    if commune and commune in texte:
        points += 2
    for identifiant in (agence.get("siret"), agence.get("siren")):
        if identifiant and str(identifiant) in re.sub(r"[^0-9]", "", texte):
            points += 2
            break
    if VOCABULAIRE_AGENCE.search(texte):
        points += 1
    return points


SEUIL_CONFIANCE = 3


def est_le_bon_site(agence: dict, page: str) -> bool:
    """Peut-on rattacher cette page à cette agence sans risquer de se tromper ?

    Un « non » ne coûte qu'une agence de plus à trouver autrement. Un « oui »
    erroné fait entrer au catalogue les biens de quelqu'un d'autre sous son
    nom : le doute ne profite pas au candidat.
    """
    return confiance(agence, page) >= SEUIL_CONFIANCE
