"""Sonde : un réseau de mandataires est-il exploitable comme source d'annonces ?

Les réseaux de mandataires — IAD, Safti, Capifrance, Optimhome, Propriétés
Privées — ont été écartés de la collecte au motif qu'ils n'ont « pas de site
local à brancher, seulement un site national qui est un portail ». Ce
raisonnement mérite d'être vérifié : ces réseaux publient une PAGE PAR BIEN,
et ces biens sont leurs propres mandats, pas ceux d'autrui. Fonctionnellement,
c'est une agence — simplement très grande.

Avant de décider quoi que ce soit, on mesure quatre choses :

1. **Ce que le site autorise.** robots.txt d'abord, toujours. Un site qui
   interdit l'exploration de ses annonces n'est pas une piste, quelle que
   soit sa richesse.
2. **Ce qu'on sait en extraire.** On passe une vraie annonce dans notre
   extracteur et on regarde ce qui en sort : prix, surface, commune,
   coordonnées, photo. Sans cela, la source ne vaut rien pour le score.
3. **Comment atteindre les annonces d'un terroir.** Un sitemap ? une
   recherche par commune ? Sans porte d'entrée géographique, il faudrait
   parcourir la France entière pour trouver la Saône-et-Loire.
4. **Le volume réellement atteignable** sur nos départements cibles.

Usage :  python scripts/explorer_mandataire.py URL_D_UNE_ANNONCE [--site https://…]
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.extraction import extraire_annonce  # noqa: E402
from app.regions import REGION_PAR_DEPT, regions_cibles  # noqa: E402

_NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SECONDES = 20
PLAFOND = 20_000_000


def lire(url: str) -> tuple[int, bytes]:
    requete = urllib.request.Request(url, headers={
        "User-Agent": _NAVIGATEUR,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    try:
        with urllib.request.urlopen(requete, timeout=SECONDES) as reponse:
            donnees = reponse.read(PLAFOND)
            if url.endswith(".gz") or donnees[:2] == b"\x1f\x8b":
                donnees = gzip.decompress(donnees)
            return reponse.status, donnees
    except urllib.error.HTTPError as erreur:
        return erreur.code, b""
    except Exception as erreur:
        print(f"    !! {type(erreur).__name__} : {erreur}")
        return 0, b""


def ce_que_le_site_autorise(base: str) -> list[str]:
    """robots.txt — la première question, avant toute autre."""
    code, donnees = lire(urljoin(base, "/robots.txt"))
    print(f"\n1. CE QUE LE SITE AUTORISE  (robots.txt → HTTP {code})")
    if code != 200 or not donnees:
        print("   robots.txt illisible : on ne peut rien conclure, donc on s'abstient.")
        return []
    texte = donnees.decode("utf-8", "replace")
    sitemaps = re.findall(r"(?im)^\s*Sitemap:\s*(\S+)", texte)

    # On ne lit que le bloc qui NOUS concerne : User-agent: *
    bloc, dans_le_bloc = [], False
    for ligne in texte.splitlines():
        if re.match(r"(?i)^\s*User-agent:", ligne):
            dans_le_bloc = re.match(r"(?i)^\s*User-agent:\s*\*\s*$", ligne) is not None
            continue
        if dans_le_bloc and ligne.strip():
            bloc.append(ligne.strip())
    interdits = [l.split(":", 1)[1].strip() for l in bloc
                 if l.lower().startswith("disallow:") and l.split(":", 1)[1].strip()]
    autorises = [l.split(":", 1)[1].strip() for l in bloc
                 if l.lower().startswith("allow:")]
    print(f"   Disallow (User-agent: *) : {interdits[:14] or 'aucun'}")
    if len(interdits) > 14:
        print(f"     … et {len(interdits) - 14} autre(s)")
    if autorises:
        print(f"   Allow : {autorises[:8]}")
    print(f"   Sitemaps déclarés : {len(sitemaps)}")
    for s in sitemaps[:6]:
        print(f"     - {s}")
    return sitemaps


def ce_qu_on_sait_extraire(url: str) -> None:
    print("\n2. CE QU'ON SAIT EXTRAIRE  (une vraie annonce dans notre extracteur)")
    code, donnees = lire(url)
    print(f"   HTTP {code}, {len(donnees)} octets")
    if code != 200 or not donnees:
        print("   Page inaccessible : rien à conclure sur l'extraction.")
        return
    annonce = extraire_annonce(donnees.decode("utf-8", "replace"), url, source="sonde")
    if not annonce:
        print("   L'extracteur ne reconnaît PAS une annonce (ni prix ni surface).")
        return
    for cle in ("titre", "prix", "surface_m2", "terrain_m2", "pieces", "type_bien",
                "commune", "code_postal", "lat", "lon", "dpe"):
        print(f"   {cle:12} : {annonce.get(cle)}")
    photos = annonce.get("photos") or []
    print(f"   photos       : {len(photos)} candidate(s)")
    for p in photos[:3]:
        print(f"                  {p[:96]}")


def comment_atteindre_un_terroir(base: str, sitemaps: list[str]) -> None:
    print("\n3. COMMENT ATTEINDRE LES ANNONCES D'UN TERROIR")
    if not sitemaps:
        print("   Aucun sitemap déclaré : il faudrait deviner les URL de recherche,")
        print("   ce qui est fragile. Piste à écarter sauf porte d'entrée évidente.")
        return

    cibles = {d for d, r in REGION_PAR_DEPT.items() if r in set(regions_cibles())}
    for sitemap in sitemaps[:4]:
        code, donnees = lire(sitemap)
        if code != 200 or not donnees:
            print(f"   {sitemap} → HTTP {code}, illisible")
            continue
        texte = donnees.decode("utf-8", "replace")
        liens = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", texte)
        sous = [u for u in liens if ".xml" in u]
        annonces = [u for u in liens if "/annonce" in u or "/bien" in u]
        print(f"   {sitemap}")
        print(f"     {len(liens)} lien(s) — {len(sous)} sous-sitemap(s), "
              f"{len(annonces)} annonce(s) directe(s)")
        if annonces:
            _resumer_par_commune(annonces, cibles)
        for s in sous[:3]:
            print(f"     ↳ {s}")


def _resumer_par_commune(urls: list[str], departements_cibles: set) -> None:
    """Les URL d'annonces portent souvent le nom de la commune : on s'en sert
    pour estimer ce qui tomberait dans nos terroirs."""
    print(f"     exemples : {urls[0][:100]}")
    codes = re.compile(r"\b(\d{5})\b")
    par_dept: dict = {}
    for u in urls:
        trouve = codes.search(u)
        if trouve:
            dept = trouve.group(1)[:2]
            par_dept[dept] = par_dept.get(dept, 0) + 1
    if par_dept:
        dans_cible = sum(n for d, n in par_dept.items() if d in departements_cibles)
        print(f"     {dans_cible} annonce(s) dans les départements ciblés "
              f"sur {sum(par_dept.values())} localisables")


def main() -> None:
    parametres = argparse.ArgumentParser()
    parametres.add_argument("annonce", help="URL d'une annonce du réseau")
    parametres.add_argument("--site", help="racine du site (déduite sinon)")
    args = parametres.parse_args()

    morceaux = urlparse(args.annonce)
    base = args.site or f"{morceaux.scheme}://{morceaux.netloc}"
    print("=" * 78)
    print(f"SONDE MANDATAIRE — {base}")
    print("=" * 78)

    sitemaps = ce_que_le_site_autorise(base)
    ce_qu_on_sait_extraire(args.annonce)
    comment_atteindre_un_terroir(base, sitemaps)
    print("\nFin de sonde.")


if __name__ == "__main__":
    main()
