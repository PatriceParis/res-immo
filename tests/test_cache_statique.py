"""L'habillage du site doit suivre le déploiement, pas traîner derrière.

Le 17 août, le site servait encore l'ancien slogan et l'ancien menu plusieurs
heures après leur remplacement — alors que les ANNONCES affichées, elles,
étaient à jour. C'est le plus trompeur des symptômes : la page a l'air
vivante, et son habillage date d'avant.

La cause : `StaticFiles` n'envoie aucun `Cache-Control`. Le navigateur applique
alors sa propre règle — garder la ressource un dixième de son âge — et
l'hébergeur peut en faire autant. Personne ne ment, personne ne prévient.

`no-cache` ne veut pas dire « ne garde rien » mais « garde, et demande-moi si
c'est encore bon ». Avec l'ETag déjà envoyé, la vérification coûte une réponse
vide. Ces tests tiennent les deux sens : plus jamais de version périmée, et
pas de retéléchargement inutile non plus.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_la_page_et_son_habillage_sont_toujours_revalides(client):
    """LE cas. Ces trois fichiers ne portent pas d'empreinte dans leur nom :
    ils doivent rester solidaires, donc être vérifiés à chaque visite."""
    for chemin in ("/", "/app.js", "/style.css"):
        reponse = client.get(chemin)
        assert reponse.status_code == 200, chemin
        assert reponse.headers.get("cache-control") == "no-cache", chemin


def test_la_revalidation_ne_retelecharge_rien(client):
    """L'excès inverse : revalider ne doit pas vouloir dire recharger. L'ETag
    permet une réponse vide quand rien n'a changé."""
    premiere = client.get("/")
    etiquette = premiere.headers.get("etag")
    assert etiquette, "sans ETag, chaque visite retéléchargerait toute la page"
    seconde = client.get("/", headers={"If-None-Match": etiquette})
    assert seconde.status_code == 304
    assert not seconde.content


def test_les_bibliotheques_figees_se_gardent_longtemps(client):
    """Leaflet est figé à une version : le revalider à chaque visite coûterait
    une requête pour rien."""
    reponse = client.get("/vendor/leaflet/leaflet.css")
    assert reponse.status_code == 200
    assert "max-age=604800" in reponse.headers.get("cache-control", "")
    assert "immutable" in reponse.headers.get("cache-control", "")


def test_la_page_servie_porte_bien_les_derniers_changements(client):
    """Un garde-fou de bout en bout : si le menu n'est pas dans la réponse,
    le problème n'est plus le cache mais la page elle-même."""
    page = client.get("/").text
    assert "Explorer par région" in page
    assert "/mentions-legales" in page
