"""La rotation des départements lisait le journal avec la mauvaise clé.

`collecter_mandataires` ÉCRIT « iad:71 » et `ordre_des_departements` RELISAIT
« 71 ». Aucune recherche n'aboutissait jamais : tous les départements
paraissaient n'avoir jamais été visités, l'égalité était tranchée par le code
du département, et chaque passage repartait de « 01 » pour s'arrêter au budget
de temps. Les codes élevés n'étaient donc atteints qu'exceptionnellement — le
71 (Saône-et-Loire, 1 333 annonces IAD) n'avait pas été revu depuis dix jours
quand ses voisins l'étaient de la veille, et une maison mise en ligne entre
temps ne pouvait pas entrer au catalogue.

C'est la deuxième fois que deux copies d'une même clé divergent — la première
avait coûté cinquante-six annonces Century 21. La parade est la même : une
seule fonction fabrique la clé, pour celui qui écrit comme pour celui qui lit.

Ces tests tiennent les DEUX sens : servir les plus anciens d'abord, mais
continuer à départager proprement ceux qu'on n'a jamais vus.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement, mandataires  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecter_mandataires", RACINE / "scripts" / "collecter_mandataires.py")
COLLECTEUR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(COLLECTEUR)

GROUPES = {"71": [], "89": [], "61": []}


def test_le_journal_est_lu_avec_la_cle_qui_a_servi_a_l_ecrire():
    """LE cas. Le journal réel est préfixé par le réseau ; sans le préfixe,
    la recherche échoue en silence et l'ordre retombe sur le code du
    département."""
    vu = {"iad:71": "2026-08-07", "iad:89": "2026-08-01"}   # 61 jamais visité
    assert mandataires.ordre_des_departements(GROUPES, vu, "iad") == ["61", "89", "71"]


def test_deux_reseaux_ne_se_confondent_pas():
    """Un département visité chez IAD ne dit rien de Safti : les cibles sont
    distinctes, et les mélanger ferait sauter le tour de l'un des deux."""
    vu = {"iad:71": "2026-08-16", "safti:71": "2026-08-01",
          "iad:89": "2026-08-01", "safti:89": "2026-08-16"}
    assert mandataires.ordre_des_departements(GROUPES, vu, "iad")[-1] == "71"
    assert mandataires.ordre_des_departements(GROUPES, vu, "safti")[-1] == "89"


def test_l_ecriture_et_la_lecture_partagent_la_meme_fabrique():
    """La faute d'origine : deux endroits fabriquaient la clé, chacun à sa
    façon. Une seule fonction, désormais — et c'est elle qu'on vérifie."""
    assert mandataires.cle_journal("iad", "71") == "iad:71"
    vu = {mandataires.cle_journal("iad", "71"): "2026-08-07"}
    assert mandataires.ordre_des_departements({"71": [], "61": []}, vu, "iad") == ["61", "71"]


def test_un_journal_vide_reste_deterministe():
    """Premier passage, ou journal perdu : aucune date ne départage. L'ordre
    doit rester stable plutôt qu'arbitraire."""
    assert mandataires.ordre_des_departements(GROUPES, {}, "iad") == ["61", "71", "89"]


def test_le_reseau_doit_etre_nomme():
    """Un défaut vide rétablirait la faute en silence chez le prochain
    appelant qui l'oublie. Mieux vaut que l'appel échoue."""
    try:
        mandataires.ordre_des_departements(GROUPES, {})
    except TypeError:
        return
    raise AssertionError("le réseau doit être un argument obligatoire")


def test_la_file_ne_contient_pas_les_departements_qu_on_jette_ensuite(monkeypatch):
    """Le Bas-Rhin, le Haut-Rhin et le Territoire de Belfort sont dans une
    région ciblée mais entièrement au-delà de 350 km : le chargement écarte
    tous leurs biens. Les mettre en file, c'était dépenser un tour de rotation
    pour rien — et retarder d'autant les départements qui comptent."""
    demandes: list[str] = []
    monkeypatch.setattr(COLLECTEUR, "lire",
                        lambda url: demandes.append(url) or b"[]")
    COLLECTEUR.communes_des_terroirs()
    interroges = {u.rsplit("/departements/", 1)[1].split("/")[0] for u in demandes}

    assert interroges == chargement.DEPARTEMENTS_CIBLES
    assert not interroges & chargement.HORS_DE_PORTEE, "hors de portée : à ne pas lire"
    assert "71" in interroges, "la Saône-et-Loire doit rester dans la file"
