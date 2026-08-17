"""Safti et Capifrance étaient configurés depuis toujours, et jamais lus.

Zéro annonce des deux au catalogue, et le journal des visites ne contenait que
des cibles IAD. Ni panne ni blocage : les trois réseaux étaient parcourus dans
l'ordre alphabétique, avec une SEULE échéance commune. Capifrance passait en
premier et s'abstenait faute de sitemap déclaré, IAD prenait tout le budget,
et Safti — dernier de l'alphabet — n'avait jamais son tour.

C'est la troisième fois que cette forme revient : un ordre fixe et un budget
partagé, et la queue de liste n'est jamais servie. Century 21, puis les
départements ce matin, puis les réseaux. La parade est la même à chaque fois :
servir d'abord ce qu'on a vu il y a le plus longtemps, et découper le temps
pour que le premier ne mange pas la part des suivants.

Ces tests tiennent les deux sens : donner son tour au réseau oublié, sans
émietter le budget quand un seul réseau est demandé.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import mandataires  # noqa: E402

RESEAUX = {"capifrance": {}, "iad": {}, "safti": {}}


def test_un_reseau_jamais_lu_passe_devant():
    """LE cas. Safti n'a aucune cible au journal : il doit ouvrir la marche,
    pas la fermer."""
    vu = {"iad:71": "2026-08-17", "iad:37": "2026-08-16",
          "capifrance:28": "2026-08-15"}
    assert mandataires.ordre_des_reseaux(RESEAUX, vu)[0] == "safti"


def test_l_ordre_suit_l_anciennete_et_non_l_alphabet():
    """L'ordre alphabétique est ce qui a privé Safti de son tour pendant des
    semaines : il ne doit plus décider de rien."""
    vu = {"capifrance:28": "2026-08-17", "iad:71": "2026-08-10",
          "safti:71": "2026-08-14"}
    assert mandataires.ordre_des_reseaux(RESEAUX, vu) == ["iad", "safti", "capifrance"]


def test_la_date_d_un_reseau_est_la_plus_recente_de_ses_cibles():
    """Un réseau compte soixante-neuf cibles départementales. Prendre la plus
    ANCIENNE le ferait paraître délaissé alors qu'on y est passé ce matin, et
    il repasserait devant à chaque tour."""
    vu = {"iad:71": "2026-08-17", "iad:02": "2026-07-01"}
    assert mandataires.derniere_visite_du_reseau("iad", vu) == "2026-08-17"
    assert mandataires.derniere_visite_du_reseau("safti", vu) == ""


def test_un_prefixe_de_reseau_n_en_attrape_pas_un_autre():
    """« iad » ne doit pas capter « iadfrance:71 » ni l'inverse : le journal
    est indexé par « réseau:département », le deux-points fait la frontière."""
    vu = {"iadfrance:71": "2026-08-17"}
    assert mandataires.derniere_visite_du_reseau("iad", vu) == ""


# --- le partage du temps ---------------------------------------------------

def test_le_premier_reseau_ne_mange_pas_la_part_des_suivants():
    """Vingt minutes pour trois réseaux : le premier en prend le tiers.
    Sans ce découpage, IAD prenait les vingt et Safti n'existait pas."""
    assert mandataires.part_de_budget(1200, 3) == 400


def test_le_temps_rendu_par_un_reseau_muet_profite_aux_suivants():
    """Capifrance s'abstient en quelques secondes faute de sitemap déclaré.
    Sa part ne doit pas être perdue : le calcul se refait à chaque réseau, sur
    ce qui RESTE, donc les suivants récupèrent tout."""
    assert mandataires.part_de_budget(1190, 2) == 595


def test_un_seul_reseau_demande_garde_tout_le_budget():
    """L'excès inverse. Un rattrapage lance `--reseau iad` : lui rogner les
    deux tiers du temps saborderait précisément ce qu'on est venu faire."""
    assert mandataires.part_de_budget(1200, 1) == 1200


def test_un_budget_deja_epuise_ne_devient_pas_negatif():
    """Un temps négatif rendrait l'échéance antérieure à maintenant, et le
    réseau serait sauté sans qu'on sache pourquoi."""
    assert mandataires.part_de_budget(-30, 2) == 0
    assert mandataires.part_de_budget(600, 0) == 600
