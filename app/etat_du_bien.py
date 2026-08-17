"""Ce que l'annonce DÉCLARE sur l'état du bien : travaux à prévoir, ou non.

On lit le texte de la page pour en tirer un constat ; on ne le republie
jamais. C'est la même règle que pour la cave, le puits ou le poêle — lire
pour analyser n'est pas rediffuser — et c'est ce qui permet de dire « sans
travaux » sans recopier une ligne de l'agence.

Trois états, et le troisième compte autant que les deux autres :

    "sans_travaux"  l'annonce l'affirme
    "travaux"       l'annonce annonce des travaux
    "inconnu"       l'annonce ne dit rien

Le silence n'est PAS une bonne nouvelle. Sur la tranche 90 000–175 000 €,
cent cinquante-six annonces sur deux cent quatre-vingt-sept ne disent rien de
l'état du bien : les compter comme « sans travaux » ferait passer la page de
cinquante-trois à deux cent neuf entrées, dont les trois quarts seraient une
invention. Une page qui promet « sans travaux » doit ne lister que des biens
qui le disent.

Quatre pièges, tous relevés dans les annonces réelles du catalogue :

- **la dénégation.** « pas de travaux à prévoir », « aucun gros travaux à
  prévoir » contiennent mot pour mot le motif qui annonce des travaux, et
  disent l'inverse. On efface donc les dénégations AVANT de chercher.
- **le passe-partout d'agence.** « des biens plus anciens, avec ou sans
  travaux à prévoir » est un texte de présentation qui ne parle d'aucun bien
  en particulier ; « la prime rénov' » est une aide publique, pas un état.
- **la partie prise pour le tout.** « toiture en bon état », « gros œuvre en
  bon état » ne disent rien du reste — au contraire, on ne vante le gros
  œuvre que lorsque le second œuvre est à refaire.
- **le mot pris dans un autre sens.** « 8 rue de l'État major » est une
  adresse ; « affaire clé en main » et « immédiatement exploitable »
  décrivent un fonds de commerce, pas une maison.
"""

from __future__ import annotations

import re

from .scoring import normaliser

# Les mots qui désignent le bien DANS SON ENSEMBLE. Sans eux, « en bon état »
# peut ne porter que sur la toiture.
_ENTIER = (r"(?:maisons?|biens?|ensemble|propriete|pavillon|longere|fermette"
           r"|villa|habitation|batisse|demeure)")

# … et ceux qui désignent une PARTIE. Une mention d'état accrochée à l'un
# d'eux ne vaut pas pour le bien entier.
_PARTIE = (r"(?:toitures?|toits?|charpentes?|gros oeuvre|materiels?|locaux?"
           r"|facades?|menuiseries|huisseries|fenetres?|chaudieres?"
           r"|couvertures?|installations?|electricite|plomberie|combles?)")

_ETAT = r"(?:tres bon|bon|excellent|parfait) etat"

# Dénégations : « pas de travaux », « aucun gros travaux »… Elles sont
# effacées du texte avant la recherche des travaux, sinon elles la
# déclencheraient en disant le contraire. Le « avec ou » écarte le
# passe-partout d'agence, qui ne parle d'aucun bien en particulier.
DENEGATION = re.compile(
    r"(?<!avec ou )(?:aucun|pas|sans|plus|ni)\s+(?:de\s+|d'|des\s+)?"
    r"(?:gros\s+|grands?\s+|autres?\s+)?travaux\w*")

# Ce qui annonce des travaux.
TRAVAUX = re.compile(
    r"\ba renover\b|\ba restaurer\b|\ba rafraichir\b|\ba moderniser\b"
    r"|travaux\s+(?:a prevoir|a realiser|importants|necessaires"
    r"|de renovation|de rafraichissement|de reamenagement|de remise)"
    r"|prevoir\s+(?:des |quelques |les )?travaux"
    r"|projet de renovation|necessite\w*\s+(?:des |de |quelques )?travaux"
    r"|\bgros oeuvre\b|rafraichissement a prevoir|\ba terminer\b|\ba finir\b")

# Ce qui affirme qu'il n'y en a pas. « clé en main » et « immédiatement
# exploitable » sont volontairement absents : dans ce catalogue, ils ne sont
# apparus que sur des fonds de commerce.
SANS_TRAVAUX = re.compile(
    r"(?<!avec ou )(?:aucun|pas|sans)\s+(?:de\s+|d')?(?:gros\s+)?travaux"
    r"|habitable\s+(?:de suite|immediatement)|pret\w*\s+a habiter"
    r"|entierement renovee?\b|renovee?\s+(?:avec soin|recemment|entierement)"
    r"|refait\w*\s+a neuf|remis\w*\s+a neuf"
    rf"|en {_ETAT} general"
    rf"|etat\s+(?:interieur|general)\s*:?\s*(?:en\s+)?{_ETAT}"
    rf"|{_ENTIER}\s+(?:[\w']+\s+){{0,4}}?en {_ETAT}")

_MOT_DE_PARTIE = re.compile(_PARTIE)

# Le passe-partout d'agence : « des biens plus anciens, avec ou sans travaux à
# prévoir ». Il ne parle d'aucun bien en particulier et doit disparaître AVANT
# les deux recherches — sinon il déclare des travaux pour l'un, ou l'absence de
# travaux pour l'autre, selon la moitié de la phrase qu'on regarde.
PASSE_PARTOUT = re.compile(r"avec ou sans travaux\w*(?:\s+a\s+prevoir)?")


def _texte(bien: dict) -> str:
    brut = normaliser(f"{bien.get('titre') or ''} {bien.get('description') or ''} "
                      f"{bien.get('texte') or ''}")
    return PASSE_PARTOUT.sub(" ", brut)


def _affirme_sans_travaux(texte: str) -> bool:
    """Vrai si une déclaration porte sur le bien ENTIER.

    On parcourt toutes les occurrences plutôt que la première : « maison avec
    toiture en bon état » satisfait la forme « bien entier … en bon état »
    alors que seule la toiture est décrite. Une déclaration dont le texte
    même nomme une partie ne compte pas ; s'il en existe une autre, plus
    loin, qui parle du tout, elle compte.
    """
    return any(not _MOT_DE_PARTIE.search(trouve.group(0))
               for trouve in SANS_TRAVAUX.finditer(texte))


def etat_declare(bien: dict) -> str:
    """« sans_travaux », « travaux », ou « inconnu » — jamais deviné."""
    texte = _texte(bien)
    sans = _affirme_sans_travaux(texte)
    # Les dénégations effacées : « pas de travaux à prévoir » ne doit pas
    # déclencher « travaux à prévoir ».
    avec = bool(TRAVAUX.search(DENEGATION.sub(" ", texte)))
    if sans and not avec:
        return "sans_travaux"
    if avec:
        return "travaux"          # l'annonce parle de travaux : on la croit
    return "inconnu"


def sans_travaux(bien: dict) -> bool:
    """Le bien est-il annoncé sans travaux ? Le doute ne profite pas à la page."""
    return etat_declare(bien) == "sans_travaux"
