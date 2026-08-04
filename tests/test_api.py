"""Tests de l'API web (avec une petite base temporaire)."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "test.db"))

    from fastapi.testclient import TestClient
    from app import db
    from app.chargement import charger_annonces_json
    from app.main import app

    annonces = [
        {
            "id": "t-1", "source": "test", "titre": "Fermette avec cave et puits",
            "description": "Cave voûtée, puits, poêle à bois, verger.",
            "prix": 200000, "surface_m2": 120, "terrain_m2": 5000,
            "commune": "Bellême", "code_postal": "61130",
            "lat": 48.373, "lon": 0.560, "altitude": 220,
            "densite_hab_km2": 50, "dpe": "D", "risques": {},
        },
        {
            # Bien faible, mais dans un terroir CIBLÉ (Oise). Il était situé à
            # Dourdan (91) : l'Île-de-France étant écartée du périmètre, il
            # n'était tout simplement plus chargé.
            "id": "t-2", "source": "test", "titre": "Pavillon simple",
            "description": "Pavillon en lotissement, chauffage électrique.",
            "prix": 450000, "surface_m2": 100, "terrain_m2": 300,
            "commune": "Beauvais", "code_postal": "60000",
            "lat": 49.430, "lon": 2.081, "altitude": 130,
            "densite_hab_km2": 300, "dpe": "F", "risques": {"inondation": True},
        },
    ]
    fichier = tmp_path / "annonces.json"
    fichier.write_text(json.dumps(annonces), encoding="utf-8")
    conn = db.connexion()
    charger_annonces_json(conn, fichier)
    conn.close()

    with TestClient(app) as tc:
        yield tc


def test_liste_et_tri_par_score(client):
    data = client.get("/api/annonces").json()
    assert data["total"] == 2
    assert data["items"][0]["id"] == "t-1"  # la fermette gagne au score


def test_filtre_prix(client):
    data = client.get("/api/annonces", params={"prix_max": 250000}).json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "t-1"


def test_filtre_cave_et_hors_inondation(client):
    assert client.get("/api/annonces", params={"cave": 1}).json()["total"] == 1
    assert client.get("/api/annonces", params={"hors_inondation": 1}).json()["total"] == 1


def test_detail_et_404(client):
    fiche = client.get("/api/annonces/t-1").json()
    assert fiche["score_detail"]["piliers"]["abri"]["points"] >= 8  # la cave compte
    assert client.get("/api/annonces/inconnu").status_code == 404


def test_meta(client):
    meta = client.get("/api/meta").json()
    assert meta["nb"] == 2
    assert meta["nb_cave"] == 1


def test_un_bien_d_ile_de_france_n_est_pas_charge(tmp_path, monkeypatch):
    """L'Île-de-France est 6e au classement des terroirs : hors cible.

    Les agences frontalières (Château-Thierry couvre La Ferté-sous-Jouarre)
    en ramenaient sans que rien ne les arrête.
    """
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "idf.db"))
    from app import db
    from app.chargement import charger_liste

    conn = db.connexion()
    charges = charger_liste(conn, [{
        "id": "idf-1", "source": "test", "titre": "Maison T6 dans hameau",
        "type_bien": "maison", "prix": 250000, "surface_m2": 140, "pieces": 6,
        "commune": "La Ferté-sous-Jouarre", "code_postal": "77260",
        "lat": 48.947, "lon": 3.126,
    }])
    conn.close()
    assert charges == 0


def test_mise_en_relation(client, tmp_path):
    """C'est le modèle économique : la demande doit réellement aboutir."""
    r = client.post("/api/contact",
                    json={"annonce_id": "t-1", "email": "jean@exemple.fr",
                          "message": "Je souhaite visiter."})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["annonce"].startswith("Fermette")

    # La demande est journalisée hors du dépôt (elle contient un e-mail).
    journal = tmp_path / "demandes_contact.jsonl"
    assert journal.exists()
    assert "jean@exemple.fr" in journal.read_text(encoding="utf-8")


def test_mise_en_relation_refuse_les_entrees_invalides(client):
    assert client.post("/api/contact",
                       json={"annonce_id": "t-1", "email": "pas-un-email"}
                       ).status_code == 422
    assert client.post("/api/contact",
                       json={"annonce_id": "inconnu", "email": "jean@exemple.fr"}
                       ).status_code == 404
    # Message démesuré : refusé avant d'atteindre le disque.
    assert client.post("/api/contact",
                       json={"annonce_id": "t-1", "email": "jean@exemple.fr",
                             "message": "x" * 5000}).status_code == 422


def test_les_pastilles_de_terroir_comptent_avec_les_filtres(client):
    """Bug signalé : la pastille annonçait « 60 biens » quand la liste filtrée
    n'en montrait que 2 — elle comptait sans tenir compte des filtres."""
    # Sans filtre : les deux biens du jeu de test, dans deux régions.
    tous = client.get("/api/regions").json()["regions"]
    par_region = {r["region"]: r["nb_biens"] for r in tous}
    assert par_region["Normandie"] == 1          # la fermette de Bellême
    assert par_region["Hauts-de-France"] == 1    # le pavillon de Beauvais

    # Avec le filtre « cave » : seule la fermette correspond.
    filtre = client.get("/api/regions", params={"cave": 1}).json()["regions"]
    par_region = {r["region"]: r["nb_biens"] for r in filtre}
    assert par_region["Normandie"] == 1
    assert par_region["Hauts-de-France"] == 0

    # Et le compte de la pastille égale bien le total de la liste filtrée.
    liste = client.get("/api/annonces", params={"cave": 1, "region": "Normandie"}).json()
    assert liste["total"] == par_region["Normandie"]


def test_le_filtre_d_inondation_reconnait_le_risque_communal(tmp_path, monkeypatch):
    """Bug muet : la case « inondation » ne filtrait plus rien.

    Les risques Géorisques ont été renommés `*_commune` pour dire leur
    portée réelle, mais le chargement lisait toujours la clé `inondation`.
    Plus aucun bien n'était donc marqué inondable : 133 biens sur 133
    passaient la case, dont 86 dans une commune documentée inondable.
    """
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "inond.db"))
    from app import db
    from app.chargement import charger_liste

    # Prix et surfaces distincts : trois biens au signalement identique sont
    # écartés par le garde-fou anti-bandeau (_signatures_suspectes).
    base = {"source": "test", "type_bien": "maison", "commune": "Bellême",
            "code_postal": "61130", "lat": 48.373, "lon": 0.560}
    conn = db.connexion()
    charges = charger_liste(conn, [
        {**base, "id": "sec", "titre": "Maison de bourg au sec",
         "prix": 200000, "surface_m2": 120, "risques": {}},
        {**base, "id": "commune", "titre": "Maison de bourg près du ru",
         "prix": 210000, "surface_m2": 130, "risques": {"inondation_commune": True}},
        {**base, "id": "parcelle", "titre": "Maison de bourg dans le val",
         "prix": 220000, "surface_m2": 140, "risques": {"inondation": True}},
    ])
    assert charges == 3
    try:
        total, items = db.chercher(conn, {"hors_inondation": 1, "limit": 50})
    finally:
        conn.close()
    assert total == 1, "le risque communal ET le risque à la parcelle doivent écarter"
    assert items[0]["id"] == "sec"


def test_le_filtre_de_region_n_ecrase_pas_les_autres_pastilles(client):
    """Compter par région en appliquant le filtre de région mettrait toutes
    les autres à zéro : ce filtre-là doit être ignoré."""
    r = client.get("/api/regions", params={"region": "Normandie"}).json()["regions"]
    par_region = {x["region"]: x["nb_biens"] for x in r}
    assert par_region["Hauts-de-France"] == 1    # toujours comptée
