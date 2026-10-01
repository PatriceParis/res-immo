"""Le chargement doit retrouver, sans le texte, tout ce qu'il y lisait.

Depuis le 1er octobre, le fichier publié ne porte plus le texte des pages
(voir scripts/exporter_reel.py et tests/test_export.py) : il porte ce qu'on y
a lu à la collecte. Le chargement, qui relisait la page à chaque démarrage,
doit désormais HÉRITER de ces constats — et ne pas les écraser avec ce qu'il
peut encore lire, c'est-à-dire presque rien : un titre, parfois un descriptif.

La régression d'août 2026 est exactement ce qui arriverait sans ces tests :
un fichier sans texte, un chargement qui relit, et des scores qui
s'effondrent sans erreur visible.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement, qualite  # noqa: E402


def test_le_chargement_garde_ce_qui_a_ete_vu_sur_la_page():
    annonce = chargement.preparer_annonce({
        "id": "x", "titre": "Maison", "description": "",
        "features": {"cave": True, "puits": True}, "etat_declare": "sans_travaux",
        "prix": 150000, "surface_m2": 120, "code_postal": "61130",
    })
    assert annonce["features"]["cave"] and annonce["features"]["puits"]
    assert annonce["has_cave"] == 1 and annonce["has_puits"] == 1
    assert annonce["etat_declare"] == "sans_travaux" and annonce["sans_travaux"] == 1


def test_ce_que_le_chargement_relit_s_ajoute_sans_rien_effacer():
    annonce = chargement.preparer_annonce({
        "id": "x", "titre": "Maison avec poêle à bois", "features": {"cave": True},
        "prix": 150000, "code_postal": "61130",
    })
    assert annonce["features"]["cave"], "ce qui a été vu sur la page reste vu"
    assert annonce["features"]["bois"], "ce qu'on relit dans le titre s'ajoute"


def test_a_la_collecte_rien_n_est_herite_et_la_page_est_lue():
    """Un bien frais n'a ni `features` ni `etat_declare` : la page fait foi."""
    annonce = chargement.preparer_annonce({
        "id": "x", "titre": "Maison", "texte": "Cave voûtée. Travaux à prévoir.",
        "prix": 150000, "code_postal": "61130",
    })
    assert annonce["features"]["cave"] and annonce["etat_declare"] == "travaux"


def test_un_etat_herite_qui_n_est_pas_un_des_trois_est_recalcule():
    annonce = chargement.preparer_annonce({
        "id": "x", "titre": "Maison à rénover", "etat_declare": "n'importe quoi",
        "prix": 150000, "code_postal": "61130",
    })
    assert annonce["etat_declare"] == "travaux"


def test_une_page_catalogue_reste_ecartee_sans_son_texte():
    assert qualite.enumere_plusieurs_biens({"plusieurs_biens": True}) is True
    assert qualite.enumere_plusieurs_biens({"plusieurs_biens": False}) is False
    assert qualite.enumere_plusieurs_biens({}) is False
    # La page entière, quand elle est là, fait foi — dans les deux sens.
    assert qualite.enumere_plusieurs_biens(
        {"texte": "Réf. 101 Réf. 202 Réf. 303", "plusieurs_biens": False}) is True
    assert qualite.enumere_plusieurs_biens(
        {"texte": "Réf. 101", "plusieurs_biens": True}) is False


def test_un_bien_vendu_reste_ecarte_sans_son_texte():
    assert qualite.est_vendu({"vendu": True}) is True
    assert qualite.est_vendu({"vendu": False, "description": ""}) is False
