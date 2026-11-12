"""Le climat de 2050 d'un bien : la bonne maille, ou rien.

Demandé le 12 novembre 2026 : afficher, commune par commune, les journées
caniculaires et les jours de sol sec attendus vers 2050 (projections DRIAS,
trajectoire TRACC). Ces tests fixent trois promesses : le bien est rattaché
à la maille la plus proche, jamais à une maille lointaine ; sans données, la
fiche se tait au lieu d'inventer ; avec données, la fiche le dit et cite sa
source. Aucun test ne lit ni n'écrit data/climat_2050.json : chacun bâtit sa
grille dans un dossier temporaire.
"""

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import climat, pages  # noqa: E402

# Bellême (61) et deux mailles : l'une à 3 km, l'autre à 30 km.
BELLEME = (48.376, 0.565)
GRILLE = {
    "source": "DRIAS-2020, Météo-France",
    "horizon": "2050",
    "reference": "1976-2005",
    "points": [
        [48.40, 0.57, {"tx35d": [0.4, 3.2], "tr": [1.1, 6.8], "swi04d": [41.0, 63.0],
                       "inconnu": [1, 2]}],
        [48.65, 0.57, {"tx35d": [9.0, 99.0]}],
    ],
}


@pytest.fixture
def grille(tmp_path, monkeypatch):
    chemin = tmp_path / "climat_2050.json"
    chemin.write_text(json.dumps(GRILLE), encoding="utf-8")
    monkeypatch.setattr(climat, "FICHIER", chemin)
    climat._grille.cache_clear()
    yield chemin
    climat._grille.cache_clear()


@pytest.fixture
def sans_grille(tmp_path, monkeypatch):
    monkeypatch.setattr(climat, "FICHIER", tmp_path / "absent.json")
    climat._grille.cache_clear()
    yield
    climat._grille.cache_clear()


def test_le_bien_prend_la_maille_la_plus_proche(grille):
    projection = climat.au_point(*BELLEME)
    assert projection["distance_km"] < 5
    valeurs = {i["code"]: (i["reference"], i["horizon"]) for i in projection["indicateurs"]}
    # La maille à 30 km (99 journées) n'est pas la nôtre ; un code inconnu
    # n'est pas affiché.
    assert valeurs == {"tx35d": (0.4, 3.2), "tr": (1.1, 6.8), "swi04d": (41.0, 63.0)}
    # Dans l'ordre de la fiche : chaleur d'abord, sécheresse ensuite.
    assert [i["code"] for i in projection["indicateurs"]] == ["tx35d", "tr", "swi04d"]


def test_une_maille_lointaine_ne_decrit_pas_le_bien(grille):
    # Évreux : à près de 60 km de la maille la plus proche.
    assert climat.au_point(49.02, 1.15) is None


def test_sans_position_ou_sans_donnees_on_se_tait(grille, tmp_path):
    assert climat.au_point(None, 0.565) is None
    illisible = tmp_path / "illisible.json"
    illisible.write_text("{pas du json", encoding="utf-8")
    assert climat.au_point(*BELLEME, chemin=illisible) is None
    assert climat.au_point(*BELLEME, chemin=tmp_path / "absent.json") is None


def test_les_phrases_disent_avant_et_apres(grille):
    lignes = climat.phrases(climat.au_point(*BELLEME))
    assert lignes[0] == ("Journées au-delà de 35 °C : moins de 1 par an sur la période "
                         "1976-2005, 3 vers 2050.")
    assert lignes[2] == ("Jours de sol sec : 41 par an sur la période 1976-2005, "
                         "63 vers 2050.")
    assert climat.phrases(None) == []


def _bien():
    from tests.test_seo import BIEN
    return dict(BIEN)


def test_la_fiche_montre_le_climat_et_cite_drias(grille):
    html = pages.page_annonce(_bien(), [])
    assert "Le climat de la commune vers 2050" in html
    assert "Journées au-delà de 35 °C" in html
    assert "DRIAS-2020, Météo-France" in html
    assert "+2,7 °C" in html


def test_sans_donnees_la_fiche_n_invente_rien(sans_grille):
    html = pages.page_annonce(_bien(), [])
    assert "vers 2050" not in html
