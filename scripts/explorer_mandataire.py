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

# Ce qui ressemble à une page de bien, tous réseaux confondus. Taillé pour
# IAD au départ (« /annonce/ »), il manquait les autres : chaque réseau a son
# vocabulaire, et une sonde qui ne voit qu'un seul mot conclut trop vite qu'il
# n'y a rien à voir.
RE_ANNONCE = re.compile(
    r"/(annonces?|biens?|vente|a-vendre|propriete|maison|offre|ref)[-/]",
    re.IGNORECASE)


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
    print("\n5. CE QU'ON SAIT EXTRAIRE  (une vraie annonce dans notre extracteur)")
    if not url:
        print("   Aucune annonce à disséquer.")
        return
    print(f"   {url[:104]}")
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


def comment_atteindre_un_terroir(base: str, sitemaps: list[str]) -> list[str]:
    print("\n3. COMMENT ATTEINDRE LES ANNONCES D'UN TERROIR")
    if not sitemaps:
        print("   Aucun sitemap déclaré : il faudrait deviner les URL de recherche,")
        print("   ce qui est fragile. Piste à écarter sauf porte d'entrée évidente.")
        return []

    cibles = {d for d, r in REGION_PAR_DEPT.items() if r in set(regions_cibles())}
    annonces = _annonces_du_sitemap(sitemaps)
    if not annonces:
        print("   Aucune annonce trouvée dans les sitemaps.")
        return []
    print(f"\n4. VOLUME ATTEIGNABLE — {len(annonces)} annonce(s) publiées au sitemap")
    _resumer_par_commune(annonces, cibles)
    return annonces


def _annonces_du_sitemap(sitemaps: list[str], profondeur: int = 2) -> list[str]:
    """Descend dans les sous-sitemaps jusqu'à trouver les annonces."""
    a_lire, annonces, vus = list(sitemaps), [], set()
    for _ in range(profondeur + 1):
        suivants = []
        for sitemap in a_lire[:12]:
            if sitemap in vus:
                continue
            vus.add(sitemap)
            code, donnees = lire(sitemap)
            if code != 200 or not donnees:
                print(f"   {sitemap} → HTTP {code}")
                continue
            liens = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>",
                               donnees.decode("utf-8", "replace"))
            sous = [u for u in liens if u.endswith((".xml", ".xml.gz"))]
            ici = [u for u in liens if RE_ANNONCE.search(u)]
            print(f"   {sitemap.split('/')[-1]:24} {len(liens):6} lien(s) — "
                  f"{len(sous)} sous-sitemap(s), {len(ici)} annonce(s)")
            annonces += ici
            suivants += sous
        a_lire = suivants
        if not a_lire:
            break
    return annonces


def _slug(texte: str) -> str:
    import unicodedata
    sans = unicodedata.normalize("NFD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sans.lower()).strip("-")


def _communes_des_departements(departements: set) -> dict:
    """Nom normalisé → département, pour les terroirs ciblés."""
    import json
    communes = {}
    for dept in sorted(departements):
        code, donnees = lire(
            f"https://geo.api.gouv.fr/departements/{dept}/communes?fields=nom")
        if code != 200 or not donnees:
            continue
        try:
            for c in json.loads(donnees):
                communes[_slug(c["nom"])] = dept
        except ValueError:
            continue
    return communes


def _resumer_par_commune(urls: list[str], departements_cibles: set) -> None:
    """Les URL d'annonces portent le nom de la commune : on s'en sert pour
    estimer ce qui tomberait dans nos terroirs, département par département."""
    print(f"   exemple : {urls[0][:104]}")
    print(f"   Rapprochement avec les communes des {len(departements_cibles)} "
          f"départements ciblés…")
    communes = _communes_des_departements(departements_cibles)
    if not communes:
        print("   Liste des communes indisponible : rapprochement impossible.")
        return
    # Les noms longs d'abord : « saint-berain-sur-dheune » avant « berain ».
    par_longueur = sorted(communes, key=len, reverse=True)
    par_dept: dict = {}
    touchees = 0
    for url in urls:
        chemin = _slug(urlparse(url).path)
        for nom in par_longueur:
            if len(nom) >= 5 and nom in chemin:
                dept = communes[nom]
                par_dept[dept] = par_dept.get(dept, 0) + 1
                touchees += 1
                break
    print(f"   {touchees} annonce(s) rattachées à une commune de nos terroirs "
          f"({touchees * 100 // max(len(urls), 1)} % du total national)")
    for dept, n in sorted(par_dept.items(), key=lambda t: -t[1]):
        print(f"     {dept} {REGION_PAR_DEPT.get(dept, ''):24} {n:5}")
    manquants = sorted(departements_cibles - set(par_dept))
    if manquants:
        print(f"   Aucune annonce trouvée dans : {', '.join(manquants)}")


def main() -> None:
    parametres = argparse.ArgumentParser()
    parametres.add_argument("cibles", nargs="+",
                            help="domaines ou URL d'annonces, un par réseau")
    args = parametres.parse_args()

    for cible in args.cibles:
        morceaux = urlparse(cible)
        base = f"{morceaux.scheme}://{morceaux.netloc}"
        annonce = cible if morceaux.path.strip("/") else ""
        print("\n" + "=" * 78)
        print(f"SONDE MANDATAIRE — {base}")
        print("=" * 78)

        sitemaps = ce_que_le_site_autorise(base)
        # On évalue d'abord la porte d'entrée : sans elle il n'y a pas de
        # piste, et elle fournit au passage une annonce à disséquer. Évaluer
        # un réseau ne demande donc plus d'en connaître une d'avance.
        annonces = comment_atteindre_un_terroir(base, sitemaps)
        ce_qu_on_sait_extraire(annonce or (annonces[0] if annonces else ""))
    print("\nFin de sonde.")


if __name__ == "__main__":
    main()
