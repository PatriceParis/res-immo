"""Le lot cherché doit tourner, et ne jamais frapper pour rien.

Vingt-six mille agences ne se sondent pas d'un coup : chaque passage en prend
un lot. Sans rotation, ce serait éternellement le même lot — la faute qui a
privé Safti de son tour et la Saône-et-Loire de dix jours de collecte.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "resoudre_sites", RACINE / "scripts" / "resoudre_sites.py")
RESOLUTION = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RESOLUTION)


def agence(nom, dept="71", siret=None, **extra):
    return {"nom": nom, "departement": dept, "source": "registre",
            "commune": "Chalon-Sur-Saone", "siret": siret, **extra}


def test_seules_les_agences_sans_site_sont_cherchees():
    """Celles d'OpenStreetMap ont déjà le leur : les resonder serait payer
    deux fois pour la même information."""
    recensees = [agence("CBF CONSEILS"),
                 agence("DEJA CONNUE", site="https://deja.fr"),
                 {"nom": "OSM AGENCE", "departement": "71",
                  "source": "openstreetmap", "site": "https://osm.fr"}]
    noms = {a["nom"] for a in RESOLUTION.a_chercher(recensees, None)}
    assert noms == {"CBF CONSEILS"}


def test_les_hors_cible_ne_sont_pas_derangees():
    """Constructeurs et syndics purs seraient refusés au sondage suivant :
    autant ne pas frapper à leur porte."""
    recensees = [agence("MAISONS PIERRE CONSTRUCTION"), agence("SYNDIC DU CENTRE"),
                 agence("CBF CONSEILS")]
    noms = {a["nom"] for a in RESOLUTION.a_chercher(recensees, None)}
    assert noms == {"CBF CONSEILS"}


def test_une_agence_hors_perimetre_est_ignoree():
    """Le Var est dans le registre, pas dans nos terroirs."""
    assert RESOLUTION.a_chercher([agence("VAR IMMO PLAGE", dept="83")], None) == []


def test_une_agence_sans_nom_exploitable_n_est_pas_cherchee():
    """« AGENCE IMMOBILIERE » ne produit aucune adresse plausible : la
    chercher coûterait une requête pour rien."""
    assert RESOLUTION.a_chercher([agence("AGENCE IMMOBILIERE")], None) == []


def test_les_jamais_essayees_passent_devant():
    """LE point de la rotation. Sans elle, le lot reprend toujours les mêmes."""
    lot = [agence("ESSAYEE HIER", siret="1"), agence("JAMAIS VUE", siret="2"),
           agence("ESSAYEE AVANT-HIER", siret="3")]
    journal = {"1": "2026-08-16", "3": "2026-08-10"}
    ordre = [a["nom"] for a in RESOLUTION.ordre_de_recherche(lot, journal)]
    assert ordre == ["JAMAIS VUE", "ESSAYEE AVANT-HIER", "ESSAYEE HIER"]


def test_deux_etablissements_d_une_meme_societe_ne_se_confondent_pas():
    """Le registre liste un établissement par ligne : le SIRET les distingue,
    le nom seul les confondrait et l'un masquerait l'autre au journal."""
    a, b = agence("C & M GESTION", siret="111"), agence("C & M GESTION", siret="222")
    assert RESOLUTION._cle(a) != RESOLUTION._cle(b)


def test_une_agence_sans_siret_garde_une_cle_stable():
    """Sans SIRET, la clé retombe sur nom + commune : elle doit rester la même
    d'un passage à l'autre, sinon la rotation ne mémorise rien."""
    a = agence("PETITE AGENCE", siret=None)
    assert RESOLUTION._cle(a) == RESOLUTION._cle(dict(a))
    assert "PETITE AGENCE" in RESOLUTION._cle(a)
