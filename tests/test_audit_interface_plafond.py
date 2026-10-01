"""L'audit de l'interface juge l'écran contre le plafond de l'écran, pas celui
de l'API — et l'effet d'une case sur des totaux que rien ne tronque.

Mesuré le 1er octobre, en rejouant l'audit dans un navigateur : six cases sur
six déclarées inopérantes — « 250 fiche(s) affichée(s) pour 3 877 attendue(s) »
— alors que l'interface tenait parole. L'audit comparait l'écran à
min(attendu, 500), le plafond de l'API ; l'accueil n'affiche que 250 fiches
depuis le 28 août et le dit dans son compteur. Et avant cela, le 13 août,
« ne retire aucun bien (500 avant comme après) » : deux comptes d'écran tous
deux butés sur le plafond, comparés entre eux. Première des deux causes qui
ont tenu « Vérification » au rouge sept semaines.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "auditer_interface", RACINE / "scripts" / "auditer_interface.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def test_le_plafond_se_lit_sur_la_page_qui_l_annonce():
    assert audit.plafond_d_affichage(250, 8281, "8 281 biens · 250 premiers affichés") == 250
    assert audit.plafond_d_affichage(37, 37, "37 biens") is None, "rien n'est tronqué"
    assert audit.plafond_d_affichage(250, 8281, "8 281 biens") is None, (
        "moins de fiches que de biens SANS l'annoncer : ce n'est pas un plafond, "
        "c'est une anomalie que le premier contrôle signale déjà")


def test_l_ecran_est_juge_contre_son_propre_plafond():
    """Le cas du 1er octobre : 3 877 biens avec cave, 250 fiches à l'écran."""
    assert audit.attendu_a_l_ecran(3877, 250) == 250
    assert audit.attendu_a_l_ecran(37, 250) == 37
    assert audit.attendu_a_l_ecran(3877, None) == 3877


def test_une_case_inoperante_se_voit_sur_les_totaux_quel_que_soit_le_plafond():
    """Le cas du 13 août : 500 avant comme après à l'écran, mais 3 877 biens
    avec la case contre 8 281 sans — la case filtre bel et bien."""
    assert not audit.case_sans_effet(3877, 8281)
    assert audit.case_sans_effet(8281, 8281), "même total avec et sans : inerte"
    assert not audit.case_sans_effet(12, 12), (
        "sur une poignée de biens, tous peuvent avoir une cave : pas un défaut")
