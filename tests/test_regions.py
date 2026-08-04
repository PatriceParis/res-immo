"""Tests du classement de résilience des régions (priorisation des terroirs)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import regions  # noqa: E402


def test_cinq_terroirs_cibles():
    cibles = regions.regions_cibles()
    assert len(cibles) == 5
    # L'Île-de-France est volontairement écartée (la moins résiliente).
    assert "Île-de-France" not in cibles


def test_classement_ordonne_et_total_coherent():
    cl = regions.classement()
    totaux = [r["total"] for r in cl]
    assert totaux == sorted(totaux, reverse=True)  # trié par indice décroissant
    for r in cl:
        assert r["total"] == sum(r["axes"].values())
    assert cl[0]["rang"] == 1


def test_normandie_en_tete():
    cl = regions.classement()
    assert cl[0]["region"] == "Normandie"
    assert cl[0]["cible"] is True


def test_ile_de_france_derniere_et_non_cible():
    cl = regions.classement()
    derniere = cl[-1]
    assert derniere["region"] == "Île-de-France"
    assert derniere["cible"] is False


def test_region_du_departement():
    assert regions.region_du_departement("61") == "Normandie"
    assert regions.region_du_departement("58") == "Bourgogne-Franche-Comté"
    assert regions.region_du_departement("10") == "Grand Est"
    assert regions.region_du_departement(28) == "Centre-Val de Loire"   # int accepté
    assert regions.region_du_departement("99") is None


def test_ile_de_france_exclue_du_perimetre():
    """L'Île-de-France est 6e au classement : elle n'est pas une cible.

    Sans cette exclusion, les agences frontalières y ramenaient des biens
    (La Ferté-sous-Jouarre, Nangis) que l'application doit écarter.
    """
    from app.chargement import DEPARTEMENTS_CIBLES

    assert "Île-de-France" not in regions.regions_cibles()
    for dept in ("75", "77", "78", "91", "92", "93", "94", "95"):
        assert dept not in DEPARTEMENTS_CIBLES, f"{dept} (IdF) ne doit pas être ciblé"
    # Les terroirs visés, eux, sont bien présents.
    for dept in ("61", "60", "41", "89", "10", "02", "37"):
        assert dept in DEPARTEMENTS_CIBLES
