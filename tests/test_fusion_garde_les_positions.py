"""Une position ne se perd pas parce que la Base Adresse n'a pas répondu.

Le 11 novembre 2026, la Base Adresse Nationale a mal répondu toute la
journée. Chaque bien revisité ce jour-là a été réenregistré sans
coordonnées, et la fusion (app/historique.py) repartait de la ligne du
jour : 258 des 430 biens de mandataires revisités et 109 des 468 biens
d'agences ont perdu leur position. Le lendemain, 365 biens servis n'avaient
ni carte, ni distance, ni climat — dont la maison de Quemigny-sur-Seine,
située depuis le 17 octobre. C'est la faute que le projet avait déjà
corrigée pour les risques Géorisques (test_fusion_garde_les_risques), sous
une autre forme.

Deux parades : la fusion garde la position connue d'un bien qui n'a pas
changé de commune ; et l'export donne à un bien sans position celle de sa
commune, quand un autre bien de la même commune la porte déjà.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.historique import completer_positions, fusionner  # noqa: E402

AGENCES = {("IAD France (21)", "")}
QUEMIGNY = {"commune": "Quemigny-sur-Seine", "code_postal": "21510",
            "lat": 47.6528, "lon": 4.6631, "altitude": 280, "densite_hab_km2": 4.1}
SANS_POSITION = {"lat": None, "lon": None, "altitude": None, "densite_hab_km2": None}


def _bien(**champs):
    return {"id": "x", "agence": "IAD France (21)", "prix": 120000, **champs}


def test_un_bien_revisite_sans_reponse_garde_sa_position():
    avant = [_bien(vue_le="2026-10-17", **QUEMIGNY)]
    jour = _bien(**{**QUEMIGNY, **SANS_POSITION})
    res = fusionner(avant, [jour], AGENCES, "2026-11-11")
    assert (res[0]["lat"], res[0]["lon"]) == (47.6528, 4.6631)
    assert res[0]["altitude"] == 280 and res[0]["densite_hab_km2"] == 4.1
    assert res[0]["revue_le"] == "2026-11-11", "le bien est bien compté revu"


def test_une_position_fraiche_l_emporte():
    avant = [_bien(vue_le="2026-10-17", **QUEMIGNY)]
    jour = _bien(**{**QUEMIGNY, "lat": 47.65, "lon": 4.66})
    res = fusionner(avant, [jour], AGENCES, "2026-11-11")
    assert (res[0]["lat"], res[0]["lon"]) == (47.65, 4.66)


def test_un_bien_qui_change_de_commune_ne_garde_pas_l_ancienne_position():
    """Un code postal corrigé (voir mandataires.code_postal_confirme) déplace
    le bien : l'ancien point serait faux."""
    avant = [_bien(vue_le="2026-10-17", **QUEMIGNY)]
    jour = _bien(commune="Aisey-sur-Seine", code_postal="21400", **SANS_POSITION)
    res = fusionner(avant, [jour], AGENCES, "2026-11-11")
    assert res[0]["lat"] is None


def test_la_commune_connue_situe_un_bien_sans_position():
    biens = [
        {"id": "a", **QUEMIGNY},
        {"id": "b", **QUEMIGNY},
        # Un point isolé (une page qui portait ses propres coordonnées) ne
        # l'emporte pas sur le point de la commune.
        {"id": "c", **{**QUEMIGNY, "lat": 47.70, "lon": 4.70, "altitude": 300}},
        # L'orthographe de la commune varie d'un site à l'autre.
        {"id": "d", "commune": "QUEMIGNY SUR SEINE", "code_postal": "21510", **SANS_POSITION},
        # Même nom, autre code postal : on ne devine pas.
        {"id": "e", "commune": "Quemigny-sur-Seine", "code_postal": "21000", **SANS_POSITION},
        # Commune que personne n'a encore située.
        {"id": "f", "commune": "Nan-sous-Thil", "code_postal": "21390", **SANS_POSITION},
    ]
    assert completer_positions(biens) == 1
    d = biens[3]
    assert (d["lat"], d["lon"], d["altitude"], d["densite_hab_km2"]) == (47.6528, 4.6631, 280, 4.1)
    assert biens[4]["lat"] is None and biens[5]["lat"] is None
    # Une position connue n'est jamais remplacée.
    assert (biens[2]["lat"], biens[2]["lon"]) == (47.70, 4.70)


def test_l_export_complete_les_positions():
    """Toutes les collectes écrivent le fichier publié par l'export : c'est
    là que la parade doit passer, pas dans un seul collecteur."""
    source = (RACINE / "scripts" / "exporter_reel.py").read_text(encoding="utf-8")
    fusion = source.index("historique.fusionner(")
    assert "historique.completer_positions(fusionnees)" in source[fusion:fusion + 800]
