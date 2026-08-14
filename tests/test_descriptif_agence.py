"""Le descriptif rédigé par l'agence ne doit plus être republié.

C'était le dernier endroit du site où le texte d'un tiers s'affichait tel
quel : la fiche modale le reprenait mot pour mot. Les pages servies par le
serveur, elles, écrivent depuis nos données depuis le début — voir
app/redaction.py, qui s'interdit explicitement de reformuler l'annonce.

La distinction que ces tests tiennent : on LIT toujours ce descriptif, pour
détecter cave, puits et poêle et pour repérer les biens vendus. Lire pour
analyser n'est pas rediffuser. Ce qui change, c'est qu'il ne sort plus — ni
par l'API, ni à l'écran.

À sa place, la seule image que nous ayons de plein droit : une orthophoto
IGN sous Licence Ouverte, désormais sur TOUTE fiche et non plus seulement
quand la photo de l'agence manque.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db, scoring  # noqa: E402
from app.qualite import est_vendu  # noqa: E402

APP_JS = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")
DESCRIPTIF = "Belle longère avec cave voûtée, puits et poêle à bois."


def test_la_fiche_n_affiche_plus_le_texte_de_l_agence():
    """LE point. Un seul `a.description` qui revient, et la republication
    recommence sans que personne ne s'en aperçoive."""
    assert "a.description" not in APP_JS


def test_l_api_ne_sort_ni_le_descriptif_ni_le_texte():
    """Ce qui n'est pas exposé ne peut pas être republié par accident — ni
    par notre fiche, ni par qui interroge l'API."""
    class Ligne(dict):
        def keys(self):  # sqlite3.Row se convertit par dict(row)
            return super().keys()

    ligne = Ligne({"id": "x", "titre": "Longère", "description": DESCRIPTIF,
                   "texte": "page entière", "prix": 90000,
                   **{c: None for c in db.CHAMPS_JSON}})
    sortie = db._row_vers_dict(ligne)
    assert "description" not in sortie
    assert "texte" not in sortie
    assert sortie["titre"] == "Longère", "le reste du bien passe normalement"


def test_le_descriptif_reste_lu_pour_detecter_les_atouts():
    """La contrepartie : sans cette lecture, cave, puits et poêle
    disparaîtraient du catalogue. Lire n'est pas rediffuser."""
    criteres = scoring.extraire_criteres("Maison à vendre", DESCRIPTIF)
    assert criteres.get("cave") and criteres.get("puits") and criteres.get("bois")


def test_le_descriptif_reste_lu_pour_reperer_les_biens_vendus():
    """L'autre usage interne : une annonce vendue qui traîne en ligne."""
    assert est_vendu({"titre": "Longère", "description": "Bien vendu."})
    assert not est_vendu({"titre": "Longère", "description": DESCRIPTIF})


def test_la_vue_aerienne_est_sur_toute_fiche():
    """Elle n'est plus un repli : elle remplace le descriptif, donc elle
    s'affiche même quand la photo de l'agence est là."""
    assert "vueDuCiel(a)" in APP_JS
    bloc = APP_JS[APP_JS.index("function vueDuCiel"):]
    bloc = bloc[:bloc.index("\nfunction imgPhoto")]
    assert "tuileAerienne" in bloc
    # Aucune condition sur la présence d'une photo d'agence : la seule
    # raison de ne rien afficher est l'absence de coordonnées.
    assert "photoReelle" not in bloc


def test_la_legende_dit_ce_que_l_image_est_et_d_ou_elle_vient():
    """Deux obligations distinctes. La mention « © IGN » est due au titre de
    la Licence Ouverte. Le cadrage COMMUNAL doit être dit parce que nos
    coordonnées viennent de la commune et du code postal : présenter cette
    vue comme la parcelle serait inventer."""
    bloc = APP_JS[APP_JS.index("function vueDuCiel"):]
    bloc = bloc[:bloc.index("\nfunction imgPhoto")]
    assert "© IGN" in bloc and "Licence Ouverte" in bloc
    assert "n'est pas connu" in bloc and "adresse" in bloc
