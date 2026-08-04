"""Découvre les agences immobilières des zones visées et teste leurs sites.

Complète (et remplace en pratique) `decouvrir_agences.py`, qui passait par
l'API d'un portail national — lequel bloque la collecte automatisée. Ici la
source est **OpenStreetMap**, de l'open data sans anti-bot.

Deux étapes, toutes deux menées **en parallèle** :

  1. interrogation d'OpenStreetMap (API Overpass) pour chaque ville : quelles
     agences immobilières y sont recensées, avec quel site web ;
  2. sondage de chaque site candidat : joignable ? sitemap avec des pages de
     biens ? données schema.org ? — c'est ce qui décide s'il est exploitable.

Les sites retenus sont ajoutés à scraper/refuge_scraper/agences_sites.json ;
un rapport complet est écrit dans data/agences_candidates.json pour garder
trace de ce qui a été écarté, et pourquoi.

Usage :
    python scripts/decouvrir_agences_osm.py             # découvre et met à jour
    python scripts/decouvrir_agences_osm.py --simuler   # rapport seul
    python scripts/decouvrir_agences_osm.py --note 40   # exigence plus élevée
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.decouverte import (  # noqa: E402
    ZONES, agences_depuis_overpass, domaine, est_portail_exclu, fusionner,
    fusionner_rapports, requete_overpass, score_candidat, urls_de_biens,
)

try:
    import requests
except ImportError:
    print("Le module 'requests' est nécessaire :  pip install requests")
    sys.exit(1)

CONFIG = RACINE / "scraper" / "refuge_scraper" / "agences_sites.json"
RAPPORT = RACINE / "data" / "agences_candidates.json"
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
ENTETES = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"}
RE_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
RE_JSONLD_IMMO = re.compile(
    r"realestatelisting|singlefamilyresidence|\"@type\"\s*:\s*\"(?:house|product|offer)\"",
    re.IGNORECASE)


def _zone(zone: dict) -> list[dict]:
    """Agences recensées par OpenStreetMap autour d'une ville.

    Overpass n'accorde que quelques créneaux simultanés par adresse IP et
    répond « 429 / trop de requêtes » au-delà : on réessaie, en alternant les
    deux serveurs publics et en patientant un peu plus à chaque tentative.
    Sans cela, la moitié des zones revenait vide alors que les données
    existent bel et bien.
    """
    dernier = ""
    for tentative in range(4):
        service = OVERPASS[tentative % len(OVERPASS)]
        try:
            r = requests.post(service, data={"data": requete_overpass(zone)},
                              headers=ENTETES, timeout=120)
            r.raise_for_status()
            agences = agences_depuis_overpass(r.json(), zone["nom"])
            print(f"  {zone['nom']:20} {len(agences):>3} agence(s) avec site web")
            return agences
        except Exception as e:
            dernier = f"{e.__class__.__name__} ({service.split('/')[2]})"
            time.sleep(4 * (tentative + 1))
    print(f"  {zone['nom']:20} ✘ abandon après 4 tentatives — {dernier}")
    return []


def _sitemap(base: str) -> list[str]:
    """URLs listées dans le sitemap du site (sous-sitemaps suivis une fois)."""
    for chemin in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        try:
            r = requests.get(base + chemin, headers=ENTETES, timeout=20)
        except Exception:
            continue
        if r.status_code != 200 or "<loc" not in r.text.lower():
            continue
        locs = RE_LOC.findall(r.text)
        detail = [u for u in locs if not u.lower().endswith(".xml")]
        for sous in [u for u in locs if u.lower().endswith(".xml")][:10]:
            try:
                detail += RE_LOC.findall(
                    requests.get(sous, headers=ENTETES, timeout=20).text)
            except Exception:
                pass
        return detail
    return []


def _liens_accueil(base: str) -> list[str]:
    """Repli : liens de la page d'accueil, quand il n'y a pas de sitemap."""
    try:
        r = requests.get(base, headers=ENTETES, timeout=20)
        r.raise_for_status()
    except Exception:
        return []
    return [urljoin(base, h) for h in re.findall(r'href=["\']([^"\']+)', r.text)]


def _sonder(agence: dict) -> dict:
    """Le site est-il exploitable ? (joignable, biens listés, schema.org)"""
    base = agence["site"].rstrip("/")
    sonde = {**agence, "joignable": False, "sitemap": False,
             "schema_org": False, "nb_biens": 0, "motif": "", "note": 0}
    try:
        r = requests.get(base, headers=ENTETES, timeout=20, allow_redirects=True)
        sonde["joignable"] = r.status_code < 400
        if not sonde["joignable"]:
            sonde["motif"] = f"HTTP {r.status_code}"
            return sonde
    except Exception as e:
        sonde["motif"] = e.__class__.__name__
        return sonde

    urls = _sitemap(base)
    sonde["sitemap"] = bool(urls)
    biens = urls_de_biens(urls or _liens_accueil(base), base)
    sonde["nb_biens"] = len(biens)

    # Une page de bien au hasard : publie-t-elle des données structurées ?
    if biens:
        try:
            page = requests.get(biens[0], headers=ENTETES, timeout=20)
            sonde["schema_org"] = bool(RE_JSONLD_IMMO.search(page.text))
        except Exception:
            pass
    else:
        sonde["motif"] = "aucune page de bien repérée"
    sonde["note"] = score_candidat(sonde)
    return sonde


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--simuler", action="store_true",
                    help="n'écrit pas la configuration, affiche seulement le rapport")
    ap.add_argument("--note", type=int, default=25,
                    help="note minimale pour brancher une agence (défaut : 25)")
    ap.add_argument("--parallele", type=int, default=12,
                    help="sondages de sites simultanés (défaut : 12)")
    ap.add_argument("--parallele-osm", type=int, default=2,
                    help="requêtes Overpass simultanées — au-delà de 2, l'API refuse")
    args = ap.parse_args()

    # Overpass n'accepte que 2 requêtes simultanées par IP : au-delà, il
    # refuse et les zones reviennent vides. Le sondage des sites, lui, vise
    # des hôtes tous différents et peut rester largement parallèle.
    print(f"1/2 — Recensement OpenStreetMap sur {len(ZONES)} zones "
          f"({args.parallele_osm} en parallèle)")
    candidates: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.parallele_osm) as pool:
        for futur in as_completed([pool.submit(_zone, z) for z in ZONES]):
            candidates += futur.result()

    # Dédoublonnage inter-zones (une agence peut couvrir deux bassins).
    uniques, vues = [], set()
    for c in candidates:
        d = domaine(c["site"])
        if d and d not in vues and not est_portail_exclu(c["site"]):
            vues.add(d)
            uniques.append(c)
    print(f"    → {len(uniques)} agence(s) distincte(s) à sonder\n")

    if not uniques:
        print("Aucune agence trouvée (Overpass indisponible ?). "
              "On s'arrête sans rien changer.")
        return

    print(f"2/2 — Sondage des sites (en parallèle, {args.parallele} à la fois)")
    sondes = []
    with ThreadPoolExecutor(max_workers=args.parallele) as pool:
        for futur in as_completed([pool.submit(_sonder, a) for a in uniques]):
            try:
                sondes.append(futur.result())
            except Exception:
                pass

    # Overpass ne répond pas pour les mêmes zones d'une fois sur l'autre : on
    # cumule avec les sondages précédents plutôt que de les écraser, sinon la
    # couverture fait du sur-place au lieu de s'enrichir.
    ancien = []
    if RAPPORT.exists():
        try:
            ancien = json.loads(RAPPORT.read_text(encoding="utf-8"))
        except ValueError:
            pass
    sondes = fusionner_rapports(ancien, sondes)
    print(f"    → {len(sondes)} sondages au total en cumulant les passes précédentes")
    retenues = [s for s in sondes if s.get("note", 0) >= args.note]
    print(f"\n{'note':>5}  {'biens':>5}  agence")
    for s in sondes[:40]:
        marque = "✔" if s.get("note", 0) >= args.note else "·"
        detail = "" if s["nb_biens"] else f"  ({s.get('motif', '')})"
        print(f"{marque}{s.get('note', 0):>4}  {s['nb_biens']:>5}  "
              f"{s['nom'][:34]:34} {domaine(s['site'])}{detail}")

    RAPPORT.parent.mkdir(exist_ok=True)
    RAPPORT.write_text(json.dumps(sondes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nRapport complet : {RAPPORT.relative_to(RACINE)} ({len(sondes)} sondages)")

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    toutes, ajoutees = fusionner(config.get("agences", []), retenues, args.note)
    if args.simuler:
        print(f"[simulation] {len(ajoutees)} agence(s) seraient ajoutées.")
        return
    if not ajoutees:
        print("Aucune nouvelle agence exploitable à ajouter.")
        return
    config["agences"] = toutes
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"{len(ajoutees)} agence(s) ajoutée(s) à {CONFIG.name} :")
    for a in ajoutees:
        print(f"   + {a['nom']} — {a['site']}  [{a['zone']}]")


if __name__ == "__main__":
    main()
