"""Un robot qui dit son nom est-il refusé là où un faux Chrome passe ?

Les onze robots du projet se présentent comme un navigateur (voir
docs/LEGAL.md). La posture loyale est de s'annoncer — « RefugeImmoBot/1.0 »
avec un lien vers la page qui explique le robot — mais beaucoup de sites
d'agences tournent sous WordPress avec un pare-feu qui refuse les clients
inconnus. Changer d'identité à l'aveugle, c'est risquer de vider le catalogue
en deux jours sans un message d'erreur : la règle de sortie retire ce qui
n'est plus revu.

Ce script MESURE, il ne change rien : chaque site de la configuration est
sondé deux fois, une par identité, et le rapport dit combien seraient perdus.
Il ne peut pas tourner depuis l'environnement de développement, dont le
proxy refuse les sites d'agences ; il tourne dans GitHub Actions
(.github/workflows/sonder-ua.yml), là où les robots vivent déjà.

Usage :  python scripts/sonder_user_agent.py [--max N] [--parallele 4]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

CONFIG = RACINE / "scraper" / "refuge_scraper" / "agences_sites.json"
RESEAUX = ["https://www.iadfrance.fr/", "https://www.safti.fr/", "https://www.century21.fr/"]

NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
ROBOT = "RefugeImmoBot/1.0 (+https://res-immo.vercel.app/robot)"
# La forme des moteurs de recherche : un navigateur « compatible » qui dit son
# nom. Certains pare-feux la traitent comme un navigateur, d'autres comme un
# robot — c'est précisément ce qu'on mesure.
COMPATIBLE = "Mozilla/5.0 (compatible; RefugeImmoBot/1.0; +https://res-immo.vercel.app/robot)"

IDENTITES = {"navigateur": NAVIGATEUR, "robot": ROBOT, "compatible": COMPATIBLE}


def sonder(url: str, identite: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": identite,
                                       "Accept-Language": "fr-FR,fr;q=0.9"},
                         timeout=20, allow_redirects=True)
        return str(r.status_code)
    except requests.RequestException as e:
        return type(e).__name__[:14]


def accepte(statut: str) -> bool:
    return statut.isdigit() and int(statut) < 400


def sonder_site(url: str, delai: float) -> dict:
    resultat = {"url": url}
    for nom, identite in IDENTITES.items():
        resultat[nom] = sonder(url, identite)
        time.sleep(delai)
    return resultat


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max", type=int, default=0, help="nombre de sites (0 = tous)")
    ap.add_argument("--parallele", type=int, default=4)
    ap.add_argument("--delai", type=float, default=0.5,
                    help="secondes entre deux requêtes vers le même site")
    args = ap.parse_args()

    agences = json.loads(CONFIG.read_text(encoding="utf-8"))["agences"]
    sites = sorted({a.get("site") or a.get("url") for a in agences
                    if a.get("site") or a.get("url")})
    if args.max:
        random.seed(1)
        sites = random.sample(sites, min(args.max, len(sites)))
    sites += RESEAUX
    print(f"{len(sites)} sites, {len(IDENTITES)} identités, {args.parallele} en parallèle\n")

    resultats = []
    with ThreadPoolExecutor(max_workers=args.parallele) as pool:
        for futur in as_completed([pool.submit(sonder_site, s, args.delai) for s in sites]):
            r = futur.result()
            resultats.append(r)
            print(f"{r['navigateur']:>14} {r['robot']:>14} {r['compatible']:>14}  {r['url'][:60]}",
                  flush=True)

    print(f"\n{'identité':12} {'acceptés':>9}  {'perdus vs navigateur':>22}")
    base = {r["url"] for r in resultats if accepte(r["navigateur"])}
    for nom in IDENTITES:
        ok = {r["url"] for r in resultats if accepte(r[nom])}
        print(f"{nom:12} {len(ok):>9}  {len(base - ok):>22}")
    perdus = [r for r in resultats if accepte(r["navigateur"]) and not accepte(r["robot"])]
    if perdus:
        print("\nRefusent le robot déclaré mais acceptent le navigateur :")
        for r in sorted(perdus, key=lambda x: x["url"]):
            print(f"  {r['navigateur']:>4} → {r['robot']:>14} (compatible : {r['compatible']:>14})  {r['url']}")
    (RACINE / "data").mkdir(exist_ok=True)
    rapport = RACINE / "data" / "sonde_user_agent.json"
    rapport.write_text(json.dumps(sorted(resultats, key=lambda r: r["url"]),
                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nRapport : {rapport.relative_to(RACINE)} (non committé par le workflow)")


if __name__ == "__main__":
    main()
