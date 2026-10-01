"""Un robot qui dit son nom, défini une seule fois, et une page derrière le nom.

Jusqu'au 1er octobre 2026, onze scripts se faisaient passer pour un navigateur
Chrome, chacun avec sa copie de la chaîne. La bascule a été MESURÉE avant
d'être faite (scripts/sonder_user_agent.py) : sur 292 sites et trois réseaux,
un seul refuse le robot déclaré en acceptant le navigateur.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import robot, seo  # noqa: E402
from app.main import app  # noqa: E402


def test_l_identite_dit_le_nom_et_renvoie_a_la_page_du_robot():
    assert robot.USER_AGENT.startswith(f"{robot.NOM}/{robot.VERSION} ")
    assert robot.USER_AGENT.endswith(f"(+{seo.SITE}{seo.URL_ROBOT})"), (
        "l'adresse dans l'identité doit être celle de la page qui décrit le robot")
    assert robot.ENTETES["User-Agent"] == robot.USER_AGENT


def test_plus_aucun_script_ne_se_fait_passer_pour_un_navigateur():
    """La chaîne Chrome ne subsiste qu'à un endroit : la sonde, qui la compare
    à l'identité réelle pour mesurer ce qu'un robot déclaré perdrait."""
    fautifs = []
    for dossier, motif in (("scripts", "*.py"), ("scraper", "*.py"), ("app", "*.py")):
        for fichier in sorted((RACINE / dossier).rglob(motif)):
            if fichier.name == "sonder_user_agent.py":
                continue
            if "Mozilla/5.0" in fichier.read_text(encoding="utf-8"):
                fautifs.append(str(fichier.relative_to(RACINE)))
    assert fautifs == [], f"se présentent encore comme un navigateur : {fautifs}"


def test_la_page_du_robot_dit_qui_il_est_et_comment_le_bloquer():
    reponse = TestClient(app).get(seo.URL_ROBOT)
    assert reponse.status_code == 200
    assert robot.USER_AGENT in reponse.text, "la page doit montrer l'identité telle qu'elle passe"
    assert f"User-agent: {robot.NOM}" in reponse.text and "Disallow: /" in reponse.text, (
        "la page doit donner les deux lignes de robots.txt qui l'arrêtent")
    assert seo.URL_MENTIONS in reponse.text, "la page doit mener à la porte du retrait"


def test_les_mentions_legales_menent_a_la_page_du_robot():
    reponse = TestClient(app).get(seo.URL_MENTIONS)
    assert reponse.status_code == 200
    assert seo.URL_ROBOT in reponse.text and robot.NOM in reponse.text
