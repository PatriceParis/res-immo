"""Tests de l'accessibilité en train (critère « atteignable sans voiture »)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import gares  # noqa: E402
from app.scoring import MAX_PILIERS, _pilier_situation  # noqa: E402


def test_villes_desservies():
    """Vendôme, Château-Thierry et Noyon : les cas cités par l'utilisateur."""
    v = gares.gare_la_plus_proche(47.7931, 1.0656)          # Vendôme
    assert v and "Vendôme" in v["nom"] and v["minutes_paris"] == 42

    ct = gares.gare_la_plus_proche(49.0450, 3.4028)         # Château-Thierry
    assert ct and ct["nom"] == "Château-Thierry" and ct["minutes_paris"] == 50

    n = gares.gare_la_plus_proche(49.5836, 3.0000)          # Noyon
    assert n and n["nom"] == "Noyon" and n["minutes_paris"] == 65


def test_commune_isolee_sans_gare():
    """Loin de toute gare de la table : aucun accès train (pas de faux positif)."""
    # Plein Morvan, à plus de 25 km des gares listées.
    assert gares.gare_la_plus_proche(47.15, 4.05) is None
    assert gares.gare_la_plus_proche(None, None) is None


def test_le_train_rapproche_du_score():
    """À situation égale, un bien desservi marque plus qu'un bien sans gare."""
    sans = _pilier_situation(150, 50, 140, None, None)
    avec = _pilier_situation(150, 50, 140, None,
                             {"minutes_paris": 42, "km": 4.0})
    assert avec > sans
    # Une gare lointaine (18 km) rapporte moins qu'une gare au pied du bien.
    loin = _pilier_situation(150, 50, 140, None,
                             {"minutes_paris": 42, "km": 18.0})
    assert sans < loin < avec


def test_pilier_situation_reste_plafonne():
    """Le bonus train ne fait pas déborder le pilier au-dessus de son maximum."""
    parfait = _pilier_situation(250, 10, 60, {"isolement": True},
                                {"minutes_paris": 42, "km": 2.0})
    assert parfait <= MAX_PILIERS["situation"]


def test_gare_dans_la_commune_touche_son_bonus():
    """Piège Python : « train.get("km") or 99 » vaut 99 quand km == 0.0.

    Une gare située DANS la commune se retrouvait donc traitée comme étant à
    99 km, et privée du bonus — exactement l'inverse du but recherché.
    """
    sur_place = _pilier_situation(250, 40, 265, None,
                                  {"minutes_paris": 80, "km": 0.0})
    lointaine = _pilier_situation(250, 40, 265, None,
                                  {"minutes_paris": 80, "km": 20.0})
    assert sur_place > lointaine


def test_le_creusot_tgv_rapproche_la_saone_et_loire():
    """Chalon est à 4 h 25 de route, mais Le Creusot TGV met Paris à 1 h 20 :
    c'est précisément ce que le pilier « accès sans voiture » doit voir."""
    creusot = gares.gare_la_plus_proche(46.8003, 4.4331)
    assert creusot and creusot["minutes_paris"] == 80
    assert "Creusot" in creusot["nom"]

    chalon = gares.gare_la_plus_proche(46.7806, 4.8536)
    assert chalon and chalon["minutes_paris"] <= 100

    # À situation routière identique, la desserte TGV fait la différence.
    sans = _pilier_situation(200, 50, 265, None, None)
    avec = _pilier_situation(200, 50, 265, None, creusot)
    assert avec > sans


def test_yonne_desservie():
    """La Puisaye est à 2 h 25 de route et à 22 km d'une gare : elle doit
    conserver un accès train, même sans gare dans la commune."""
    toucy = gares.gare_la_plus_proche(47.7333, 3.2944)
    assert toucy and "Auxerre" in toucy["nom"]
    assert gares.gare_la_plus_proche(47.7982, 3.5734)["minutes_paris"] == 105
