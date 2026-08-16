"""La découverte d'agences doit couvrir tout le périmètre, et rien d'autre.

Question posée par l'utilisateur : « indexes-tu bien toutes les agences du
secteur ? ». Non. Les dix-neuf zones de découverte historiques ne couvraient
que HUIT des trente-six départements visés. La présence des autres au
catalogue était accidentelle — le Calvados et la Meurthe-et-Moselle, nos deux
mieux pourvus avec 174 et 171 biens, n'avaient aucune zone : leurs agences
venaient d'ajouts à la main ou des réseaux de mandataires.

Symétriquement, trois départements étaient visés en pure perte : le Bas-Rhin,
le Haut-Rhin et le Territoire de Belfort sont ENTIÈREMENT au-delà des 350 km
que l'application s'impose. On y aurait dépensé du budget de collecte pour des
annonces écartées au chargement.

Ces tests tiennent les deux bouts : aucun département visé sans zone, aucune
zone hors de portée.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.chargement import DEPARTEMENTS_CIBLES, DISTANCE_MAX_KM, HORS_DE_PORTEE  # noqa: E402
from app.decouverte import ZONES  # noqa: E402
from app.geo import distance_paris_km, haversine_km  # noqa: E402


def test_aucune_zone_de_decouverte_hors_du_perimetre():
    """Chercher des agences à plus de 350 km, c'est préparer des annonces que
    le chargement jettera. Le contrôle vaut pour toute zone ajoutée demain."""
    for zone in ZONES:
        km = distance_paris_km(zone["lat"], zone["lon"])
        assert km <= DISTANCE_MAX_KM, f"{zone['nom']} est à {km:.0f} km de Paris"


def test_les_departements_hors_de_portee_ne_sont_plus_vises():
    """Bas-Rhin, Haut-Rhin, Territoire de Belfort : leurs points les plus
    proches de Paris sont à 367, 379 et 360 km. Aucun de leurs biens ne
    pourrait être servi."""
    assert HORS_DE_PORTEE == {"67", "68", "90"}
    assert not (DEPARTEMENTS_CIBLES & HORS_DE_PORTEE)
    for lat, lon in ((48.7419, 7.3625), (48.0794, 7.3585), (47.6380, 6.8628)):
        assert distance_paris_km(lat, lon) > DISTANCE_MAX_KM


def test_la_haute_saone_reste_visee_et_recoit_une_zone():
    """Elle n'a aucun bien, mais elle est bien dans le périmètre : Vesoul est
    à 313 km. C'est un trou de couverture, pas un département hors portée —
    la confondre avec l'Alsace aurait fermé une vraie piste."""
    assert "70" in DEPARTEMENTS_CIBLES
    vesoul = next((z for z in ZONES if "Vesoul" in z["nom"]), None)
    assert vesoul, "la Haute-Saône doit avoir sa zone de découverte"
    assert distance_paris_km(vesoul["lat"], vesoul["lon"]) <= DISTANCE_MAX_KM


def test_la_couverture_a_plus_que_double():
    """Le garde-fou du travail lui-même : dix-neuf zones ne suffisaient pas
    pour trente-trois départements."""
    assert len(ZONES) >= 40, f"{len(ZONES)} zones — la couverture a régressé"


def test_deux_zones_ne_font_pas_double_emploi():
    """Chaque zone coûte une interrogation d'OpenStreetMap et le sondage de
    tous les sites qu'elle ramène. Deux centres à moins de dix kilomètres
    paient deux fois le même territoire."""
    trop_proches = [
        (a["nom"], b["nom"])
        for i, a in enumerate(ZONES) for b in ZONES[i + 1:]
        if haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) < 10
    ]
    assert not trop_proches, f"zones redondantes : {trop_proches}"
