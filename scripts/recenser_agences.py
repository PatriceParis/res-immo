"""Recensement des agences immobilières des terroirs ciblés — toutes sources.

But : constituer la liste la plus complète possible des agences par
département, pour que la collecte d'annonces ait de la matière et qu'on sache
enfin quelle part du marché on couvre réellement.

Trois pistes, complémentaires — aucune n'est suffisante seule :

  osm       OpenStreetMap, balayé par DÉPARTEMENT (et non plus autour de 19
            villes choisies à la main). Donne un site web pour une minorité
            des points ; les autres sont conservés comme pistes à résoudre.

  reseaux   Annuaires des réseaux de franchise (Laforêt, Century 21, Orpi,
            Guy Hoquet, Nestenn, ERA…). Chaque réseau publie la liste de ses
            agences avec une page par agence — c'est exhaustif et tenu à jour
            par le réseau lui-même. Les réseaux de MANDATAIRES (IAD, Safti,
            Capifrance…) sont écartés : ils n'ont pas d'agence à brancher,
            leurs mandats vivent sur un site national unique.

  sirene    Registre officiel des entreprises, code d'activité 68.31Z. Seule
            source exhaustive par construction. Elle ne donne pas les sites
            web : elle sert de RÉFÉRENCE pour mesurer la couverture, et à
            repérer nommément les agences qui manquent.

Le résultat est écrit dans data/ : `agences_recensees.json` (tout ce qu'on
sait, quelle que soit la source) et `couverture_agences.json` (la part
couverte par département). Le branchement effectif sur la collecte reste le
travail de scripts/decouvrir_agences_osm.py, qui sonde les sites.

Usage :
    python scripts/recenser_agences.py                     # les trois pistes
    python scripts/recenser_agences.py --sources osm,sirene
    python scripts/recenser_agences.py --departements 61,60
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import decouverte, reseaux, sirene  # noqa: E402
from app.chargement import DEPARTEMENTS_CIBLES  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]
GEO_API = "https://geo.api.gouv.fr"

SORTIE = RACINE / "data" / "agences_recensees.json"
SORTIE_COUVERTURE = RACINE / "data" / "couverture_agences.json"


# Certains sitemaps de réseaux nationaux pèsent des dizaines de méga-octets.
# Les lire en entier immobilisait le recensement : un premier essai est resté
# plus de trente minutes sur trois départements, sans rien écrire. On borne
# donc ce qu'on accepte de télécharger.
PLAFOND_TELECHARGEMENT = 12_000_000      # 12 Mo, largement de quoi pour un index


def _lire(url: str, essais: int = 3, timeout: int = 90) -> str | None:
    for essai in range(essais):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9",
                "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                brut = r.read(PLAFOND_TELECHARGEMENT)
            if len(brut) >= PLAFOND_TELECHARGEMENT:
                print(f"    … {url[:60]} tronqué à {PLAFOND_TELECHARGEMENT // 1_000_000} Mo")
            return brut.decode("utf-8", "ignore")
        except Exception as e:
            if essai == essais - 1:
                print(f"    ✗ {url[:70]} — {type(e).__name__}")
            time.sleep(2 * (essai + 1))
    return None


def _json(url: str, **kw) -> dict | None:
    brut = _lire(url, **kw)
    if not brut:
        return None
    try:
        return json.loads(brut)
    except ValueError:
        return None


# --- Piste 1 : OpenStreetMap, par département -------------------------------


# Overpass met parfois les requêtes en file d'attente sans rien dire. Un
# essai de 180 s par miroir, deux fois, sur deux miroirs, c'est douze minutes
# perdues pour UN département — c'est ce qui a immobilisé les deux premiers
# essais de recensement. Un seul essai par miroir, plus court.
def _overpass(requete: str) -> dict | None:
    for miroir in OVERPASS:
        url = miroir + "?data=" + urllib.parse.quote(requete)
        d = _json(url, essais=1, timeout=90)
        if d is not None:
            return d
        time.sleep(2)
    return None


# Budget de la piste OpenStreetMap. Sans lui, 36 départements à deux essais
# de 90 secondes dépassaient à eux seuls la durée du job.
SECONDES_OSM = 1200


def piste_osm(departements: list[str]) -> tuple[list[dict], list[dict]]:
    """Agences du département : celles qui ont un site, et celles sans."""
    avec, sans = [], []
    echeance = time.monotonic() + SECONDES_OSM
    # Overpass n'accepte que 2 requêtes simultanées par IP ; au-delà il refuse
    # et les départements reviennent vides sans le dire.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futurs = {pool.submit(_overpass, decouverte.requete_overpass_departement(d)): d
                  for d in departements}
        for futur in as_completed(futurs):
            dept = futurs[futur]
            if time.monotonic() > echeance:
                futur.cancel()
                continue
            rep = futur.result()
            if rep is None:
                print(f"  dept {dept} : Overpass n'a pas répondu")
                continue
            a = decouverte.agences_depuis_overpass(rep, f"dept {dept}")
            s = decouverte.agences_sans_site(rep, f"dept {dept}")
            for x in a + s:
                x["departement"] = dept
            avec += a
            sans += s
            print(f"  dept {dept} : {len(a)} avec site, {len(s)} sans site")
    return avec, sans


# --- Piste 2 : annuaires des réseaux de franchise ---------------------------


# Aucun réseau ne doit pouvoir manger le budget des autres.
SECONDES_PAR_RESEAU = 120


def _urls_du_sitemap(base: str, profondeur: int = 1) -> list[str]:
    """URLs listées par le sitemap d'un site (sous-sitemaps suivis une fois)."""
    import re
    RE_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
    echeance = time.monotonic() + SECONDES_PAR_RESEAU
    for chemin in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        brut = _lire(base.rstrip("/") + chemin, essais=1, timeout=30)
        if not brut or "<loc" not in brut.lower():
            continue
        locs = RE_LOC.findall(brut)
        detail = [u for u in locs if not u.lower().endswith(".xml")]
        sous = [u for u in locs if u.lower().endswith(".xml")]
        if profondeur:
            # Les annuaires d'agences sont souvent dans un sous-sitemap dédié :
            # on les suit d'abord, et on ne descend dans les autres que s'il
            # reste du temps.
            interessants = [u for u in sous if reseaux.MOTIF_PAGE_AGENCE.search(u)]
            for su in (interessants or sous)[:12]:
                if time.monotonic() > echeance:
                    print(f"    … {base} : temps imparti atteint, on garde l'acquis")
                    break
                s = _lire(su, essais=1, timeout=30)
                if s:
                    detail += RE_LOC.findall(s)
        return list(dict.fromkeys(detail))
    return []


def _communes_par_departement(departements: list[str]) -> dict:
    par_dept = {}
    for dept in departements:
        d = _json(f"{GEO_API}/departements/{dept}/communes?fields=nom", essais=2,
                  timeout=45)
        par_dept[dept] = [c.get("nom") for c in (d or []) if c.get("nom")]
        print(f"  dept {dept} : {len(par_dept[dept])} communes")
    return par_dept


def piste_reseaux(departements: list[str]) -> list[dict]:
    # Toutes les communes de France, pour écarter les noms ambigus : sans
    # cela, /agence-immobiliere/bretigny (Essonne) était rattaché à Brétigny
    # dans l'Oise, et /immobilier-montlucon-centre-ville-les-forges/ devenait
    # « Orpi Ville ». Trois résultats, trois faux.
    communes_fr = _json(f"{GEO_API}/communes?fields=nom", essais=2, timeout=90) or []
    nationales = reseaux.occurrences_nationales(communes_fr)
    extensions = reseaux.extensions_nationales(communes_fr)
    print(f"  {len(nationales)} noms de communes en France pour lever les ambiguïtés"
          if nationales else
          "  ⚠ liste nationale indisponible : le rapprochement sera plus prudent")
    index = reseaux.index_des_communes(
        _communes_par_departement(departements), nationales)
    print(f"  {len(index)} noms utilisables comme repère sur nos terroirs\n")
    trouvees = []
    for reseau in reseaux.RESEAUX:
        if reseau.get("mandataires"):
            print(f"  {reseau['nom']} : réseau de mandataires, pas d'agence à brancher")
            continue
        urls = _urls_du_sitemap(reseau["site"])
        agences = reseaux.agences_du_reseau(reseau, urls, index, extensions)
        trouvees += agences
        print(f"  {reseau['nom']} : {len(urls)} URLs au sitemap → "
              f"{len(agences)} agence(s) sur nos terroirs")
    return trouvees


# --- Piste 3 : registre officiel des entreprises ----------------------------


# Budget de la piste registre : au-delà, on garde ce qu'on a. Mieux vaut un
# recensement partiel et livré qu'un recensement complet et perdu.
SECONDES_REGISTRE = 900


def piste_sirene(departements: list[str]) -> list[dict]:
    recensees = []
    echeance = time.monotonic() + SECONDES_REGISTRE
    for dept in departements:
        if time.monotonic() > echeance:
            print(f"  temps imparti atteint : départements suivants non traités")
            break
        page, pages, total = 1, 1, 0
        while page <= pages and page <= 40 and time.monotonic() < echeance:
            url = sirene.API + "?" + urllib.parse.urlencode(
                sirene.parametres(dept, page=page))
            rep = _json(url, essais=2, timeout=30)
            if rep is None:
                break
            pages = sirene.nombre_de_pages(rep)
            lot = sirene.agences_depuis_reponse(rep, dept)
            recensees += lot
            total += len(lot)
            page += 1
            time.sleep(0.4)          # l'API publique est aimable, restons-le
        print(f"  dept {dept} : {total} agence(s) au registre")
    return recensees


# --- Programme --------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sources", default="osm,reseaux,sirene",
                   help="pistes à lancer (osm, reseaux, sirene), séparées par des virgules")
    p.add_argument("--departements", default="",
                   help="codes séparés par des virgules (défaut : tous les terroirs ciblés)")
    args = p.parse_args()

    depts = ([d.strip() for d in args.departements.split(",") if d.strip()]
             or sorted(DEPARTEMENTS_CIBLES))
    sources = {s.strip() for s in args.sources.split(",") if s.strip()}
    print(f"Recensement sur {len(depts)} département(s) : {', '.join(depts)}\n")

    recensees: list[dict] = []
    sans_site: list[dict] = []
    registre: list[dict] = []

    # Chaque piste écrit dès qu'elle a fini. Sans cela, une piste qui traîne
    # (les sitemaps des grands réseaux pèsent lourd) faisait perdre AUSSI le
    # travail des précédentes quand le job atteignait sa limite de temps.
    def enregistrer() -> None:
        # On COMPLÈTE le fichier existant au lieu de le remplacer : le
        # recensement se fait par tranches de départements (36 en un seul run
        # dépasserait le temps imparti), et une tranche qui écrase la
        # précédente ne construirait jamais l'annuaire complet.
        try:
            deja = json.loads(SORTIE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            deja = []
        uniques, vues = [], set()
        for a in deja + recensees + sans_site + registre:
            cle = (decouverte.domaine(a.get("site"))
                   or (a.get("nom", "").lower(), (a.get("commune") or "").lower()))
            if cle in vues:
                continue
            vues.add(cle)
            uniques.append(a)
        SORTIE.parent.mkdir(parents=True, exist_ok=True)
        SORTIE.write_text(json.dumps(uniques, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        return uniques

    if "osm" in sources:
        print("── OpenStreetMap, par département ──")
        avec, sans = piste_osm(depts)
        for a in avec:
            a["source"] = "openstreetmap"
        for a in sans:
            a["source"] = "openstreetmap (sans site)"
        recensees += avec
        sans_site += sans
        enregistrer()
        print(f"→ {len(avec)} avec site, {len(sans)} sans site (enregistré)\n")

    if "reseaux" in sources:
        print("── Annuaires des réseaux de franchise ──")
        r = piste_reseaux(depts)
        for a in r:
            a["source"] = "réseau"
        recensees += r
        enregistrer()
        print(f"→ {len(r)} agence(s) de réseau (enregistré)\n")

    if "sirene" in sources:
        print("── Registre officiel des entreprises (NAF 68.31Z) ──")
        registre = piste_sirene(depts)
        for a in registre:
            a["source"] = "registre"
        enregistrer()
        print(f"→ {len(registre)} agence(s) recensée(s) (enregistré)\n")

    uniques = enregistrer()
    avec_site = [a for a in uniques if a.get("site")]
    print(f"Total : {len(uniques)} agence(s) recensée(s), "
          f"dont {len(avec_site)} avec un site exploitable.")
    print(f"Écrit dans {SORTIE.relative_to(RACINE)}")

    if registre:
        couv = sirene.couverture(registre, avec_site)
        # Les listes de manquantes sont volumineuses : on garde les comptes et
        # un échantillon nommé, de quoi savoir quoi chercher ensuite.
        resume = {d: {"recensees": v["recensees"], "reconnues": v["reconnues"],
                      "part": round(100 * v["reconnues"] / v["recensees"])
                      if v["recensees"] else 0,
                      "exemples_manquants": [m["nom"] for m in v["manquantes"][:15]]}
                  for d, v in sorted(couv.items())}
        SORTIE_COUVERTURE.write_text(
            json.dumps(resume, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        total_r = sum(v["recensees"] for v in couv.values())
        total_ok = sum(v["reconnues"] for v in couv.values())
        print(f"\nCouverture : {total_ok} agence(s) reconnue(s) sur {total_r} "
              f"recensée(s) au registre "
              f"({round(100 * total_ok / total_r) if total_r else 0} %).")
        print(f"Détail par département dans {SORTIE_COUVERTURE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
