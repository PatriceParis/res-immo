"""Tests du classement de résilience des régions (priorisation des terroirs)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import regions  # noqa: E402


def test_tous_les_terroirs_cibles_sauf_l_ile_de_france():
    """La règle est « on écarte l'Île-de-France », pas « on en garde cinq ».

    Le compte était figé à 5 : ajouter une 7e région faisait silencieusement
    sortir de la cible le Centre-Val de Loire — d'où viennent les troglodytes
    et le Vendômois — et ses biens auraient disparu du site.
    """
    cibles = regions.regions_cibles()
    assert "Île-de-France" not in cibles
    assert set(cibles) == {r["region"] for r in regions.REGIONS} - {"Île-de-France"}


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


def test_tout_departement_accepte_a_un_terroir_d_accueil():
    """Un bien accepté doit être atteignable par le filtre de région.

    La Sarthe et la Mayenne étaient acceptées en dur, sans appartenir à
    aucune région du classement : leurs 16 biens étaient comptés dans
    « 133 biens trouvés » mais rattachés à aucune pastille de terroir —
    donc introuvables. Le total et la somme des pastilles ne collaient plus.
    """
    from app.chargement import DEPARTEMENTS_CIBLES

    cibles = set(regions.regions_cibles())
    for dept in DEPARTEMENTS_CIBLES:
        region = regions.region_du_departement(dept)
        assert region in cibles, f"{dept} accepté mais rattaché à {region!r}"


def test_le_perche_sarthois_est_couvert():
    """Le Perche ne s'arrête pas à la frontière de l'Orne — et Le Mans est la
    meilleure desserte TGV de toute la sélection (55 min)."""
    from app.chargement import DEPARTEMENTS_CIBLES

    assert regions.region_du_departement("72") == "Pays de la Loire"
    assert regions.region_du_departement("53") == "Pays de la Loire"
    assert {"72", "53"} <= DEPARTEMENTS_CIBLES
