"""Tests du moteur de classification (détection + barème)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import scoring  # noqa: E402


def test_detection_equipements_avec_accents():
    criteres = scoring.extraire_criteres(
        "Fermette avec cave et dépendances",
        "Belle cave voûtée. Puits dans la cour, poêle à bois, verger d'arbres "
        "fruitiers et panneaux solaires photovoltaïques. Grange attenante.",
    )
    assert criteres["cave"]
    assert criteres["puits"]
    assert criteres["bois"]
    assert criteres["verger_potager"]
    assert criteres["solaire"]
    assert criteres["grange_dependance"]
    assert not criteres["serre"]


def test_le_mot_caverne_ne_declenche_pas_cave():
    criteres = scoring.extraire_criteres("Maison", "À deux pas de cavernes touristiques.")
    assert not criteres["cave"]


def test_score_borne_0_100():
    tout = {c: True for c in scoring.MOTIFS}
    detail = scoring.calculer_score({
        "features": tout, "risques": {}, "terrain_m2": 20000,
        "altitude": 400, "densite_hab_km2": 10, "temps_voiture_min": 80, "dpe": "A",
    })
    assert 0 <= detail["total"] <= 100
    rien = scoring.calculer_score({
        "features": {}, "risques": {"inondation": True, "argile": 2, "seveso_km": 2,
                                     "nucleaire_km": 5, "feu_foret": True},
        "terrain_m2": 0, "altitude": 10, "densite_hab_km2": 5000,
        "temps_voiture_min": 400, "dpe": "G",
    })
    assert 0 <= rien["total"] <= 100
    assert rien["total"] < detail["total"]


def test_la_cave_ameliore_le_score():
    base = {"features": {}, "risques": {}, "terrain_m2": 1000,
            "altitude": 150, "densite_hab_km2": 50, "temps_voiture_min": 100}
    avec_cave = {**base, "features": {"cave": True}}
    assert (scoring.calculer_score(avec_cave)["total"]
            > scoring.calculer_score(base)["total"])
    assert "Cave / sous-sol" in scoring.calculer_score(avec_cave)["badges"]


def test_zone_inondable_penalise_et_alerte():
    base = {"features": {}, "risques": {}, "terrain_m2": 0}
    inonde = {"features": {}, "risques": {"inondation": True}, "terrain_m2": 0}
    assert (scoring.calculer_score(inonde)["total"]
            < scoring.calculer_score(base)["total"])
    assert "Zone inondable" in scoring.calculer_score(inonde)["alertes"]


def test_somme_des_maximums_fait_100():
    assert sum(scoring.MAX_PILIERS.values()) == 100


def test_troglodyte_et_nouveaux_criteres():
    f = scoring.extraire_criteres(
        "Maison troglodyte",
        "Troglodyte en tuffeau, source, poulailler, prairie, vigne, ruches, "
        "pompe à chaleur, en hameau.")
    for cle in ("troglodyte", "source", "poulailler", "prairie", "vigne",
                "ruches", "pompe_chaleur", "pierre", "isolement"):
        assert f[cle], cle
    detail = scoring.calculer_score({"features": f, "risques": {}, "terrain_m2": 0})
    assert "Habitat troglodyte" in detail["badges"]
    assert detail["piliers"]["abri"]["points"] >= 7           # troglodyte seul
    assert detail["piliers"]["alimentation"]["points"] >= 6   # mots-clés, sans terrain


def test_autonomie_alimentaire_sans_terrain():
    # Un petit terrain bien équipé marque des points (nouveau comportement).
    f = scoring.extraire_criteres("Maison", "Potager, poulailler et quelques ruches.")
    pts = scoring.calculer_score({"features": f, "risques": {}, "terrain_m2": 0}
                                 )["piliers"]["alimentation"]["points"]
    assert pts >= 8  # verger/potager 4 + poulailler 2 + ruches 2


def test_risque_communal_ne_condamne_pas_le_bien():
    """Géorisques signale un risque DOCUMENTÉ SUR LA COMMUNE, pas sur le bien.

    Mesuré sur nos annonces réelles : séisme et radon ressortent à 100 % des
    communes, l'inondation à 80 %. Les compter comme une exposition du bien
    pénaliserait tout le monde à tort.
    """
    from app.scoring import MAX_PILIERS, _pilier_risques, _alertes, _vigilances

    commune = {"inondation_commune": True, "seisme_commune": True,
               "radon_commune": True, "icpe_commune": True, "portee": "commune"}
    bien_expose = {"inondation": True}

    # Le bien réellement en zone inondable est bien plus pénalisé.
    assert _pilier_risques(bien_expose) < _pilier_risques(commune)
    assert _pilier_risques(commune) >= MAX_PILIERS["risques"] - 2   # à peine entamé
    # Et on n'affiche pas « Zone inondable » pour un simple signal communal.
    assert "Zone inondable" not in _alertes(commune, None)
    assert "Zone inondable" in _alertes(bien_expose, None)
    # Le signal communal reste visible, comme point à vérifier.
    assert any("commune" in v for v in _vigilances(commune))
