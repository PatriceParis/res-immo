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
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, pages, redaction, regions, seo
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
    gare: str | None = Query(None, description="Nom exact de la gare desservant le bien"),
    train_max: int | None = Query(None, description="Paris en N minutes de train au plus"),
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
    gare: str | None = None,
    train_max: int | None = None,
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


@app.get("/api/gares")
def liste_gares(
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
    region: str | None = None,
    train_max: int | None = None,
    q: str | None = None,
):
    """Gares desservant les biens, classées par temps de trajet vers Paris.

    Les comptes suivent les filtres courants, pour la même raison que les
    pastilles de terroir : un menu qui annonce « Creil (12) » quand la liste
    n'en montrerait aucun serait faux.
    """
    filtres = {k: v for k, v in locals().items()}
    assurer_donnees()
    conn = db.connexion()
    try:
        return {"gares": db.gares(conn, filtres)}
    finally:
        conn.close()


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


# --- Pages rendues par le SERVEUR, pour les moteurs et les IA --------------
#
# L'interface est une page unique rendue en JavaScript : un robot qui ne
# l'exécute pas — c'est le cas de la plupart des robots d'IA — n'y voit rien.
# Ces routes servent le même catalogue en HTML. Voir app/pages.py.


def _base(requete: Request) -> str:
    """L'adresse publique du site, telle que le visiteur l'a demandée.

    Écrite en dur, elle serait fausse en local et sur les déploiements de
    prévisualisation Vercel — donc des canoniques fausses, ce qui est pire
    que pas de canonique du tout.
    """
    return str(requete.base_url).rstrip("/") or seo.SITE


def _catalogue() -> list[dict]:
    """Les biens tels que le site les sert : préparés, filtrés et notés.

    On lit la base directement plutôt que `db.chercher`, qui plafonne à cinq
    cents résultats pour protéger l'API. Un plan du site tronqué laisserait
    la moitié du catalogue hors de l'index sans que rien ne le signale.
    """
    assurer_donnees()
    conn = db.connexion()
    try:
        lignes = conn.execute("SELECT * FROM annonces").fetchall()
    finally:
        conn.close()
    return [db._row_vers_dict(ligne) for ligne in lignes]


def _mediane(valeurs):
    v = sorted(x for x in valeurs if x is not None)
    return v[len(v) // 2] if v else None


def _stats_terroir(biens: list[dict]) -> dict:
    communes = [b.get("commune") for b in biens if b.get("commune")]
    connus = [b for b in biens if b.get("hors_inondation") is not None]
    return {
        "communes": len(set(communes)),
        "communes_frequentes": Counter(communes).most_common(),
        "prix_median": _mediane(b.get("prix") for b in biens),
        "surface_mediane": _mediane(b.get("surface_m2") for b in biens),
        "altitude_mediane": (
            round(_mediane(b.get("altitude") for b in biens))
            if any(b.get("altitude") is not None for b in biens) else None),
        "part_hors_inondation": (
            round(100 * sum(1 for b in connus if b["hors_inondation"]) / len(connus))
            if connus else None),
    }


@app.get("/robots.txt")
def robots(requete: Request):
    return PlainTextResponse(seo.robots_txt(_base(requete)),
                             headers={"Cache-Control": "public, max-age=3600"})


@app.get("/llms.txt")
def llms(requete: Request):
    biens = _catalogue()
    par_region = Counter(b.get("region") for b in biens if b.get("region"))
    return PlainTextResponse(
        seo.llms_txt(len(biens), dict(par_region), _base(requete)),
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/sitemap.xml")
def plan_du_site(requete: Request):
    biens = _catalogue()
    regions = {b.get("region") for b in biens if b.get("region")}
    return Response(seo.sitemap(biens, regions, _base(requete)),
                    media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/terroir/{terroir}")
def page_terroir(terroir: str, requete: Request):
    region = seo.region_du_slug(terroir)
    if not region:
        raise HTTPException(status_code=404, detail="terroir inconnu")
    biens = [b for b in _catalogue() if b.get("region") == region]
    if not biens:
        raise HTTPException(status_code=404, detail="aucun bien sur ce terroir")
    biens.sort(key=lambda b: b.get("score_total") or 0, reverse=True)
    return HTMLResponse(
        pages.page_terroir(region, biens, _stats_terroir(biens), _base(requete)),
        headers={"Cache-Control": "public, max-age=1800"})


@app.get("/annonce/{descriptif}/{identifiant}")
def page_annonce(descriptif: str, identifiant: str, requete: Request):
    biens = _catalogue()
    bien = next((b for b in biens if b.get("id") == identifiant), None)
    if bien is None:
        # 410 et non 404 : le bien a existé, il a été vendu ou retiré. Le
        # moteur retire alors la page de son index sans attendre des semaines,
        # et sans compter l'adresse comme une erreur de notre part.
        raise HTTPException(status_code=410, detail="ce bien n'est plus suivi")
    if descriptif != seo.descriptif_annonce(bien):
        # Une seule adresse par bien. Le titre évolue au fil des collectes —
        # prix révisé, surface corrigée — et sans cette redirection le même
        # bien s'indexerait sous plusieurs adresses.
        return RedirectResponse(seo.url_annonce(bien), status_code=301)
    voisins = sorted(
        (b for b in biens if b.get("region") == bien.get("region")
         and b.get("id") != bien.get("id")),
        key=lambda b: b.get("score_total") or 0, reverse=True)
    return HTMLResponse(
        pages.page_annonce(bien, voisins, _base(requete),
                           redaction.contexte_departemental(biens)),
        headers={"Cache-Control": "public, max-age=1800"})


# L'interface web (fichiers statiques) est servie en dernier, sous la racine.
app.mount("/", StaticFiles(directory=RACINE / "app" / "static", html=True), name="static")
