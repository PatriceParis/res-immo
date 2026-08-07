"""Serveur web de Refuge Immo : API de recherche + interface.

Lancement :  python -m uvicorn app.main:app   puis  http://localhost:8000
Au premier démarrage, la base est remplie avec les annonces RÉELLES collectées
(data/annonces_reel.json) — il n'y a plus de jeu de démonstration.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    troglodyte: int = 0,
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
def liste_regions(
    prix_min: int | None = None,
    prix_max: int | None = None,
    temps_max: int | None = None,
    surface_min: int | None = None,
    terrain_min: int | None = None,
    score_min: int | None = None,
    cave: int = 0,
    puits: int = 0,
    bois: int = 0,
    solaire: int = 0,
    dependances: int = 0,
    potager: int = 0,
    troglodyte: int = 0,
    hors_inondation: int = 0,
    type_bien: str | None = None,
    agence: str | None = None,
    q: str | None = None,
):
    """Classement de résilience des terroirs + nombre de biens par région.

    Les comptes tiennent compte des **filtres courants** : une pastille qui
    annonce « 60 biens » alors que la liste filtrée n'en montre que 2 induit
    l'utilisateur en erreur. Le filtre de région lui-même est ignoré, sinon
    toutes les autres régions tomberaient à zéro.
    """
    filtres = {k: v for k, v in locals().items()}
    assurer_donnees()
    conn = db.connexion()
    try:
        comptes = db.comptes_par_region(conn, filtres)
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


RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[a-z]{2,}$", re.IGNORECASE)


class DemandeContact(BaseModel):
    """Demande de mise en relation avec l'agence qui détient le mandat."""

    annonce_id: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    message: str = Field(default="", max_length=1000)


@app.post("/api/contact")
def demander_contact(demande: DemandeContact):
    """Enregistre une demande de mise en relation et renvoie de quoi aboutir.

    C'est le modèle économique du service : gratuit pour l'acheteur, rémunéré
    à la mise en relation qualifiée. On ne conserve que l'e-mail et le
    message — le strict nécessaire pour recontacter — et la réponse contient
    le lien vers l'annonce d'origine, pour que la démarche aboutisse même si
    l'agence tarde.
    """
    if not RE_EMAIL.match(demande.email.strip()):
        raise HTTPException(status_code=422, detail="Adresse e-mail invalide")

    assurer_donnees()
    conn = db.connexion()
    try:
        row = conn.execute(
            "SELECT titre, commune, agence, agence_url, url FROM annonces WHERE id = ?",
            (demande.annonce_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable")

    # Journal des demandes, hors du dépôt (et hors de /tmp en local) : il
    # contient une donnée personnelle, il n'a rien à faire dans Git.
    ligne = {
        "recu_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "annonce_id": demande.annonce_id,
        "email": demande.email.strip(),
        "message": demande.message.strip()[:1000],
        "agence": row["agence"],
    }
    try:
        journal = db.chemin_db().parent / "demandes_contact.jsonl"
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except OSError:
        # Un journal indisponible ne doit pas faire échouer la demande de
        # l'utilisateur : il a droit à sa réponse et au lien vers l'agence.
        pass

    return {
        "ok": True,
        "agence": row["agence"],
        "annonce": row["titre"],
        "commune": row["commune"],
        "url": row["url"] or row["agence_url"] or "",
    }


_UA_NAV = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def referer_de_la_page(page: str | None, cible) -> str:
    """Le Referer qu'enverrait un navigateur affichant `page`.

    À défaut de page exploitable (absente, relative, autre protocole), on se
    rabat sur le domaine de l'image : c'est ce qui se faisait avant, et cela
    convient tant que l'agence héberge ses photos chez elle.
    """
    if page:
        origine = urlparse(page)
        if origine.scheme in ("http", "https") and origine.hostname:
            return f"{origine.scheme}://{origine.netloc}/"
    return f"{cible.scheme}://{cible.hostname}/"


@app.get("/api/photo")
def proxy_photo(u: str, p: str | None = None):
    """Relaie une image d'agence depuis NOTRE domaine.

    Les CDN d'agences bloquent souvent le « hotlink » (image chargée depuis un
    autre site) : le navigateur n'affichait donc rien sur Vercel. En passant par
    ce relais, l'image est servie depuis res-immo.vercel.app et s'affiche.

    `p` est la page de l'annonce d'où vient l'image. C'est elle qui donne le
    bon Referer : un navigateur qui affiche cette page réclame l'image AVEC
    l'adresse de la page. Beaucoup d'agences hébergent leurs photos sur un CDN
    d'un autre domaine (groupe123immo.com → staticlbi.com) ; se réclamer du
    CDN lui-même, comme on le faisait, n'imite aucun navigateur réel. Sans
    `p`, on retombe sur l'ancien comportement, qui suffit aux agences qui
    hébergent leurs images chez elles.
    """
    cible = urlparse(u)
    if cible.scheme not in ("http", "https") or not cible.hostname:
        raise HTTPException(status_code=400, detail="URL invalide")
    # Anti-SSRF : on refuse les adresses privées / locales.
    try:
        for infos in socket.getaddrinfo(cible.hostname, None):
            ip = ipaddress.ip_address(infos[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(status_code=400, detail="hôte non autorisé")
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="hôte introuvable")

    # On imite le navigateur affichant la PAGE de l'annonce : c'est cette
    # adresse-là que vérifient les protections anti-hotlink des CDN.
    req = urllib.request.Request(u, headers={
        "User-Agent": _UA_NAV,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": referer_de_la_page(p, cible),
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
