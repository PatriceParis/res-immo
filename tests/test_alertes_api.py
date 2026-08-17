"""L'API des alertes : fermée sans les clés, sûre avec.

Le pire état serait la configuration partielle — un formulaire qui encaisse
des adresses qu'aucun courriel ne peut confirmer. Recueillir pour perdre est
la faute déjà commise une fois par la mise en relation ; ces tests tiennent
la porte : tout ou rien.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

SECRET = "secret-de-test-pour-l-api-des-alertes"


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class FauxCurseur:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, *_): pass
    rowcount = 1


class FausseConnexion:
    def cursor(self): return FauxCurseur()
    def commit(self): pass
    def close(self): pass


@pytest.fixture()
def configure(monkeypatch):
    """Les trois clés posées, la base et l'envoi remplacés par des sondes."""
    from app import alertes_db, courriels
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("ALERTES_SECRET", SECRET)
    monkeypatch.setenv("RESEND_API_KEY", "cle-de-test")
    appels = {"inscrits": [], "confirmes": [], "supprimes": [], "courriels": []}
    monkeypatch.setattr(alertes_db, "connexion", lambda: FausseConnexion())
    monkeypatch.setattr(alertes_db, "preparer", lambda conn: None)
    monkeypatch.setattr(alertes_db, "inscrire",
                        lambda conn, e, p, t: appels["inscrits"].append((e, p, t)))
    monkeypatch.setattr(alertes_db, "confirmer",
                        lambda conn, e: appels["confirmes"].append(e) or True)
    monkeypatch.setattr(alertes_db, "supprimer",
                        lambda conn, e: appels["supprimes"].append(e) or True)
    monkeypatch.setattr(courriels, "envoyer",
                        lambda dest, sujet, texte, lien="", **k:
                        appels["courriels"].append((dest, sujet, texte)) or True)
    return appels


# --- porte fermée ----------------------------------------------------------

def test_sans_les_cles_tout_repond_service_indisponible(client, monkeypatch):
    """LE test. Aucune des trois routes ne doit rien encaisser ni révéler."""
    for cle in ("DATABASE_URL", "ALERTES_SECRET", "RESEND_API_KEY"):
        monkeypatch.delenv(cle, raising=False)
    assert client.post("/api/alertes", json={
        "email": "a@b.fr", "terroirs": ["Normandie"]}).status_code == 503
    assert client.get("/api/alertes/confirmer?email=a@b.fr&jeton=x").status_code == 503
    assert client.get("/api/alertes/desinscrire?email=a@b.fr&jeton=x").status_code == 503


def test_une_configuration_partielle_reste_fermee(client, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.delenv("ALERTES_SECRET", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    assert client.post("/api/alertes", json={
        "email": "a@b.fr", "terroirs": ["Normandie"]}).status_code == 503


# --- porte ouverte ---------------------------------------------------------

def test_l_inscription_enregistre_puis_envoie_l_activation(client, configure):
    reponse = client.post("/api/alertes", json={
        "email": "Patrice@Exemple.fr", "prix_max": 150000,
        "terroirs": ["Normandie", "Grand Est"]})
    assert reponse.status_code == 200
    assert configure["inscrits"] == [("patrice@exemple.fr", 150000,
                                      ["Normandie", "Grand Est"])]
    (dest, sujet, texte), = configure["courriels"]
    assert dest == "patrice@exemple.fr" and "Activez" in sujet
    from app import alertes
    assert alertes.jeton("patrice@exemple.fr", SECRET) in texte


def test_des_criteres_invalides_sont_refuses_sans_rien_enregistrer(client, configure):
    assert client.post("/api/alertes", json={
        "email": "a@b.fr", "terroirs": ["Bretagne"]}).status_code == 422
    assert not configure["inscrits"] and not configure["courriels"]


def test_l_activation_exige_le_jeton_exact(client, configure):
    from app import alertes
    bon = alertes.jeton("a@b.fr", SECRET)
    assert client.get(
        f"/api/alertes/confirmer?email=a@b.fr&jeton={bon}").status_code == 200
    assert configure["confirmes"] == ["a@b.fr"]
    assert client.get(
        "/api/alertes/confirmer?email=a@b.fr&jeton=forge").status_code == 403
    assert configure["confirmes"] == ["a@b.fr"], "un jeton forgé ne touche pas la base"


def test_la_desinscription_efface_et_le_dit(client, configure):
    from app import alertes
    reponse = client.get("/api/alertes/desinscrire?email=a@b.fr&jeton="
                         + alertes.jeton("a@b.fr", SECRET))
    assert reponse.status_code == 200
    assert configure["supprimes"] == ["a@b.fr"]
    assert "effacée" in reponse.text
    assert 'name="robots" content="noindex"' in reponse.text


def test_le_formulaire_reel_apparait_quand_les_cles_existent(client, configure):
    page = client.get("/alertes").text
    assert 'type="email"' in page
    assert "/api/alertes" in page
    assert "courriel" in page and "activation" in page
    assert "ne sont pas encore ouvertes" not in page


def test_un_envoi_d_activation_rate_est_signale(client, configure, monkeypatch):
    """« Merci ! » sur un courriel jamais parti serait un mensonge : le
    visiteur attendrait une activation qui ne viendra pas."""
    from app import courriels
    monkeypatch.setattr(courriels, "envoyer", lambda *a, **k: False)
    assert client.post("/api/alertes", json={
        "email": "a@b.fr", "terroirs": ["Normandie"]}).status_code == 502
