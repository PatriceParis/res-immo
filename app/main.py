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
from .chargement import charger_annonces_json, charger_liste

RACINE = Path(__file__).resolve().parent.parent
DEMO = RACINE / "data" / "annonces_demo.json"

_amorce_faite = False


def assurer_demo() -> None:
    """Si la base est vide, charge le jeu de démonstration.

    Depuis le fichier data/annonces_demo.json en local ; généré en mémoire sur
    un hébergement serverless (Vercel), où le disque est en lecture seule et
    où l'événement de démarrage n'est pas toujours exécuté — d'où l'appel de
    cette fonction au début de chaque route de l'API.
    """
    global _amorce_faite
    if _amorce_faite:
        return
    conn = db.connexion()
    try:
        if db.nb_annonces(conn) == 0:
            if DEMO.exists():
                n = charger_annonces_json(conn, DEMO)
            else:
                from .demo import generer_annonces
                n = charger_liste(conn, generer_annonces())
            print(f"✔ Base vide : {n} annonces de démonstration chargées.")
    finally:
        conn.close()
    _amorce_faite = True


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    assurer_demo()
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
    agence: str | None = None,
    q: str | None = Query(None, description="Recherche texte (titre, description, commune)"),
    tri: str = "score",
    limit: int = 200,
    offset: int = 0,
):
    filtres = {k: v for k, v in locals().items()}
    assurer_demo()
    conn = db.connexion()
    try:
        total, items = db.chercher(conn, filtres)
    finally:
        conn.close()
    return {"total": total, "items": items}


@app.get("/api/annonces/{annonce_id}")
def detail_annonce(annonce_id: str):
    assurer_demo()
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
    assurer_demo()
    conn = db.connexion()
    try:
        return db.meta(conn)
    finally:
        conn.close()


@app.get("/api/agences")
def agences():
    """Agences présentes en base (nom, site, nombre de biens, score moyen)."""
    assurer_demo()
    conn = db.connexion()
    try:
        return {"agences": db.agences(conn)}
    finally:
        conn.close()


# L'interface web (fichiers statiques) est servie en dernier, sous la racine.
app.mount("/", StaticFiles(directory=RACINE / "app" / "static", html=True), name="static")
