"""Découverte d'agences : « quelles agences ont des biens intéressants ? »

Étape 1 de la stratégie « collecte via les agences » (voir
docs/STRATEGIE_COLLECTE.md). Ce script interroge l'API JSON de Bien'ici pour
une zone donnée, relève le nom (et si possible le site) des agences qui
publient des maisons correspondant au profil « refuge », puis les ajoute à
l'annuaire scraper/refuge_scraper/agences.json.

On pourra ensuite lancer la collecte directe sur ces agences :
    bash scripts/collecter.sh agence

Nécessite internet. Usage personnel — voir docs/LEGAL.md.

Exemple :
    python scripts/decouvrir_agences.py --lieux "orne, yonne, nievre" --prix-max 300000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

try:
    import requests
except ImportError:  # pragma: no cover
    print("Le module 'requests' est nécessaire : pip install -r requirements-local.txt")
    sys.exit(1)

ANNUAIRE = RACINE / "scraper" / "refuge_scraper" / "agences.json"
URL_SUGGEST = "https://res.bienici.com/suggest.json?q={q}"
URL_ANNONCES = "https://www.bienici.com/realEstateAds.json?filters={filtres}"
ENTETES = {"User-Agent": "RefugeImmo-POC/0.1 (veille personnelle)"}


def _zones(lieu: str) -> list:
    try:
        r = requests.get(URL_SUGGEST.format(q=urllib.parse.quote(lieu)),
                         headers=ENTETES, timeout=10)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return []
    candidats = data if isinstance(data, list) else data.get("suggestions") or []
    for c in candidats[:1]:
        if isinstance(c, dict):
            return (c.get("zoneIds") or []) + ([c["zoneId"]] if c.get("zoneId") else [])
    return []


def _agence_de(ad: dict) -> dict | None:
    """Extrait nom + site d'agence d'une annonce Bien'ici (clés variables : défensif)."""
    if not isinstance(ad, dict):
        return None
    contact = {}
    for cle in ("userRelativeData", "contactRelativeData", "agency", "professional"):
        if isinstance(ad.get(cle), dict):
            contact = {**ad[cle], **contact}
    nom = (contact.get("agencyName") or contact.get("name")
           or ad.get("agencyName") or contact.get("companyName"))
    site = (contact.get("website") or contact.get("webSite") or contact.get("url"))
    if not nom:
        return None
    return {"nom": str(nom).strip(), "site": (site or "").strip()}


def decouvrir(lieux: list[str], prix_max: int | None, pages: int) -> list[dict]:
    trouvees: dict[str, dict] = {}
    for lieu in lieux:
        zones = _zones(lieu)
        if not zones:
            print(f"  · {lieu}: zone introuvable")
            continue
        for page in range(pages):
            filtres = {"size": 24, "from": page * 24, "filterType": "buy",
                       "propertyType": ["house"], "zoneIdsByTypes": {"zoneIds": zones}}
            if prix_max:
                filtres["maxPrice"] = prix_max
            url = URL_ANNONCES.format(filtres=urllib.parse.quote(json.dumps(filtres)))
            try:
                r = requests.get(url, headers=ENTETES, timeout=12)
                r.raise_for_status()
                annonces = r.json().get("realEstateAds") or []
            except (requests.RequestException, ValueError):
                break
            for ad in annonces:
                info = _agence_de(ad)
                if info:
                    trouvees.setdefault(info["nom"], info)
                    if info["site"] and not trouvees[info["nom"]]["site"]:
                        trouvees[info["nom"]]["site"] = info["site"]
            print(f"  · {lieu} p.{page + 1}: {len(annonces)} annonces, "
                  f"{len(trouvees)} agences cumulées")
            if not annonces:
                break
            time.sleep(1.5)  # politesse
    return list(trouvees.values())


def fusionner_annuaire(nouvelles: list[dict]) -> int:
    annuaire = json.loads(ANNUAIRE.read_text(encoding="utf-8"))
    connues = {a["nom"].lower() for a in annuaire["agences"]}
    ajout = 0
    for info in nouvelles:
        if info["nom"].lower() in connues or not info.get("site"):
            continue
        annuaire["agences"].append({
            "nom": info["nom"], "site": info["site"].rstrip("/"),
            "reseau": "découvert (Bien'ici)", "categorie": "à qualifier",
            "zone": "", "specialite": "", "sitemap": None, "verifie": False,
        })
        connues.add(info["nom"].lower())
        ajout += 1
    ANNUAIRE.write_text(json.dumps(annuaire, ensure_ascii=False, indent=2), encoding="utf-8")
    return ajout


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lieux", default="orne, yonne, nievre, eure-et-loir")
    p.add_argument("--prix-max", type=int, default=None)
    p.add_argument("--pages", type=int, default=3)
    args = p.parse_args()

    lieux = [x.strip() for x in args.lieux.split(",") if x.strip()]
    print(f"Découverte d'agences sur : {', '.join(lieux)}")
    nouvelles = decouvrir(lieux, args.prix_max, args.pages)
    print(f"\n{len(nouvelles)} agence(s) relevée(s).")
    with_site = [a for a in nouvelles if a.get("site")]
    ajout = fusionner_annuaire(nouvelles) if nouvelles else 0
    print(f"{len(with_site)} avec site web ; {ajout} ajoutée(s) à l'annuaire.")
    if nouvelles and not with_site:
        print("Astuce : Bien'ici n'a pas exposé les sites. Cherchez le nom de "
              "l'agence sur un moteur pour trouver son site, puis :\n"
              "  bash scripts/collecter.sh agence -a site=https://son-site.fr")


if __name__ == "__main__":
    main()
