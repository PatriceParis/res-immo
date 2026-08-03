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
            "id": "t-2", "source": "test", "titre": "Pavillon simple",
            "description": "Pavillon en lotissement, chauffage électrique.",
            "prix": 450000, "surface_m2": 100, "terrain_m2": 300,
            "commune": "Dourdan", "code_postal": "91410",
            "lat": 48.529, "lon": 2.011, "altitude": 130,
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
