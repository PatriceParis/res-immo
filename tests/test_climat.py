"""Le climat de 2050 d'un bien : la bonne maille, ou rien.

Demandé le 12 novembre 2026 : afficher, commune par commune, les journées
caniculaires et les jours de sol sec attendus vers 2050 (projections DRIAS,
trajectoire TRACC). Ces tests fixent trois promesses : le bien est rattaché
à la maille la plus proche, jamais à une maille lointaine ; sans données, la
fiche se tait au lieu d'inventer ; avec données, la fiche le dit et cite sa
source. Le convertisseur est éprouvé sur des fichiers au format exact d'une
extraction DRIAS réelle (relevé le même jour). Aucun test ne lit ni n'écrit
data/climat_2050.json : chacun bâtit ses fichiers dans un dossier temporaire.
"""

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import climat, pages  # noqa: E402
from scripts import importer_drias  # noqa: E402

# Bellême (61) et deux mailles : l'une à 3 km, l'autre à 30 km.
BELLEME = (48.376, 0.565)
GRILLE = {
    "source": "DRIAS (Météo-France), indicateurs TRACC-2023",
    "horizon": "2050",
    "reference": "1976-2005",
    "avertissement": "D'après un seul modèle climatique (X / Y) parmi les 17 de la trajectoire.",
    "points": [
        [48.40, 0.57, {"tmm": [10.64, 12.61], "tx35d": [None, 2.4], "tr": [1.1, 6.8],
                       "swi04d": [41.0, 63.0], "inconnu": [1, 2]}],
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
    assert valeurs == {"tmm": (10.64, 12.61), "tx35d": (None, 2.4), "tr": (1.1, 6.8),
                       "swi04d": (41.0, 63.0)}
    # Dans l'ordre de la fiche : chaleur d'abord, sécheresse ensuite.
    assert [i["code"] for i in projection["indicateurs"]] == ["tmm", "tx35d", "tr", "swi04d"]


def test_une_maille_lointaine_ne_decrit_pas_le_bien(grille):
    # Évreux : à près de 60 km de la maille la plus proche.
    assert climat.au_point(49.02, 1.15) is None


def test_sans_position_ou_sans_donnees_on_se_tait(grille, tmp_path):
    assert climat.au_point(None, 0.565) is None
    illisible = tmp_path / "illisible.json"
    illisible.write_text("{pas du json", encoding="utf-8")
    assert climat.au_point(*BELLEME, chemin=illisible) is None
    assert climat.au_point(*BELLEME, chemin=tmp_path / "absent.json") is None


def test_les_phrases_disent_avant_et_apres_quand_on_le_sait(grille):
    lignes = climat.phrases(climat.au_point(*BELLEME))
    assert lignes == [
        "Température moyenne annuelle : 10,6 °C sur la période 1976-2005, 12,6 °C vers 2050.",
        # L'extraction ne donne pas toujours la référence : on ne l'invente pas.
        "Journées au-delà de 35 °C : 2 par an vers 2050.",
        "Nuits à plus de 20 °C : 1 par an sur la période 1976-2005, 7 par an vers 2050.",
        "Jours de sol sec : 41 par an sur la période 1976-2005, 63 par an vers 2050.",
    ]
    assert climat.phrases(None) == []


def _bien():
    from tests.test_seo import BIEN
    return dict(BIEN)


def test_la_fiche_montre_le_climat_cite_drias_et_avertit(grille):
    html = pages.page_annonce(_bien(), [])
    assert "Le climat de la commune vers 2050" in html
    assert "Journées au-delà de 35 °C" in html
    assert "DRIAS (Météo-France), indicateurs TRACC-2023" in html
    assert "+2,7 °C" in html
    assert "un seul modèle climatique" in html


def test_sans_donnees_la_fiche_n_invente_rien(sans_grille):
    html = pages.page_annonce(_bien(), [])
    assert "vers 2050" not in html


# ---------------------------------------------------------------- conversion

# L'en-tête d'une extraction réelle du 12 novembre 2026, colonnes comprises.
COLONNES = ("Point;Latitude;Longitude;Niveau;Annee;TMm_yr;TMm_seas_JJA;TMm_seas_DJF;"
            "TXm_seas_JJA;TX35D_yr;TX30D_yr;TR_yr;IFM40_yr;SWI04_yr;ECARTTMm_yr;"
            "ECARTTMm_seas_JJA;ECARTTMm_seas_DJF;ECARTTXm_seas_JJA;ECARTRRq99refD_yr;"
            "ECARTIFM40_yr;ECARTSWI04_yr;ECARTRELRR_yr;ECARTRELRR_seas_JJA;"
            "ECARTRELRR_seas_DJF;ECARTRELRRq99_yr;ECARTRELRx1d_yr;")


def _extraction(dossier: Path, modele: str, lignes: list[str], niveau_entete: str = (
        "#     GWL20 (2052-2071) : Niveau de réchauffement Monde 2.0 degrés -> 2050 / "
        "France +2.7°C")) -> Path:
    texte = "\n".join([
        "#-----------------------------------------------------------------------------",
        "# Date d'extraction : 12/11/2026 - 11h07 loc.",
        "# Producteur : MF_DCSC",
        "# Experience : TRACC2023",
        f"# Modele     : {modele}",
        "# Niveaux de réchauffement :",
        niveau_entete,
        "# Type d'indice : annuel",
        "# Format des enregistrements ",
        "# " + COLONNES,
        "#-----------------------------------------------------------------------------",
        *lignes, ""])
    chemin = dossier / f"indices{modele}.txt"
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def _ligne(point, lat, lon, annee, tmm, tx35, swi, ecart_tmm, ecart_swi, niveau="GWL20"):
    # Colonnes non utilisées remplies de zéros ; l'ordre suit COLONNES.
    return (f"{point};{lat};{lon};{niveau};{annee};{tmm};0;0;25;{tx35};20;10;2;{swi};"
            f"{ecart_tmm};0;0;2;0;1;{ecart_swi};0;0;0;0;0;")


def test_la_conversion_moyenne_les_annees_et_deduit_la_reference_des_ecarts(tmp_path):
    fichier = _extraction(tmp_path, "CCLM4-8-17_MPI-ESM", [
        _ligne(1, 48.40, 0.57, 2052, 12.0, 2, 60, 2.0, 20),
        _ligne(1, 48.40, 0.57, 2053, 13.0, 4, 70, 2.4, 30),
        # Ajaccio : hors de la zone servie, écarté.
        _ligne(2, 41.93, 8.74, 2052, 17.0, 9, 200, 2.0, 50),
    ])
    resultat = importer_drias.convertir([fichier])
    assert len(resultat["points"]) == 1
    lat, lon, valeurs = resultat["points"][0]
    assert (lat, lon) == (48.4, 0.57)
    assert valeurs["tmm"] == [10.3, 12.5]          # 12,5 - 2,2 d'écart moyen
    assert valeurs["swi04d"] == [40.0, 65.0]       # 65 - 25
    # Pas de colonne d'écart pour TX35D dans cette extraction : pas de référence.
    assert valeurs["tx35d"] == [None, 3.0]
    assert "un seul modèle climatique (CCLM4-8-17 / MPI-ESM)" in resultat["avertissement"]


def test_plusieurs_modeles_donnent_la_mediane(tmp_path):
    fichiers = [
        _extraction(tmp_path, modele, [_ligne(1, 48.40, 0.57, 2052, tmm, tx35, 60, 2.0, 20)])
        for modele, tmm, tx35 in (("A_X", 12.0, 2), ("B_Y", 13.0, 6), ("C_Z", 15.0, 3))]
    valeurs = importer_drias.convertir(fichiers)["points"][0][2]
    assert valeurs["tmm"][1] == 13.0
    assert valeurs["tx35d"][1] == 3.0
    assert "Médiane de 3 modèles" in importer_drias.convertir(fichiers)["avertissement"]


def test_une_extraction_de_la_periode_de_reference_donne_la_reference(tmp_path):
    futur = _extraction(tmp_path, "A_X", [_ligne(1, 48.40, 0.57, 2052, 12.0, 4, 60, 2.0, 20)])
    (tmp_path / "ref").mkdir()
    passe = _extraction(tmp_path / "ref", "A_X_ref",
                        [_ligne(1, 48.40, 0.57, 1990, 10.0, 1, 40, 0, 0, niveau="REF")],
                        niveau_entete="#     REF (1976-2005) : Période de référence")
    valeurs = importer_drias.convertir([futur, passe])["points"][0][2]
    assert valeurs["tx35d"] == [1.0, 4.0]


def test_le_fichier_converti_se_lit_par_la_fiche(tmp_path, monkeypatch):
    fichier = _extraction(tmp_path, "A_X", [_ligne(1, 48.40, 0.57, 2052, 12.0, 4, 60, 2.0, 20)])
    sortie = tmp_path / "climat_2050.json"
    assert importer_drias.main([str(fichier), "--sortie", str(sortie)]) == 0
    climat._grille.cache_clear()
    projection = climat.au_point(*BELLEME, chemin=sortie)
    assert projection and projection["indicateurs"][0]["code"] == "tmm"
    climat._grille.cache_clear()


# La médiane des 17 modèles, telle que DRIAS la livre (« Quantiles… », Q50) :
# une ligne par point, sans colonne Annee, colonnes NOR… et A… (relevé sur
# l'extraction réelle du 12 novembre 2026).
COLONNES_Q50 = ("Point;Latitude;Longitude;Niveau;NORTMm_yr;NORTXm_seas_JJA;NORTX35D_yr;"
                "NORTX30D_yr;NORTR_yr;NORRR_seas_JJA;NORIFM40_yr;NORSWI04_yr;ATMm_yr;"
                "ATXm_seas_JJA;ATX35D_yr;ATX30D_yr;ATR_yr;AIFM40_yr;ASWI04_yr;ARRR_seas_JJA;")


def _mediane(dossier: Path, lignes: list[str]) -> Path:
    texte = "\n".join([
        "# Experience : TRACC2023_DISTRIBUTION",
        "# Modele     : Q50",
        "#     GWL20 : Niveau de réchauffement Monde 2.0 degrés -> 2050 / France +2.7°C",
        "# " + COLONNES_Q50, *lignes, ""])
    chemin = dossier / "indicesQ50.txt"
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def test_la_mediane_des_modeles_donne_la_reference_des_jours_de_chaleur(tmp_path):
    q50 = _mediane(tmp_path, [
        # tmm 12,6 (écart 2,1) ; tx35d 2,4 (écart 1,9) ; pluie d'été 160 mm, -20 %
        "1;48.40;0.57;GWL20;12.6;24.6;2.4;15.2;9.8;160;3;145;2.1;2.7;1.9;9.1;8.6;2;29;-0.2;",
    ])
    # Un modèle isolé fourni en même temps ne fausse pas la médiane.
    isole = _extraction(tmp_path, "A_X", [_ligne(1, 48.40, 0.57, 2052, 20.0, 50, 60, 2.0, 20)])
    resultat = importer_drias.convertir([isole, q50])
    valeurs = resultat["points"][0][2]
    assert valeurs["tmm"] == [10.5, 12.6]
    assert valeurs["tx35d"] == [0.5, 2.4]
    assert valeurs["tx30d"] == [6.1, 15.2]
    assert valeurs["rr_jja"] == [200.0, 160.0]
    assert valeurs["swi04d"] == [116.0, 145.0]
    assert resultat["modeles"] == ["Q50"]
    assert "Médiane des 17 modèles" in resultat["avertissement"]
