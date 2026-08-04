"""Serveur web de Refuge Immo : API de recherche + interface.

Lancement :  python -m uvicorn app.main:app   puis  http://localhost:8000
Au premier démarrage, la base est remplie avec les annonces RÉELLES collectées
(data/annonces_reel.json) — il n'y a plus de jeu de démonstration.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles

from . import db, regions
from .chargement import charger_liste

RACINE = Path(__file__).resolve().parent.parent
# Annonces RÉELLES collectées (scripts/collecter*.py ou la GitHub Action).
# C'est désormais la SEULE source du site — il n'y a plus de jeu de démonstration.
REEL = RACINE / "data" / "annonces_reel.json"

_amorce_faite = False


def assurer_donnees() -> None:
    """Charge en base les annonces réelles (data/annonces_reel.json) si vide.

    Appelée au début de chaque route car, en serverless (Vercel), l'événement
    de démarrage n'est pas toujours exécuté et la base /tmp est réinitialisée.
    """
    global _amorce_faite
    if _amorce_faite:
        return
    conn = db.connexion()
    try:
        if db.nb_annonces(conn) == 0 and REEL.exists():
            try:
                biens = json.loads(REEL.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                biens = []
            if biens:
                charger_liste(conn, biens)
                print(f"✔ {len(biens)} annonce(s) réelle(s) chargée(s).")
    finally:
        conn.close()
    _amorce_faite = True


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    assurer_donnees()
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
    region: str | None = None,
    agence: str | None = None,
    q: str | None = Query(None, description="Recherche texte (titre, description, commune)"),
    tri: str = "score",
    limit: int = 200,
    offset: int = 0,
):
    filtres = {k: v for k, v in locals().items()}
    assurer_donnees()
    conn = db.connexion()
    try:
        total, items = db.chercher(conn, filtres)
    finally:
        conn.close()
    return {"total": total, "items": items}


@app.get("/api/annonces/{annonce_id}")
def detail_annonce(annonce_id: str):
    assurer_donnees()
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
    assurer_donnees()
    conn = db.connexion()
    try:
        return db.meta(conn)
    finally:
        conn.close()


@app.get("/api/regions")
def liste_regions():
    """Classement de résilience des terroirs + nombre de biens par région."""
    assurer_donnees()
    conn = db.connexion()
    try:
        comptes = {r["region"]: r["nb"] for r in conn.execute(
            "SELECT region, COUNT(*) nb FROM annonces GROUP BY region").fetchall()}
    finally:
        conn.close()
    classement = regions.classement()
    for r in classement:
        r["nb_biens"] = comptes.get(r["region"], 0)
    return {"regions": classement, "cibles": regions.regions_cibles()}


@app.get("/api/agences")
def agences():
    """Agences présentes en base (nom, site, nombre de biens, score moyen)."""
    assurer_donnees()
    conn = db.connexion()
    try:
        return {"agences": db.agences(conn)}
    finally:
        conn.close()


_UA_NAV = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


@app.get("/api/photo")
def proxy_photo(u: str):
    """Relaie une image d'agence depuis NOTRE domaine.

    Les CDN d'agences bloquent souvent le « hotlink » (image chargée depuis un
    autre site) : le navigateur n'affichait donc rien sur Vercel. En passant par
    ce relais, l'image est servie depuis res-immo.vercel.app et s'affiche.
    """
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise HTTPException(status_code=400, detail="URL invalide")
    # Anti-SSRF : on refuse les adresses privées / locales.
    try:
        for infos in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(infos[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(status_code=400, detail="hôte non autorisé")
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="hôte introuvable")

    # On imite le navigateur chargeant l'image DEPUIS le site de l'agence
    # (Referer + Origin de son propre domaine) : c'est ce que vérifient la
    # plupart des protections anti-hotlink des CDN.
    req = urllib.request.Request(u, headers={
        "User-Agent": _UA_NAV,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": f"{p.scheme}://{p.hostname}/",
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            ct = (r.headers.get("Content-Type") or "").split(";")[0].strip()
            if not ct.startswith("image/"):
                raise HTTPException(status_code=415, detail="pas une image")
            data = r.read(6_000_000)  # plafond ~6 Mo
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="image injoignable")
    return Response(content=data, media_type=ct or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


# L'interface web (fichiers statiques) est servie en dernier, sous la racine.
app.mount("/", StaticFiles(directory=RACINE / "app" / "static", html=True), name="static")
