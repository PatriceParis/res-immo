"""Ce que plusieurs tests se partagent — et d'abord une base qui leur appartient.

Deux tests interrogeaient les pages servies sans se donner de données : ils
lisaient la base PAR DÉFAUT, data/refuge.db. Pleine sur toute machine de
développement, vide en CI — où « /petits-prix » répondait un 404 sans bien,
et où ces deux tests ont échoué à chaque push du 17 août au 1er octobre sans
que personne lise pourquoi. Un test qui dépend d'un fichier que la machine a
ou n'a pas ne teste pas le code : il teste la machine.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

# Un bien qui passe tous les filtres des pages servies : sous le seuil des
# petits prix (100 000 €), dans la tranche « sans travaux » (90 000–175 000 €)
# et déclaré tel par son texte, en Normandie, à moins de 350 km de Paris.
UN_BIEN_SERVI = {
    "id": "conftest-x1", "source": "agence-test", "type_bien": "maison",
    "titre": "Maison 5 pièces à Bellême", "agence": "Agence Test",
    "agence_url": "https://agence-test.fr", "url": "https://agence-test.fr/bien/x1",
    "texte": "Maison en très bon état général, aucun travaux à prévoir.",
    "prix": 95000, "surface_m2": 120, "terrain_m2": 900, "pieces": 5,
    "commune": "Bellême", "code_postal": "61130", "departement": "61",
    "lat": 48.373, "lon": 0.561,
}


@pytest.fixture()
def base_avec_un_bien(tmp_path, monkeypatch) -> dict:
    """Une base temporaire qui contient UN_BIEN_SERVI, et rien d'autre.

    La base est désignée par REFUGE_DB, que l'application lit à chaque
    connexion : les pages servies pendant le test ne voient que ce bien.
    """
    from app import db
    from app.chargement import charger_liste

    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "un_bien.db"))
    conn = db.connexion()
    charges = charger_liste(conn, [UN_BIEN_SERVI])
    conn.close()
    assert charges == 1, "le bien témoin doit passer les filtres de chargement"
    return UN_BIEN_SERVI
