"""Tests de l'audit des données (scripts/auditer.py).

Un audit qui crie au loup pour rien finit ignoré — et le jour où il signale
une vraie erreur, personne ne regarde. Ces tests fixent la frontière entre
ce qu'il doit voir et ce qu'il doit laisser passer.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location("auditer", RACINE / "scripts" / "auditer.py")
auditer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(auditer)

ville_du_titre = auditer.ville_du_titre


def test_la_commune_du_titre_est_reconnue():
    """Le cas qui justifie la règle : sept offres de constructeur annoncées
    à Oslon, Seurre, Chenôves, toutes enregistrées au siège de l'entreprise."""
    assert ville_du_titre("Maison 3 chambres + Terrain à Oslon !") == "Oslon"
    assert ville_du_titre(
        "Acheter maison de 6 pièces 107 m² 63 500 € à Dissay-sous-Courcillon (72500)"
    ) == "Dissay-sous-Courcillon"
    assert ville_du_titre("Maison mitoyenne 6 pièces à Mérigny !") == "Mérigny"


def test_ce_qui_suit_de_n_est_pas_toujours_une_commune():
    """« Maison de Maître » désignait la commune « Maître »."""
    assert ville_du_titre("Maison de Maître - 6 chambres - Parc arboré") is None
    assert ville_du_titre("Monts - Baisse de Prix") is None
    assert ville_du_titre("Charmante maison de Caractère avec jardin") is None


def test_une_ville_citee_pour_situer_le_bien_n_est_pas_sa_commune():
    """« à 15 mn de Bellême » dit justement que le bien n'est PAS à Bellême.

    La longère est à Val-au-Perche : les deux informations sont exactes, et
    l'audit les signalait comme une contradiction.
    """
    assert ville_du_titre(
        "Authentique longère au cœur du Perche à 15 mn de Bellême") is None
    assert ville_du_titre(
        "Charmante maison de caractère dans un village, à 5 minutes de Bellême") is None
    assert ville_du_titre("Fermette rénovée proche de Nogent-le-Rotrou") is None
    # Mais une adresse franche reste une adresse.
    assert ville_du_titre(
        "Maison en pierre avec jardin et garage à Bellême (61130)") == "Bellême"
