"""Serveur web de Refuge Immo : API de recherche + interface.

Lancement :  python -m uvicorn app.main:app   puis  http://localhost:8000
Au premier démarrage, si la base est vide, le jeu de démonstration
(data/annonces_demo.json) est chargé automatiquement.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from . import db
from .chargement import charger_annonces_json

RACINE = Path(__file__).resolve().parent.parent
DEMO = RACINE / "data" / "annonces_demo.json"


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    conn = db.connexion()
    try:
        if db.nb_annonces(conn) == 0 and DEMO.exists():
            n = charger_annonces_json(conn, DEMO)
            print(f"✔ Base vide : {n} annonces de démonstration chargées.")
    finally:
        conn.close()
    yield


app = FastAPI(title="Refuge Immo", version="0.1.0", lifespan=cycle_de_vie)


@app.get("/api/annonces")
def liste_annonces(
    prix_min: int | None = None,
    prix_max: int | None = None,
    temps_max: int | None = Query(None, description="Temps de route max depuis Paris (minutes)"),
    surface_min: int | None = None,
    terrain_min: int | None = None,
    score_min: int | None = None,
    cave: int = 0,
    puits: int = 0,
    bois: int = 0,
    solaire: int = 0,
    dependances: int = 0,
    potager: int = 0,
    hors_inondation: int = 0,
    type_bien: str | None = None,
    q: str | None = Query(None, description="Recherche texte (titre, description, commune)"),
    tri: str = "score",
    limit: int = 200,
    offset: int = 0,
):
    filtres = {k: v for k, v in locals().items()}
    conn = db.connexion()
    try:
        total, items = db.chercher(conn, filtres)
    finally:
        conn.close()
    return {"total": total, "items": items}


@app.get("/api/annonces/{annonce_id}")
def detail_annonce(annonce_id: str):
    conn = db.connexion()
    try:
        row = conn.execute("SELECT * FROM annonces WHERE id = ?", (annonce_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    return db._row_vers_dict(row)


@app.get("/api/meta")
def meta():
    conn = db.connexion()
    try:
        return db.meta(conn)
    finally:
        conn.close()


# L'interface web (fichiers statiques) est servie en dernier, sous la racine.
app.mount("/", StaticFiles(directory=RACINE / "app" / "static", html=True), name="static")
