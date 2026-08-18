"""Un réseau qui n'aboutit jamais doit tout de même céder son tour.

Le 18 août au matin, le passage mandataires de 3 h a tourné et n'a RIEN écrit
— pas une annonce, pas une ligne au journal de rotation. La trace de passage
posée la veille l'a montré du premier coup : `fichiers_modifies: 0`, alors que
visiter ne serait-ce qu'un département stampe toujours le journal.

L'enchaînement, lisible dans le code :

1. `ordre_des_reseaux` sert d'abord le réseau vu il y a le plus longtemps, et
   un réseau sans aucune entrée au journal compte comme jamais vu.
2. Safti et Capifrance n'ont jamais terminé un seul département — le journal
   ne contenait que des clés `iad:*`. Ils passaient donc devant à CHAQUE fois.
3. Lire les sitemaps d'un réseau coûte plusieurs minutes, et ce coût était
   payé hors budget. Les deux premiers dépensaient leur part sans jamais
   atteindre un département, donc sans rien noter…
4. …donc en restant « jamais vus », donc premiers au passage suivant. Et IAD,
   le seul réseau qui rapportait, arrivait dernier avec un budget vide.

La rotation ajoutée pour donner son tour à Safti a fini par affamer celui qui
produisait. Le correctif ne change pas ce qui est collecté : il note la
TENTATIVE, de sorte qu'avoir eu sa chance suffise à céder la place.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import mandataires  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecter_mandataires", RACINE / "scripts" / "collecter_mandataires.py")
COLLECTEUR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(COLLECTEUR)

RESEAUX = {"capifrance": {}, "iad": {}, "safti": {}}


def test_un_reseau_qui_a_seulement_essaye_cede_son_tour():
    """LE test. Après une tentative notée, le réseau ne repasse plus devant
    ceux qui n'ont pas encore eu la leur."""
    journal = {mandataires.cle_tentative("safti"): "2026-08-18",
               "iad:71": "2026-08-17"}
    ordre = mandataires.ordre_des_reseaux(RESEAUX, journal)
    assert ordre.index("safti") > ordre.index("iad"), (
        "Safti a eu son tour aujourd'hui et repasse pourtant devant IAD, vu "
        "hier : il prendra encore la part de celui qui produit")
    assert ordre[0] == "capifrance", "le jamais essayé doit passer en premier"


def test_sans_la_tentative_le_reseau_sterile_repasse_toujours_devant():
    """L'ancien comportement, gardé sous les yeux : c'est lui qui affamait
    IAD. Un réseau qui ne termine jamais un département reste « jamais vu »."""
    journal = {"iad:71": "2026-08-17"}
    assert mandataires.ordre_des_reseaux(RESEAUX, journal)[0] != "iad", (
        "sans marque de tentative, les réseaux stériles passent devant")
    assert mandataires.derniere_visite_du_reseau("safti", journal) == ""


def test_la_tentative_compte_comme_passage_du_reseau():
    """Elle doit être vue par la rotation des réseaux…"""
    journal = {mandataires.cle_tentative("safti"): "2026-08-18"}
    assert mandataires.derniere_visite_du_reseau("safti", journal) == "2026-08-18"


def test_la_tentative_n_est_pas_prise_pour_un_departement():
    """…et par elle seule. Confondue avec un département, elle ferait croire
    qu'on a visité une cible jamais ouverte — et la règle de sortie supprime
    les annonces des cibles qu'elle croit avoir visitées."""
    journal = {mandataires.cle_tentative("iad"): "2026-08-18"}
    groupes = {"71": [], "21": []}
    ordre = mandataires.ordre_des_departements(groupes, journal, "iad")
    assert set(ordre) == {"21", "71"}, "aucun département inventé"
    assert mandataires.TENTATIVE not in ordre
    for departement in ordre:
        assert journal.get(mandataires.cle_journal("iad", departement), "") == "", (
            "un département réel ne doit rien hériter de la tentative")


def test_le_collecteur_note_sa_tentative_avant_le_premier_departement():
    """La marque doit être posée dès le sitemap lu : un budget épuisé au
    premier département ne doit pas effacer le fait qu'on a essayé."""
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    corps = source[source.index("def collecter_un_reseau"):]
    corps = corps[:corps.index("\ndef ")] if "\ndef " in corps else corps
    marque = corps.index("cle_tentative")
    boucle = corps.index("for dept in mandataires.ordre_des_departements")
    assert marque < boucle, (
        "la tentative est notée après la boucle des départements : un réseau "
        "qui n'en atteint aucun ne la noterait jamais")


def test_un_reseau_sans_budget_ne_lit_meme_pas_ses_sitemaps():
    """Vingt mille adresses téléchargées avec une part déjà vide, c'est le
    temps du réseau suivant qu'on dépense."""
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    corps = source[source.index("def collecter_un_reseau"):]
    garde = corps.index("time.monotonic() > fin_prevue")
    lecture = corps.index("sitemaps_declares")
    assert garde < lecture, (
        "le budget doit être contrôlé avant de lire les sitemaps")
