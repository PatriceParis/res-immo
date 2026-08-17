"""Serveur web de Refuge Immo : API de recherche + interface.

Lancement :  python -m uvicorn app.main:app   puis  http://localhost:8000
Au premier démarrage, la base est remplie avec les annonces RÉELLES collectées
(data/annonces_reel.json) — il n'y a plus de jeu de démonstration.
"""

from __future__ import annotations

import json
import re
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


# La mise en relation a été retirée le 17 août 2026, endpoint compris.
#
# Elle recueillait l'e-mail du visiteur pour le transmettre à l'agence, et le
# disait sans détour : « gratuit pour l'acheteur, rémunéré à la mise en
# relation qualifiée ». Prêter son concours, même à titre accessoire et contre
# rémunération, à la recherche d'un immeuble pour autrui, c'est l'activité que
# la loi Hoguet réserve aux titulaires d'une carte professionnelle. La phrase
# « Refuge Immo n'est pas une agence immobilière » ne décrivait pas ce que le
# site faisait — et une clause ne défait pas une qualification.
#
# Retirer le bouton sans retirer l'endpoint n'aurait rien réglé : la route
# restait ouverte, et le journal des e-mails avec elle. Ce journal vivait
# d'ailleurs à côté de la base, donc dans /tmp sur l'hébergement, effacé à
# chaque redémarrage : les adresses recueillies étaient perdues sans que
# personne le sache. Collecter une donnée personnelle pour la perdre est le
# pire des deux mondes.
#
# Ce qui remplace : /alertes, où le visiteur choisit lui-même un budget et des
# terroirs, et où c'est NOUS qui lui écrivons. Aucune coordonnée ne part chez
# une agence, aucune commission n'est perçue.


# Le relais /api/photo a été retiré le 10 août 2026. Il republiait chaque
# image depuis notre domaine avec un Referer forgé pour passer les
# protections anti-hotlink — la position la plus fragile juridiquement, et
# construite pour un problème que la mesure n'a pas retrouvé : sonde du
# 10 août, soixante photos sur soixante acceptées en hotlink honnête, trente
# hébergeurs dont IAD, zéro refus. Les photos partent désormais directement
# de chez l'agence, avec notre Referer : elle voit notre trafic, et peut
# nous bloquer d'un réglage si elle le souhaite.

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


@app.get(seo.URL_PETITS_PRIX)
def page_petits_prix(requete: Request):
    """Le seul tri qui distingue cette page des mille autres du même sujet :
    la note d'abord, le prix ensuite. Voir pages.page_petits_prix."""
    catalogue = _catalogue()
    biens = [b for b in catalogue
             if b.get("prix") and b["prix"] <= seo.SEUIL_PETITS_PRIX]
    if not biens:
        raise HTTPException(status_code=404, detail="aucun bien sous ce prix")
    biens.sort(key=lambda b: (-(b.get("score_total") or 0), b.get("prix") or 0))
    notes = [b["score_total"] for b in catalogue if b.get("score_total")]
    stats = _stats_terroir(biens) | {
        "moins_cher": min(b["prix"] for b in biens),
        "bien_notes": sum(1 for b in biens if (b.get("score_total") or 0) >= 40),
        # La médiane de TOUT le catalogue : sans elle, « 27 biens au-dessus de
        # 40 » ne se compare à rien et ne veut rien dire.
        "mediane_generale": round(_mediane(notes)) if notes else None,
    }
    return HTMLResponse(pages.page_petits_prix(biens, stats, _base(requete)),
                        headers={"Cache-Control": "public, max-age=1800"})


@app.get(seo.URL_SANS_TRAVAUX)
def page_sans_travaux(requete: Request):
    """Les biens d'une tranche dont l'ANNONCE dit qu'ils sont prêts.

    On compte aussi les muettes et celles qui annoncent des travaux : sans ces
    deux nombres, « 53 biens sans travaux » ne se compare à rien, et la page ne
    pourrait pas dire ce qu'elle ignore. Voir pages.page_sans_travaux.
    """
    catalogue = _catalogue()
    tranche = [b for b in catalogue
               if b.get("prix")
               and seo.PLANCHER_SANS_TRAVAUX <= b["prix"] <= seo.PLAFOND_SANS_TRAVAUX]
    biens = [b for b in tranche if b.get("sans_travaux")]
    if not biens:
        raise HTTPException(
            status_code=404,
            detail="aucun bien annoncé sans travaux dans cette tranche")
    biens.sort(key=lambda b: (-(b.get("score_total") or 0), b.get("prix") or 0))
    stats = _stats_terroir(biens) | {
        "dans_la_tranche": len(tranche),
        "muettes": sum(1 for b in tranche if b.get("etat_declare") == "inconnu"),
        "avec_travaux": sum(1 for b in tranche if b.get("etat_declare") == "travaux"),
        "bien_notes": sum(1 for b in biens if (b.get("score_total") or 0) >= 40),
    }
    return HTMLResponse(pages.page_sans_travaux(biens, stats, _base(requete)),
                        headers={"Cache-Control": "public, max-age=1800"})


@app.get(seo.URL_ALERTES)
def page_alertes(requete: Request, prix_max: int | None = None,
                 region: str = ""):
    """« Soyez alerté » — ce qui remplace la mise en relation retirée.

    Les paramètres ne servent qu'à PRÉ-REMPLIR le formulaire depuis la fiche
    d'où l'on vient : le visiteur reste libre de tout changer. Rien n'est
    enregistré ici — voir pages.page_alertes pour le pourquoi.
    """
    if region and region not in seo.TERROIRS:
        region = ""
    return HTMLResponse(
        pages.page_alertes({}, prix_max, region, _base(requete)),
        headers={"Cache-Control": "public, max-age=3600"})


@app.get(seo.URL_MENTIONS)
def page_mentions(requete: Request):
    """Qui édite ce site et qui en répond. La loi l'exige, et une agence qui
    veut le retrait de ses annonces doit avoir une porte où frapper."""
    return HTMLResponse(pages.page_mentions_legales(_base(requete)),
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get(seo.URL_METHODE)
def page_methode(requete: Request):
    """Le minimum qui rend la note non trompeuse : sources, millésime,
    échelle, poids des piliers et limites. Pas le barème."""
    return HTMLResponse(pages.page_methode(_base(requete)),
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get(seo.URL_CONFIDENTIALITE)
def page_confidentialite(requete: Request):
    """Ce que le site traite comme données — c'est-à-dire très peu."""
    return HTMLResponse(pages.page_confidentialite(_base(requete)),
                        headers={"Cache-Control": "public, max-age=86400"})


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


class StatiquesDatees(StaticFiles):
    """Les fichiers de l'interface, avec une consigne de cache explicite.

    Sans elle, `StaticFiles` n'envoie AUCUN `Cache-Control`. Le navigateur
    applique alors sa règle par défaut — garder la page un dixième de son âge —
    et l'hébergeur peut en faire autant. Résultat observé le 17 août : le site
    servait encore l'ancien slogan et l'ancien menu plusieurs heures après le
    déploiement, alors que les données affichées, elles, étaient à jour. Le
    plus trompeur des symptômes : la page a l'air vivante, mais son habillage
    date d'avant.

    `no-cache` ne veut pas dire « ne garde rien » : cela veut dire « garde,
    mais demande-moi si c'est encore bon ». Avec l'ETag que `StaticFiles`
    envoie déjà, cette vérification coûte une réponse vide de 304 octets, et
    l'utilisateur ne voit jamais une version périmée.

    La page et ses deux fichiers ne portent aucune empreinte dans leur nom :
    ils doivent donc rester solidaires. Les bibliothèques de `vendor/`, elles,
    sont figées à une version — on peut les garder longtemps sans risque.
    """

    async def get_response(self, path: str, scope):
        reponse = await super().get_response(path, scope)
        if path.startswith("vendor/"):
            reponse.headers["Cache-Control"] = "public, max-age=604800, immutable"
        else:
            reponse.headers["Cache-Control"] = "no-cache"
        return reponse


# L'interface web (fichiers statiques) est servie en dernier, sous la racine.
app.mount("/", StatiquesDatees(directory=RACINE / "app" / "static", html=True),
          name="static")
