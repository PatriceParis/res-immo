"""Collecte les annonces des réseaux de mandataires (IAD, Capifrance).

Pourquoi ce second collecteur
-----------------------------
Le collecteur par navigateur visite des agences : un site, quelques dizaines
de biens. Les réseaux de mandataires sont d'une autre échelle — 94 216
annonces publiées au sitemap chez IAD, dont 44 318 dans nos terroirs. Les
lire de la même façon serait à la fois trop lent et inutilement lourd pour
leurs serveurs.

Trois différences, toutes destinées à ne télécharger que le nécessaire :

- **On trie avant de visiter.** L'adresse porte le type de bien et la commune :
  les appartements et les départements hors cible sont écartés sans qu'aucune
  page ne soit ouverte.
- **Pas de navigateur.** Ces pages livrent leurs données structurées en HTML
  simple — vérifié par la sonde : prix, surface, terrain, pièces et six photos
  sortent d'une requête ordinaire. Chromium n'apporterait rien pour dix fois
  le coût.
- **Un tour par département**, du plus anciennement vu au plus récent, avec un
  budget de temps. Le découpage par département n'est pas cosmétique : voir
  app/mandataires.py.

Courtoisie
----------
On lit le sitemap que le réseau publie à l'intention des robots, on n'ouvre
que des pages qu'il n'interdit pas (robots.txt d'IAD interdit /liste/annonces*,
les pages de recherche : on n'y touche pas), et on espace les requêtes.

Usage :
    python scripts/collecter_mandataires.py                      # tous les réseaux
    python scripts/collecter_mandataires.py --reseau iad --minutes 25
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db, mandataires  # noqa: E402
from app.chargement import preparer_annonce  # noqa: E402
from app.enrichissement import _altitude, _densite, _geocoder, _geocoder_cp  # noqa: E402
from app.extraction import extraire_annonce  # noqa: E402
from app.qualite import est_bien_valide, est_vendu  # noqa: E402
from app.regions import REGION_PAR_DEPT, regions_cibles  # noqa: E402

JOURNAL = RACINE / "data" / "mandataires_visites.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
RE_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
SECONDES = 20
PLAFOND = 20_000_000
# Profondeur de descente dans les sitemaps imbriqués (index → ads → pages).
PROFONDEUR = 3


def lire(url: str) -> bytes:
    requete = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    try:
        with urllib.request.urlopen(requete, timeout=SECONDES) as reponse:
            donnees = reponse.read(PLAFOND)
            if url.endswith(".gz") or donnees[:2] == b"\x1f\x8b":
                donnees = gzip.decompress(donnees)
            return donnees
    except Exception:
        return b""


def sitemaps_declares(site: str) -> list[str]:
    """Ceux que le réseau annonce lui-même dans robots.txt."""
    donnees = lire(urljoin(site, "/robots.txt"))
    if not donnees:
        return []
    return re.findall(r"(?im)^\s*Sitemap:\s*(\S+)", donnees.decode("utf-8", "replace"))


def adresses_du_sitemap(sitemaps: list[str], motif) -> list[str]:
    a_lire, annonces, vus = list(sitemaps), [], set()
    for _ in range(PROFONDEUR):
        suivants = []
        for sitemap in a_lire:
            if sitemap in vus:
                continue
            vus.add(sitemap)
            donnees = lire(sitemap)
            if not donnees:
                continue
            liens = RE_LOC.findall(donnees.decode("utf-8", "replace"))
            suivants += [u for u in liens if u.endswith((".xml", ".xml.gz"))]
            annonces += [u for u in liens if motif.search(u)]
        a_lire = suivants
        if not a_lire:
            break
    return annonces


def communes_des_terroirs() -> dict:
    """Communes des départements ciblés, via l'API officielle."""
    cibles = sorted({d for d, r in REGION_PAR_DEPT.items()
                     if r in set(regions_cibles())})
    par_dept = {}
    for dept in cibles:
        donnees = lire(f"https://geo.api.gouv.fr/departements/{dept}/communes?fields=nom")
        if not donnees:
            continue
        try:
            par_dept[dept] = [c["nom"] for c in json.loads(donnees)]
        except ValueError:
            continue
    return par_dept


def derniere_visite() -> dict:
    try:
        return json.loads(JOURNAL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def noter_visite(cle: str, jour: str) -> None:
    journal = derniere_visite()
    journal[cle] = jour
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        JOURNAL.write_text(json.dumps(journal, ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass


def enregistrer_une(conn, annonce: dict, reseau: dict) -> str:
    """Renvoie « garde », « vendu », « ecarte » ou « illisible »."""
    donnees = lire(annonce["url"])
    if not donnees:
        return "illisible"
    brut = extraire_annonce(donnees.decode("utf-8", "replace"), annonce["url"],
                            source=mandataires.normaliser(annonce["agence"]),
                            agence=annonce["agence"], agence_url=reseau["site"])
    if not brut:
        return "illisible"
    if est_vendu(brut):
        return "vendu"
    # La commune vient de l'ADRESSE, pas de la page : ces réseaux publient le
    # code postal mais rarement la commune, et jamais les coordonnées.
    brut.setdefault("commune", annonce["commune"])
    brut["commune"] = brut.get("commune") or annonce["commune"]
    brut["departement"] = brut.get("departement") or annonce["departement"]
    if not est_bien_valide(brut):
        return "ecarte"

    brut["id"] = "%s-%s" % (mandataires.normaliser(annonce["agence"]),
                            hashlib.sha1(annonce["url"].encode()).hexdigest()[:12])
    if brut.get("lat") is None:
        geo = (_geocoder(brut.get("commune"), brut.get("code_postal"))
               or _geocoder_cp(brut.get("code_postal")))
        if geo:
            brut["lat"], brut["lon"], ville, cp, citycode = geo
            if ville and not brut.get("commune"):
                brut["commune"] = ville
            if cp:
                brut["code_postal"] = brut.get("code_postal") or cp
            if brut.get("densite_hab_km2") is None:
                brut["densite_hab_km2"] = _densite(citycode)
    if brut.get("altitude") is None and brut.get("lat") is not None:
        brut["altitude"] = _altitude(brut["lat"], brut["lon"])
    db.upsert_annonce(conn, preparer_annonce(brut))
    return "garde"


def collecter_un_reseau(conn, cle: str, reseau: dict, index: list,
                        fin_prevue: float, args) -> int:
    print(f"\n=== {reseau['nom']}")
    sitemaps = sitemaps_declares(reseau["site"])
    if not sitemaps:
        print("  robots.txt ne déclare aucun sitemap : on s'abstient.")
        return 0
    adresses = adresses_du_sitemap(sitemaps, reseau["motif_annonce"])
    print(f"  {len(adresses)} annonce(s) au sitemap")
    a_visiter = mandataires.annonces_a_visiter(adresses, reseau, index)
    groupes = mandataires.par_departement(a_visiter)
    print(f"  {len(a_visiter)} dans nos terroirs, sur {len(groupes)} département(s)")

    vu = derniere_visite()
    total = 0
    for dept in mandataires.ordre_des_departements(groupes, vu):
        if time.monotonic() > fin_prevue:
            print("  budget de temps atteint — la suite au prochain passage.")
            break
        lot = groupes[dept][:args.max_par_departement]
        gardes = compteurs = 0
        etats = {"garde": 0, "vendu": 0, "ecarte": 0, "illisible": 0}
        for annonce in lot:
            if time.monotonic() > fin_prevue:
                break
            etats[enregistrer_une(conn, annonce, reseau)] += 1
            compteurs += 1
            time.sleep(args.delai)
        gardes = etats["garde"]
        conn.commit()
        noter_visite(f"{cle}:{dept}", date.today().isoformat())
        print(f"  {dept} · {gardes:3} gardé(s) sur {compteurs} visité(s)"
              f" — {etats['vendu']} vendu(s), {etats['ecarte']} hors cible,"
              f" {etats['illisible']} illisible(s)")
        total += gardes
    return total


def main() -> None:
    parametres = argparse.ArgumentParser()
    parametres.add_argument("--reseau", choices=sorted(mandataires.RESEAUX),
                            help="n'en collecter qu'un")
    parametres.add_argument("--minutes", type=float, default=30,
                            help="budget de temps total")
    parametres.add_argument("--max-par-departement", type=int, default=25,
                            help="annonces visitées par département et par passage")
    parametres.add_argument("--delai", type=float, default=1.5,
                            help="secondes entre deux pages")
    args = parametres.parse_args()

    print("Communes des terroirs ciblés…")
    communes = communes_des_terroirs()
    if not communes:
        print("Liste des communes indisponible : sans elle on ne sait pas ce qui")
        print("relève de nos terroirs. On s'arrête plutôt que de tout collecter.")
        raise SystemExit(1)
    index = mandataires.index_des_communes(communes)
    print(f"  {len(index)} communes sur {len(communes)} département(s)")

    fin_prevue = time.monotonic() + args.minutes * 60
    conn = db.connexion()
    total = 0
    choisis = [args.reseau] if args.reseau else sorted(mandataires.RESEAUX)
    for cle in choisis:
        total += collecter_un_reseau(conn, cle, mandataires.RESEAUX[cle], index,
                                     fin_prevue, args)
    conn.close()
    print(f"\nTerminé : {total} bien(s) ajouté(s) depuis les réseaux de mandataires.")


if __name__ == "__main__":
    main()
