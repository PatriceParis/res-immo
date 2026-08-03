"""Collecte via un VRAI navigateur (Chromium piloté par Playwright).

Un simple User-Agent suffit pour beaucoup de sites, mais certains portails
protégés par un anti-robots avancé (Cloudflare…) exigent un vrai navigateur
qui exécute le JavaScript. Ce script pilote Chromium, ouvre les pages
d'annonces des agences, lit les données schema.org (via app.extraction),
géocode la commune si besoin, calcule le score et enregistre les biens.

Ce n'est pas un « déguisement » : c'est réellement un navigateur Chrome.

Installation (une seule fois, sur votre machine) :
    pip install playwright && playwright install chromium

Usage :
    python scripts/collecter_navigateur.py -s https://une-agence.fr
    python scripts/collecter_navigateur.py -s https://une-agence.fr --index https://une-agence.fr/nos-biens
    python scripts/collecter_navigateur.py            # toutes les agences de agences.json
Options : --max 25 (biens/agence), --delai 3 (secondes entre pages).

À réserver à une veille personnelle — voir docs/LEGAL.md. Même un vrai
navigateur ne franchit pas toutes les protections : le script s'arrête
proprement et l'indique dans le journal si un site résiste.
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

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright n'est pas installé. Sur votre machine :\n"
          "  pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

ANNUAIRE = RACINE / "scraper" / "refuge_scraper" / "agences.json"
MOTIF_BIEN = re.compile(
    r"/(annonces?|biens?|vente|vendre|a-vendre|property|properties|nos-biens|detail|ref)[-/]",
    re.IGNORECASE,
)
UA = os.environ.get(
    "REFUGE_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
)


def _slug(nom: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (nom or "agence").lower()).strip("-")


def _cibles(site: str, nom: str) -> list[dict]:
    if site:
        return [{"nom": nom or urlparse(site).netloc, "site": site.rstrip("/")}]
    try:
        return json.loads(ANNUAIRE.read_text(encoding="utf-8")).get("agences", [])
    except (OSError, ValueError):
        print(f"Annuaire illisible : {ANNUAIRE}")
        return []


def _liens_biens(page, base: str) -> list[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))") or []
    urls, vus = [], set()
    hote = urlparse(base).netloc
    for h in hrefs:
        if not h:
            continue
        u = urljoin(base, h)
        if urlparse(u).netloc == hote and MOTIF_BIEN.search(u) and u not in vus:
            vus.add(u)
            urls.append(u)
    return urls


def _geocoder(commune: str | None, cp: str | None):
    """Coordonnées de la commune via la Base Adresse Nationale (facultatif)."""
    if not commune or requests is None:
        return None
    try:
        r = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={"q": f"{commune} {cp or ''}".strip(), "type": "municipality", "limit": 1},
            timeout=8, headers={"User-Agent": "RefugeImmo-POC"})
        r.raise_for_status()
        feats = r.json().get("features") or []
    except Exception:
        return None
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"]
    return lat, lon, feats[0]["properties"].get("postcode")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-s", "--site", default="", help="site d'une agence")
    ap.add_argument("-n", "--nom", default="", help="nom de l'agence")
    ap.add_argument("--index", default="", help="page listant les annonces (sinon accueil)")
    ap.add_argument("--max", type=int, default=25, help="biens max par agence")
    ap.add_argument("--delai", type=float, default=3.0, help="secondes entre deux pages")
    args = ap.parse_args()

    conn = db.connexion()
    total = 0
    with sync_playwright() as p:
        navigateur = p.chromium.launch(
            executable_path=os.environ.get("REFUGE_CHROMIUM") or None, headless=True)
        contexte = navigateur.new_context(
            user_agent=UA, locale="fr-FR",
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
        page = contexte.new_page()

        for cible in _cibles(args.site, args.nom):
            base = cible["site"].rstrip("/")
            depart = args.index or base
            print(f"\n▶ {cible['nom']} — {depart}")
            try:
                page.goto(depart, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"  ✘ page de départ injoignable ({e.__class__.__name__})")
                continue

            urls = _liens_biens(page, base)[:args.max]
            print(f"  {len(urls)} page(s) d'annonce repérée(s)")
            n = 0
            for u in urls:
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(800)
                    html = page.content()
                except Exception:
                    continue
                brut = extraire_annonce(html, u, source=_slug(cible["nom"]),
                                        agence=cible["nom"], agence_url=base)
                if brut:
                    brut["id"] = "%s-%s" % (_slug(cible["nom"]),
                                            hashlib.sha1(u.encode()).hexdigest()[:12])
                    if brut.get("lat") is None and brut.get("commune"):
                        geo = _geocoder(brut.get("commune"), brut.get("code_postal"))
                        if geo:
                            brut["lat"], brut["lon"], cp = geo
                            brut.setdefault("code_postal", cp)
                            if cp:
                                brut["departement"] = cp[:2]
                    db.upsert_annonce(conn, preparer_annonce(brut))
                    n += 1
                time.sleep(args.delai)
            conn.commit()
            print(f"  ✔ {n} bien(s) enregistré(s)")
            total += n

        navigateur.close()
    conn.close()
    print(f"\nTerminé : {total} bien(s) réel(s) ajouté(s). Rechargez l'application.")


if __name__ == "__main__":
    main()
