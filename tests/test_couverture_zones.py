"""La découverte ne regardait pas là où le catalogue a déjà des biens.

Une maison de Montbard, vendue par une agence de Venarey-les-Laumes, n'était
pas au catalogue. L'agence est pourtant au registre depuis toujours — deux
établissements — mais aucune zone de découverte ne couvrait ce bassin : 35 km
d'Avallon dont le rayon fait 25, 53 km de Sainte-Sabine dont le rayon fait 30.
Un trou, entre deux cercles.

En cherchant si le trou était isolé, la mesure a donné bien pire : 443 des
1 459 biens servis et géolocalisés — TRENTE POUR CENT — étaient hors de toute
zone. Et pas dans des lieux obscurs : Rouen, Bayeux, Lisieux, Charolles,
Digoin. Ils étaient arrivés par les réseaux de mandataires, qui travaillent
par département, ou par des ajouts à la main. La découverte par OpenStreetMap
n'avait jamais regardé là, donc n'y trouvait aucune agence locale — et son
silence ressemblait à une absence d'agences.

Ces tests tiennent la couverture ET la crédibilité des zones : un centre
inventé serait pire qu'un trou, parce qu'il enverrait la découverte chercher
des agences là où il n'y a personne.
"""

import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement, decouverte  # noqa: E402


def distance(la1, lo1, la2, lo2) -> float:
    r = 6371
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def couverte(lat: float, lon: float) -> bool:
    return any(distance(z["lat"], z["lon"], lat, lon) <= z["rayon_km"]
               for z in decouverte.ZONES)


def test_le_bassin_de_montbard_est_couvert():
    """LE cas d'origine. Montbard est à 1 h de Paris par TGV — exactement ce
    que le pilier « accès sans voiture » est fait pour reconnaître."""
    assert couverte(47.6236, 4.3378)


def test_les_villes_qui_manquaient_sont_couvertes():
    """Elles avaient des biens au catalogue et aucune zone : la découverte n'y
    cherchait donc aucune agence."""
    for nom, lat, lon in (("Rouen", 49.4432, 1.0999),
                          ("Bayeux", 49.2764, -0.7024),
                          ("Charolles", 46.4344, 4.2757),
                          ("Digoin", 46.4820, 3.9770)):
        assert couverte(lat, lon), nom


def test_chaque_zone_porte_un_centre_et_un_rayon_utilisables():
    """Un centre inventé serait pire qu'un trou : il enverrait la découverte
    chercher des agences là où il n'y a personne, et le silence ressemblerait
    encore à une absence."""
    for zone in decouverte.ZONES:
        assert zone["nom"].strip(), zone
        assert 40 < zone["lat"] < 52, zone      # France métropolitaine nord
        assert -2 < zone["lon"] < 9, zone
        assert 15 <= zone["rayon_km"] <= 40, zone


def test_aucune_zone_n_est_posee_deux_fois():
    """Deux cercles au même endroit doublent le coût des requêtes Overpass
    sans rien couvrir de plus."""
    centres = [(round(z["lat"], 3), round(z["lon"], 3)) for z in decouverte.ZONES]
    assert len(centres) == len(set(centres))
    noms = [z["nom"] for z in decouverte.ZONES]
    assert len(noms) == len(set(noms))


def test_les_zones_couvrent_l_essentiel_du_catalogue():
    """Le garde-fou de fond, mesuré sur les vraies données : l'angle mort doit
    rester très en dessous des trente pour cent constatés le 17 août."""
    # On lit le FICHIER sans passer par le chargement : construire la base
    # ici polluait l'état partagé et faisait échouer, plus loin dans la suite,
    # des tests qui passaient seuls. Un test ne doit rien laisser derrière lui.
    import json
    tout = json.loads((RACINE / "data" / "annonces_reel.json").read_text(encoding="utf-8"))
    avec = [b for b in tout
            if b.get("lat") and b.get("departement") in chargement.DEPARTEMENTS_CIBLES]
    if len(avec) < 200:
        return                      # catalogue trop maigre pour conclure
    dehors = [b for b in avec if not couverte(b["lat"], b["lon"])]
    assert len(dehors) / len(avec) < 0.15, (
        f"{len(dehors)} biens sur {len(avec)} hors de toute zone")
