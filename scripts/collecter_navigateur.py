"""Collecte via un VRAI navigateur (Chromium/Playwright), sitemap en priorité.

Stratégie, pour chaque agence :
  1. on lit son **sitemap.xml** (qui liste directement les pages de biens) ;
  2. à défaut, on ouvre la (les) page(s) « nos biens » (champ `index`) et on y
     relève les liens vers les annonces ;
  3. on ouvre chaque page d'annonce dans un vrai navigateur (exécution du
     JavaScript), on lit les données schema.org — sinon le texte (prix en €,
     m²…) via app.extraction — on géocode la commune, on calcule le score et
     on enregistre.

Ce n'est pas un déguisement : c'est réellement un navigateur Chrome.

Installation (une fois) :  pip install playwright && playwright install chromium

Usage :
    python scripts/collecter_navigateur.py                       # agences_sites.json
    python scripts/collecter_navigateur.py -s https://agence.fr --index https://agence.fr/nos-biens
Options : --max 12 (biens/agence), --delai 2.5 (s entre pages).

Usage personnel — voir docs/LEGAL.md. Un vrai navigateur ne franchit pas
toutes les protections ; le script s'arrête proprement et l'indique.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db  # noqa: E402
from app.chargement import preparer_annonce  # noqa: E402
from app.extraction import extraire_annonce  # noqa: E402
from app.qualite import est_bien_valide, est_vendu  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright n'est pas installé :\n"
          "  pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

CONFIG = RACINE / "scraper" / "refuge_scraper" / "agences_sites.json"
MOTIF_BIEN = re.compile(
    r"/(annonces?|biens?|vente|vendre|a-vendre|property|properties|nos-biens|detail|ref|maison|propriete)[-/]",
    re.IGNORECASE,
)
UA = os.environ.get(
    "REFUGE_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
)
RE_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)


def _slug(nom: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (nom or "agence").lower()).strip("-")


def _cibles(site: str, nom: str, index: str) -> list[dict]:
    if site:
        return [{"nom": nom or urlparse(site).netloc, "site": site.rstrip("/"),
                 "index": [index] if index else []}]
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("agences", [])
    except (OSError, ValueError):
        print(f"Config illisible : {CONFIG}")
        return []


def _sitemap_urls(base: str) -> list[str]:
    """URLs de pages de biens listées dans le sitemap.xml (via requests)."""
    if requests is None:
        return []
    entetes = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"}
    for chemin in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        try:
            r = requests.get(base + chemin, headers=entetes, timeout=15)
        except Exception:
            continue
        if r.status_code != 200 or "<loc" not in r.text.lower():
            continue
        locs = RE_LOC.findall(r.text)
        detail, sous = [], []
        for u in locs:
            (sous if u.lower().endswith(".xml") else detail).append(u)
        for su in sous[:15]:            # suivre les sous-sitemaps une fois
            try:
                detail += RE_LOC.findall(requests.get(su, headers=entetes, timeout=15).text)
            except Exception:
                pass
        biens = [u for u in dict.fromkeys(detail) if MOTIF_BIEN.search(u)]
        if biens:
            return biens
    return []


def _liens_page(page, base: str) -> list[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))") or []
    urls, vus, hote = [], set(), urlparse(base).netloc
    for h in hrefs:
        if not h:
            continue
        u = urljoin(base, h).split("#")[0]
        if urlparse(u).netloc == hote and MOTIF_BIEN.search(u) and u not in vus:
            vus.add(u)
            urls.append(u)
    return urls


def _ban(params: dict):
    """Base Adresse Nationale ; renvoie (lat, lon, ville, cp, codeINSEE) ou None."""
    if requests is None:
        return None
    try:
        r = requests.get("https://api-adresse.data.gouv.fr/search/", params=params,
                         timeout=8, headers={"User-Agent": "RefugeImmo-POC"})
        r.raise_for_status()
        feats = r.json().get("features") or []
    except Exception:
        return None
    if not feats:
        return None
    pr = feats[0]["properties"]
    lon, lat = feats[0]["geometry"]["coordinates"]
    return lat, lon, (pr.get("city") or pr.get("name")), pr.get("postcode"), pr.get("citycode")


def _densite(citycode):
    """Densité de population (hab/km²) de la commune via geo.api.gouv.fr."""
    if not citycode or requests is None:
        return None
    try:
        r = requests.get(f"https://geo.api.gouv.fr/communes/{citycode}",
                         params={"fields": "population,surface"}, timeout=8,
                         headers={"User-Agent": "RefugeImmo-POC"})
        r.raise_for_status()
        d = r.json()
    except Exception:
        return None
    pop, surf = d.get("population"), d.get("surface")  # surface en hectares
    return round(pop / (surf / 100.0), 1) if pop and surf else None


def _altitude(lat, lon):
    """Altitude (m) de la position via l'API open-meteo (best-effort)."""
    if lat is None or lon is None or requests is None:
        return None
    try:
        r = requests.get("https://api.open-meteo.com/v1/elevation",
                         params={"latitude": lat, "longitude": lon}, timeout=8,
                         headers={"User-Agent": "RefugeImmo-POC"})
        r.raise_for_status()
        vals = r.json().get("elevation") or []
    except Exception:
        return None
    return round(vals[0]) if vals and isinstance(vals[0], (int, float)) else None


def _geocoder(commune, cp):
    if not commune:
        return None
    return _ban({"q": f"{commune} {cp or ''}".strip(), "type": "municipality", "limit": 1})


def _geocoder_cp(cp):
    """Géocode par code postal (fiable) : renvoie la commune principale du CP."""
    if not cp:
        return None
    return _ban({"q": str(cp), "type": "municipality", "limit": 1})


def _geocoder_texte(texte):
    """Repli : cherche une COMMUNE citée dans le titre (type=municipality pour
    ne jamais tomber sur une adresse au hasard, ex. un titre vague → Orléans)."""
    if not texte:
        return None
    return _ban({"q": texte[:80], "type": "municipality", "limit": 1})


def _urls_a_visiter(page, cible: dict, base: str, maxi: int) -> list[str]:
    # On récupère BEAUCOUP plus d'URL que de biens voulus : beaucoup de pages
    # sont écartées ensuite (biens vendus, appartements, pages catalogue). La
    # boucle d'appel s'arrête d'elle-même une fois `maxi` biens VALIDES gardés.
    vivier = max(maxi * 8, 80)
    urls = _sitemap_urls(base)
    if urls:
        print(f"  sitemap : {len(urls)} page(s) de biens")
        return urls[:vivier]
    # repli : on parcourt les pages « nos biens »
    urls = []
    for idx in (cible.get("index") or [base]):
        try:
            page.goto(idx, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1800)
        except Exception as e:
            print(f"  ✘ index injoignable {idx} ({e.__class__.__name__})")
            continue
        for u in _liens_page(page, base):
            if u not in urls:
                urls.append(u)
    # depuis un index, on ne garde que les liens qui ressemblent à un détail
    # (un chiffre dans le chemin) pour éviter les pages de catégorie.
    details = [u for u in urls if re.search(r"\d", urlparse(u).path)]
    choix = details or urls
    print(f"  index : {len(choix)} lien(s) de bien repéré(s)")
    return choix[:vivier]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-s", "--site", default="")
    ap.add_argument("-n", "--nom", default="")
    ap.add_argument("--index", default="")
    ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--delai", type=float, default=0.9)
    # Plafond de pages ouvertes par agence : une agence dont tout le catalogue
    # est vendu ne doit pas consommer le temps des autres.
    ap.add_argument("--pages-max", type=int, default=30)
    # Budget de temps global : on rend la main proprement avant que le runner
    # CI ne coupe le job, sinon l'export et le commit ne tournent jamais.
    ap.add_argument("--minutes-max", type=float, default=40.0)
    args = ap.parse_args()

    conn = db.connexion()
    total = 0
    fin_prevue = time.monotonic() + args.minutes_max * 60
    with sync_playwright() as p:
        navigateur = p.chromium.launch(
            executable_path=os.environ.get("REFUGE_CHROMIUM") or None, headless=True)
        contexte = navigateur.new_context(
            user_agent=UA, locale="fr-FR",
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
        page = contexte.new_page()

        for cible in _cibles(args.site, args.nom, args.index):
            if time.monotonic() > fin_prevue:
                print("\n⏱ Budget de temps atteint : on s'arrête là pour que "
                      "l'export et l'enregistrement aient lieu.")
                break
            base = cible["site"].rstrip("/")
            # Réglages par agence : `max` (biens voulus) et `pages` (pages à
            # ouvrir). Utile là où le catalogue est gros mais commence par des
            # biens vendus — il faut creuser plus loin pour trouver du dispo —
            # et pour ne pas laisser un seul terroir occuper toute la liste.
            maxi = int(cible.get("max") or args.max)
            pages_max = int(cible.get("pages") or args.pages_max)
            print(f"\n▶ {cible['nom']} — {base}")
            urls = _urls_a_visiter(page, cible, base, maxi)
            n, vendus, ecartes, vues = 0, 0, 0, 0
            for u in urls:
                if n >= maxi:          # on s'arrête sur les biens GARDÉS,
                    break              # pas sur les pages visitées
                if vues >= pages_max:
                    print(f"  … plafond de {pages_max} pages atteint pour cette agence")
                    break
                if time.monotonic() > fin_prevue:
                    break
                vues += 1
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(600)
                    html = page.content()
                except Exception:
                    continue
                brut = extraire_annonce(html, u, source=_slug(cible["nom"]),
                                        agence=cible["nom"], agence_url=base)
                if not brut:
                    continue
                # Rejette les pages où l'extraction n'a pas trouvé un vrai titre
                # d'annonce (titre = nom de l'agence / du site) : peu exploitables.
                titre_bas = (brut.get("titre") or "").strip().lower()
                hote = urlparse(base).netloc.replace("www.", "")
                if not titre_bas or titre_bas in (cible["nom"].lower(), hote):
                    continue
                # Filtre qualité : vrai logement de type refuge, encore à vendre
                # (écarte blog, catalogue, appartement, terrain nu, bien vendu…).
                if est_vendu(brut):
                    vendus += 1
                    continue
                if not est_bien_valide(brut):
                    ecartes += 1
                    continue
                brut["id"] = "%s-%s" % (_slug(cible["nom"]),
                                        hashlib.sha1(u.encode()).hexdigest()[:12])
                if brut.get("lat") is None:
                    geo = (_geocoder(brut.get("commune"), brut.get("code_postal"))
                           or _geocoder_cp(brut.get("code_postal"))
                           or _geocoder_texte(brut.get("titre")))
                    if geo:
                        brut["lat"], brut["lon"], ville, cp, citycode = geo
                        if ville and not brut.get("commune"):
                            brut["commune"] = ville
                        if cp:
                            brut["code_postal"] = brut.get("code_postal") or cp
                            brut["departement"] = brut.get("departement") or str(cp)[:2]
                        if brut.get("densite_hab_km2") is None:
                            brut["densite_hab_km2"] = _densite(citycode)
                # Altitude (pilier Situation) une fois la position connue.
                if brut.get("altitude") is None and brut.get("lat") is not None:
                    brut["altitude"] = _altitude(brut["lat"], brut["lon"])
                db.upsert_annonce(conn, preparer_annonce(brut))
                n += 1
                time.sleep(args.delai)
            conn.commit()
            print(f"  ✔ {n} bien(s) enregistré(s)"
                  f" — {vendus} déjà vendu(s), {ecartes} hors cible")
            total += n

        navigateur.close()
    conn.close()
    print(f"\nTerminé : {total} bien(s) réel(s) ajouté(s). Rechargez l'application.")


if __name__ == "__main__":
    main()
