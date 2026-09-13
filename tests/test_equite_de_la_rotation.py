"""Un tri alphabétique affamait 39 % du catalogue, sans rien casser.

Le vérificateur de liens tourne chaque nuit depuis le 18 août. Un mois plus
tard, relevé par domaine :

    iadfrance.fr   2 549 annonces   855 vérifiées   34 %
    safti.fr       2 784 annonces     0 vérifiée     0 %

Toute la fin de l'alphabet était à zéro, et la frontière tombait au milieu
d'iadfrance — exactement là où le budget quotidien s'épuisait. Rien
n'échouait : les passages se terminaient bien, les journaux se remplissaient,
et 2 784 annonces n'étaient simplement jamais regardées.

La cause tenait à la troisième clé de tri. Les jamais-vérifiés partagent tous
la même date vide, il fallait bien les départager — c'était l'URL, donc
l'ordre alphabétique du domaine, donc `i` avant `s`.

Et ce n'était pas un retard que le temps aurait résorbé : le catalogue
absorbe ~170 annonces par jour quand le passage en vérifie ~60. La file des
jamais-vérifiés s'allonge de cent par jour, et chaque nouvelle annonce d'un
domaine mieux placé dans l'alphabet repasse devant celles qui attendaient.
Safti n'attendait pas son tour : il ne l'aurait jamais eu.

La leçon est la même que pour le titre de Safti (test_titre_de_safti.py) :
une erreur qui ne produit pas d'échec produit un SILENCE, et un silence
ressemble à une absence.
"""

import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import liens  # noqa: E402

LOT = 150  # le budget d'un passage, cf. scripts/verifier_liens.py --max


def catalogue(**tailles: int) -> list[dict]:
    """Un catalogue où chaque domaine pèse le nombre d'annonces demandé."""
    return [{"url": f"https://www.{domaine}/annonce/{n}"}
            for domaine, taille in tailles.items()
            for n in range(taille)]


def domaines(annonces: list[dict]) -> Counter:
    return Counter(urlparse(a["url"]).netloc.removeprefix("www.")
                   for a in annonces)


def test_le_gros_domaine_de_fin_d_alphabet_est_servi_des_le_premier_lot():
    """LE test. Les proportions sont celles du catalogue au 13 septembre."""
    annonces = catalogue(**{"iadfrance.fr": 2549, "safti.fr": 2784})
    lot = liens.ordre_de_verification(annonces, {}, {})[:LOT]
    assert domaines(lot)["safti.fr"] > 0, (
        "safti.fr reste à zéro : le lot part encore dans l'ordre alphabétique")


def test_la_part_de_chaque_domaine_suit_sa_taille():
    """Servir tout le monde ne suffit pas : un domaine qui pèse 39 % du
    catalogue doit recevoir ~39 % du budget, pas une annonce par tour."""
    annonces = catalogue(**{"iadfrance.fr": 2549, "safti.fr": 2784,
                            "century21estagence.com": 27})
    lot = domaines(liens.ordre_de_verification(annonces, {}, {})[:LOT])
    total = 2549 + 2784 + 27
    for domaine, taille in (("safti.fr", 2784), ("iadfrance.fr", 2549)):
        attendu = LOT * taille / total
        assert abs(lot[domaine] - attendu) <= 2, (
            f"{domaine} reçoit {lot[domaine]} liens sur {LOT}, "
            f"au lieu des ~{attendu:.0f} que sa taille lui vaut")


def test_un_petit_domaine_ne_prend_pas_la_place_des_gros():
    """Le symétrique : un tour de rôle strict (un par domaine) donnerait
    100 % de couverture aux miettes et des miettes aux gros. Vingt domaines
    de dix annonces ne doivent pas confisquer un lot de cent cinquante."""
    petits = {f"agence{n:02d}.fr": 10 for n in range(20)}
    annonces = catalogue(**{"safti.fr": 2784}, **petits)
    lot = domaines(liens.ordre_de_verification(annonces, {}, {})[:LOT])
    assert lot["safti.fr"] > LOT * 0.8, (
        f"safti.fr ne prend que {lot['safti.fr']} liens sur {LOT} alors qu'il "
        "pèse 93 % du catalogue")


def test_les_suspects_passent_toujours_devant():
    """La raison d'être de la rotation ne doit pas disparaître avec le
    correctif : un constat de mort en attente reste prioritaire, sinon sa
    confirmation attend un tour complet."""
    annonces = catalogue(**{"iadfrance.fr": 400, "safti.fr": 400})
    suspect = annonces[-1]["url"]  # un safti, le plus mal placé qui soit
    ordre = liens.ordre_de_verification(annonces, {}, {suspect: {"constats": 1}})
    assert ordre[0]["url"] == suspect


def test_dans_un_domaine_les_jamais_vus_passent_avant_les_anciens():
    """L'ordre promis à l'intérieur d'un domaine est intact."""
    annonces = catalogue(**{"safti.fr": 3})
    jamais_vu = annonces[2]["url"]
    verifies = {annonces[0]["url"]: "2026-09-01",
                annonces[1]["url"]: "2026-08-01"}
    ordre = [a["url"] for a in liens.ordre_de_verification(annonces, verifies, {})]
    assert ordre == [jamais_vu, annonces[1]["url"], annonces[0]["url"]]


def test_le_lot_est_reproductible():
    """Deux domaines de même taille ne doivent pas s'ordonner au hasard :
    un passage doit pouvoir être rejoué à l'identique."""
    annonces = catalogue(**{f"agence{n}.fr": 50 for n in range(6)})
    premier = [a["url"] for a in liens.ordre_de_verification(annonces, {}, {})]
    second = [a["url"] for a in liens.ordre_de_verification(annonces[::-1], {}, {})]
    assert premier == second
