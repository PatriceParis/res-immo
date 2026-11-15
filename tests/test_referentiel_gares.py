"""Les 41 gares saisies à la main laissaient 72 % du catalogue sans desserte.

`app/gares.py` portait une liste écrite pour « les 5 régions cibles ». Le
catalogue a débordé ces régions depuis longtemps — mesuré le 15 novembre
2026, les départements sans aucune gare à 25 km étaient le Nord, la
Meurthe-et-Moselle, la Seine-Maritime, le Calvados et l'Indre-et-Loire. Ceux
de Lille, Nancy, Rouen, Caen et Tours. Ce n'était pas une absence de
desserte : c'était notre ignorance, et le filtre « gare la plus proche »
écartait les biens sur elle.

Le référentiel SNCF des gares de voyageurs (Licence Ouverte, 2 792 gares)
porte la couverture de 28 % à 96 %. Il ne porte en revanche AUCUN temps de
trajet, et c'est là que ces tests sont le plus utiles : les deux questions
— « une gare à portée ? » et « Paris en combien ? » — n'ont plus la même
réponse, et rien ne doit les confondre.
"""

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import gares, pages  # noqa: E402
from app.geo import haversine_km  # noqa: E402

REFERENTIEL = RACINE / "data" / "gares_sncf.json"


def test_le_referentiel_est_present_et_plausible():
    """Versionné, parce que le serveur qui sert les fiches n'a pas de réseau
    et ne pourra jamais le télécharger lui-même."""
    assert REFERENTIEL.exists(), "lancer scripts/importer_gares.py"
    gares_sncf = json.loads(REFERENTIEL.read_text(encoding="utf-8"))
    assert len(gares_sncf) > 2000
    for gare in gares_sncf[:50]:
        assert gare["nom"] and -5 < gare["lon"] < 10 and 41 < gare["lat"] < 52


@pytest.mark.parametrize("ville, lat, lon", [
    ("Lille", 50.63, 3.06), ("Nancy", 48.69, 6.18), ("Rouen", 49.44, 1.09),
    ("Caen", 49.18, -0.37), ("Tours", 47.39, 0.69),
])
def test_les_villes_qui_manquaient_ont_une_gare(ville, lat, lon):
    """LE test. Ces cinq-là sont les chefs-lieux des départements que la
    liste manuelle ignorait — et chacun a évidemment une gare."""
    trouvee = gares.gare_la_plus_proche(lat, lon)
    assert trouvee is not None, f"{ville} n'a toujours aucune gare"
    assert trouvee["km"] < 10


def test_aucun_temps_de_trajet_n_est_inventé():
    """Le référentiel n'en porte pas, et on ne l'estime pas depuis la
    distance : Vendôme est à 42 min pour 160 km, Creil à 30 min pour 50 — le
    rapport varie du simple au triple selon la ligne. Mieux vaut ne rien dire
    que dire faux."""
    lille = gares.gare_la_plus_proche(50.63, 3.06)
    assert lille["nom"].startswith("Lille")
    assert lille["minutes_paris"] is None, "un temps a été inventé"


def test_le_temps_de_paris_n_est_pas_attribue_a_la_mauvaise_gare():
    """À Vendôme, la gare la plus proche s'appelle « Vendôme » mais le TGV
    part de « Vendôme–Villiers-sur-Loir TGV », quatre kilomètres plus loin.
    Les 42 minutes appartiennent à la seconde."""
    v = gares.gare_la_plus_proche(47.7931, 1.0656)
    assert v["minutes_paris"] == 42
    assert v["nom_vers_paris"] != v["nom"]
    assert v["km_vers_paris"] is not None


def test_la_fiche_dit_les_deux_faits_separement():
    bien = {"train": gares.gare_la_plus_proche(47.7931, 1.0656)}
    proche, vers_paris = pages._gare_proche(bien), pages._gare_vers_paris(bien)
    assert "Vendôme" in proche and "km" in proche
    assert "42 min" in vers_paris and "Villiers" in vers_paris


def test_la_fiche_dit_ce_qu_est_la_gare():
    """46 % des gares les plus proches sont des haltes : l'écrire évite de
    faire passer deux trains par jour pour une desserte."""
    bien = {"train": gares.gare_la_plus_proche(50.63, 3.06)}
    assert "grande gare" in pages._gare_proche(bien)
    assert pages._gare_vers_paris(bien) == "", "pas de temps connu, donc rien"


def test_la_grille_ne_rate_aucune_gare():
    """L'index par degré évite 47 millions de distances au chargement. Mal
    dimensionné, il ferait manquer la gare d'à côté sans que rien ne le
    signale — un gain de temps payé en silence."""
    gares._charger_referentiel()
    toutes = [g for cellule in gares._GRILLE.values() for g in cellule]
    for lat, lon in ((50.63, 3.06), (47.39, 0.69), (43.60, 1.44),
                     (48.99, 2.44), (46.80, 4.43)):
        force_brute = min(haversine_km(lat, lon, g[1], g[2]) for g in toutes)
        par_la_grille = gares._plus_proche_du_referentiel(lat, lon)[1]
        assert par_la_grille == pytest.approx(force_brute, abs=0.01), (
            f"à ({lat}, {lon}) la grille annonce {par_la_grille:.1f} km "
            f"quand la plus proche est à {force_brute:.1f}")


def test_un_point_sans_gare_dans_le_rayon_ne_promet_rien():
    """Au large de la Bretagne : aucune gare, et la question ne se pose pas."""
    assert gares.gare_la_plus_proche(47.5, -5.5) is None
    assert gares.gare_la_plus_proche(None, None) is None
