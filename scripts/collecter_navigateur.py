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
import signal
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db  # noqa: E402
from app.chargement import preparer_annonce  # noqa: E402
from app.extraction import extraire_annonce  # noqa: E402
from app.enrichissement import (  # noqa: E402
    _altitude, _densite, _geocoder, _geocoder_cp, _geocoder_texte)
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


JOURNAL_VISITES = RACINE / "data" / "agences_visitees.json"


def _cle_agence(site: str) -> str:
    """Identifie une agence par son DOMAINE, jamais par son nom.

    « Century 21 » désigne cinq agences distinctes dans la configuration —
    Chalon, Compiègne, Amboise… Indexer la rotation sur le nom revenait à
    marquer les cinq comme visitées dès qu'on passait chez l'une : les quatre
    autres partaient en fin de file et n'étaient jamais atteintes. Le domaine,
    lui, est unique.
    """
    hote = urlparse(site or "").netloc.lower()
    return hote[4:] if hote.startswith("www.") else hote


def _derniere_visite() -> dict:
    """Date de dernier PASSAGE par domaine d'agence — qu'il ait rapporté ou non.

    Se fonder sur `revue_le` (présent seulement quand l'agence a livré des
    biens) affamerait la rotation : une agence dont le site est cassé ne
    recevrait jamais de date, resterait éternellement en tête et prendrait le
    budget des autres à chaque collecte. On enregistre donc le passage.

    L'export sert de repli pour les agences visitées avant l'existence de ce
    journal ; il porte l'URL de l'agence, donc la même clé.
    """
    vu: dict = {}
    try:
        for bien in json.loads(
                (RACINE / "data" / "annonces_reel.json").read_text(encoding="utf-8")):
            cle, date = _cle_agence(bien.get("agence_url")), bien.get("revue_le") or ""
            if cle and date > vu.get(cle, ""):
                vu[cle] = date
    except (OSError, ValueError):
        pass
    try:
        for cle, date in json.loads(
                JOURNAL_VISITES.read_text(encoding="utf-8")).items():
            if date > vu.get(cle, ""):
                vu[cle] = date
    except (OSError, ValueError):
        pass
    return vu


def _noter_visite(site: str, jour: str) -> None:
    """Consigne le passage chez une agence, même s'il n'a rien rapporté."""
    try:
        journal = json.loads(JOURNAL_VISITES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        journal = {}
    journal[_cle_agence(site)] = jour
    try:
        JOURNAL_VISITES.parent.mkdir(parents=True, exist_ok=True)
        JOURNAL_VISITES.write_text(
            json.dumps(journal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    except OSError:
        pass    # un journal indisponible ne doit pas arrêter la collecte


def _configurees() -> list[dict]:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("agences", [])
    except (OSError, ValueError):
        print(f"Config illisible : {CONFIG}")
        return []


def _cibles(site: str, nom: str, index: str) -> list[dict]:
    if site:
        # Une agence DÉJÀ configurée garde son identité, même désignée par son
        # URL. Sans cela, `-s https://immo-ray.com` la rebaptisait
        # « immo-ray.com » : ses biens repartaient sous un autre identifiant et
        # le catalogue se retrouvait avec 21 doublons — le même bien deux fois,
        # sous deux noms d'agence.
        connue = next((a for a in _configurees()
                       if _cle_agence(a.get("site")) == _cle_agence(site)), None)
        if connue and not nom:
            cible = dict(connue)
            if index:
                cible["index"] = [index]
            return [cible]
        return [{"nom": nom or urlparse(site).netloc, "site": site.rstrip("/"),
                 "index": [index] if index else []}]
    agences = _configurees()
    if not agences:
        return []

    # ROTATION. La collecte s'arrête au budget de temps : en parcourant
    # toujours la liste dans le même ordre, on revisitait sans cesse les mêmes
    # premières agences et JAMAIS les dernières. Constat réel : 51 agences
    # configurées, 4 réellement revues lors d'une collecte.
    #
    # Deux conséquences, toutes deux invisibles depuis le site : les biens des
    # agences de fin de liste étaient figés pour toujours — un bien vendu chez
    # elles n'expirait jamais, faute d'être jamais constaté absent — et une
    # amélioration de l'extraction ne les atteignait pas.
    #
    # On commence donc par celles qu'on a vues il y a le plus longtemps, les
    # jamais visitées en tête. Chaque agence revient à son tour.
    vu = _derniere_visite()
    agences.sort(key=lambda a: (vu.get(_cle_agence(a.get("site")), ""),
                                a.get("nom") or ""))
    return agences


def _sitemap_urls(base: str, fin_prevue: float = 0.0) -> list[str]:
    """URLs de pages de biens listées dans le sitemap.xml (via requests).

    `fin_prevue` borne la RECHERCHE elle-même. Sans cela, une agence pouvait
    y engloutir des minutes — trois chemins candidats, seize requêtes de
    quinze secondes chacune — pendant que le budget de la collecte filait.
    Quatre passages planifiés de suite ont ainsi dépassé la limite du job et
    ont été tués AVANT l'export : le travail était fait, puis jeté.
    """
    if requests is None:
        return []
    entetes = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"}
    for chemin in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        if fin_prevue and time.monotonic() > fin_prevue:
            return []
        try:
            r = requests.get(base + chemin, headers=entetes, timeout=10)
        except Exception:
            continue
        if r.status_code != 200 or "<loc" not in r.text.lower():
            continue
        locs = RE_LOC.findall(r.text)
        detail, sous = [], []
        for u in locs:
            (sous if u.lower().endswith(".xml") else detail).append(u)
        for su in sous[:8]:             # suivre les sous-sitemaps une fois
            if fin_prevue and time.monotonic() > fin_prevue:
                break
            try:
                detail += RE_LOC.findall(requests.get(su, headers=entetes, timeout=10).text)
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


class TempsEcoule(Exception):
    """L'agence n'a pas rendu la main dans le temps qui lui était imparti."""


def _sonner(signum, frame):
    raise TempsEcoule()


def borner(secondes: int):
    """Arme un réveil qui INTERROMPT l'agence en cours, quoi qu'elle fasse.

    Le garde-fou de dernier recours, et le seul qui ne demande la coopération
    de personne. Tous les autres la demandent : un `timeout=` de `requests`
    s'applique à chaque LECTURE et non au total — un serveur qui distille ses
    octets une seconde à la fois ne le déclenche jamais ; les délais posés sur
    la page Playwright ne couvrent que les appels au navigateur ; les
    vérifications de budget ne s'exécutent qu'entre deux tours de boucle.

    Trois correctifs successifs ont ainsi énuméré les appels à borner, et le
    passage suivant est reparti pour trente-quatre minutes sans mener une
    seule agence à son terme. On cesse d'énumérer : `SIGALRM` interrompt le
    processus jusque dans un appel système bloquant, donc y compris dans
    l'appel qu'on aura oublié.

    Renvoie une fonction à appeler pour désarmer.
    """
    if not hasattr(signal, "SIGALRM"):        # Windows : on s'en passe
        return lambda: None
    signal.signal(signal.SIGALRM, _sonner)
    signal.alarm(max(1, int(secondes)))
    return lambda: signal.alarm(0)


def _urls_a_visiter(page, cible: dict, base: str, maxi: int,
                    fin_prevue: float = 0.0) -> list[str]:
    # On récupère BEAUCOUP plus d'URL que de biens voulus : beaucoup de pages
    # sont écartées ensuite (biens vendus, appartements, pages catalogue). La
    # boucle d'appel s'arrête d'elle-même une fois `maxi` biens VALIDES gardés.
    vivier = max(maxi * 8, 80)
    urls = _sitemap_urls(base, fin_prevue)
    if urls:
        print(f"  sitemap : {len(urls)} page(s) de biens")
        return urls[:vivier]
    # repli : on parcourt les pages « nos biens »
    urls = []
    for idx in (cible.get("index") or [base]):
        # Seule boucle du collecteur qui n'avait pas d'échéance. Une agence
        # déclarant plusieurs pages d'index pouvait y passer tout le temps de
        # la collecte — trente secondes de navigation chacune — sans que le
        # budget par agence, vérifié seulement DANS la boucle des biens, ait
        # jamais son mot à dire.
        if fin_prevue and time.monotonic() > fin_prevue:
            print("  ⏱ temps épuisé pendant la recherche des pages de biens")
            break
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


JOURNAL_DEROULE = RACINE / "data" / "deroule_collecte.json"


def _consigner_deroule(deroule: list[dict], minutes: float) -> None:
    """Ce que chaque agence a coûté, et comment son tour s'est terminé.

    Écrit dans le dépôt et non seulement au journal du run : celui-ci n'est
    lisible que depuis l'onglet Actions, et la surveillance quotidienne n'a
    que git. Quatre passages de suite sont restés inexplicables faute de ce
    fichier ; le cinquième a été compris en une ligne.

    La distinction qui compte est dans « fin » : une agence « terminée » a
    rendu la main d'elle-même, une agence dont le « temps est épuisé » a
    consommé son budget, une agence « INTERROMPUE » ne répondait plus. Trois
    causes, trois remèdes opposés.
    """
    try:
        JOURNAL_DEROULE.parent.mkdir(parents=True, exist_ok=True)
        JOURNAL_DEROULE.write_text(json.dumps({
            "minutes": minutes,
            "agences": deroule,
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass          # un journal indisponible ne doit pas perdre la collecte


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
    # Budget de temps global. Il doit laisser la place aux étapes SUIVANTES
    # (enrichissement des risques, export, commit) : une collecte de 40 min
    # sur un job plafonné à 50 a déjà fait couper le job avant l'export.
    #   collecte 28 + risques 10 + export 1 = 39 min, sous les 50 du job.
    ap.add_argument("--minutes-max", type=float, default=28.0)
    # Budget PAR AGENCE. Le budget global dit quand s'arrêter, pas comment
    # répartir — et c'est la répartition qui manquait. Un passage de
    # trente-quatre minutes n'a visité que TROIS agences pour dix-huit biens :
    # le plafond de trente pages, à une vingtaine de secondes la page chez une
    # agence lente, suffit à consommer douze minutes à lui seul.
    #
    # Or toute la rotation repose sur l'inverse : beaucoup d'agences, peu de
    # biens chacune. À trois agences par passage, les deux cent trente-cinq de
    # l'annuaire demanderaient treize jours pour boucler le tour, et un bien
    # vendu resterait affiché deux semaines.
    ap.add_argument("--minutes-par-agence", type=float, default=4.0)
    args = ap.parse_args()

    conn = db.connexion()
    total = agences = 0
    deroule: list[dict] = []
    depart = time.monotonic()
    fin_prevue = depart + args.minutes_max * 60
    with sync_playwright() as p:
        navigateur = p.chromium.launch(
            executable_path=os.environ.get("REFUGE_CHROMIUM") or None, headless=True)
        contexte = navigateur.new_context(
            user_agent=UA, locale="fr-FR",
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
        page = contexte.new_page()
        # Plafond sur TOUT échange avec le navigateur, et pas seulement sur
        # les appels dont on a pensé à passer un `timeout=`. Un passage de
        # trente-quatre minutes s'est terminé sans qu'une seule agence soit
        # menée à son terme : le garde-fou du workflow a fini par le tuer, et
        # rien n'avait bougé. `page.content()` et `eval_on_selector_all()` ne
        # prennent pas de délai en paramètre — une page dont le script bloque
        # la boucle d'événements les fait attendre indéfiniment. Ces deux
        # réglages valent pour tous les appels, y compris ceux qu'on oublie.
        page.set_default_timeout(20_000)
        page.set_default_navigation_timeout(25_000)

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
            debut = time.monotonic()
            # L'agence n'a droit qu'à sa part, et jamais au-delà du budget
            # global. La recherche d'URL est comprise dedans : c'est parfois
            # elle qui traîne.
            fin_agence = min(fin_prevue, debut + args.minutes_par_agence * 60)
            print(f"\n▶ {cible['nom']} — {base}")
            n, vendus, ecartes, vues = 0, 0, 0, 0
            debordement = ""
            # Trente secondes de marge sur le budget : le temps de finir
            # proprement le bien en cours avant que le réveil ne sonne.
            desarmer = borner(args.minutes_par_agence * 60 + 30)
            try:
                urls = _urls_a_visiter(page, cible, base, maxi, fin_agence)
                for u in urls:
                    if n >= maxi:          # on s'arrête sur les biens GARDÉS,
                        break              # pas sur les pages visitées
                    if vues >= pages_max:
                        print(f"  … plafond de {pages_max} pages atteint pour cette agence")
                        break
                    if time.monotonic() > fin_agence:
                        debordement = (" — temps de l'agence épuisé"
                                       if time.monotonic() <= fin_prevue
                                       else " — budget global épuisé")
                        break
                    vues += 1
                    try:
                        page.goto(u, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(600)
                        # Un coup de molette avant de lire la page : beaucoup de
                        # diaporamas ne chargent leurs photos qu'au défilement, et
                        # sans cela on ne voyait que les icônes de l'en-tête. La
                        # sonde l'a montré sur immo-ray : 14 images avant, 50 après.
                        page.mouse.wheel(0, 2500)
                        page.wait_for_timeout(900)
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
            except TempsEcoule:
                debordement = " — INTERROMPUE, l'agence ne rendait pas la main"
                print(f"  ⏱ arrêt forcé : aucun appel n'a rendu la main en "
                      f"{args.minutes_par_agence:.0f} min. On passe à la suite.")
            finally:
                desarmer()
            conn.commit()
            # Le temps passé est imprimé pour CHAQUE agence : c'est ce qui
            # manquait pour comprendre où filait le budget. Cinq passages tués
            # sans laisser de trace, puis un sixième qui n'a vu que trois
            # agences — la réponse tenait dans une ligne qu'on n'écrivait pas.
            duree = time.monotonic() - debut
            print(f"  ✔ {n} bien(s) enregistré(s)"
                  f" — {vendus} déjà vendu(s), {ecartes} hors cible"
                  f" — {vues} page(s) en {duree / 60:.1f} min{debordement}")
            _noter_visite(cible["site"], date.today().isoformat())
            # Et consigné dans le dépôt, pas seulement imprimé. Le journal du
            # run n'est lisible que depuis l'onglet Actions ; ce fichier-ci
            # est committé, donc lisible depuis git seul — c'est ce qui a
            # permis de comprendre les quatre passages précédents.
            deroule.append({
                "agence": cible["nom"], "secondes": round(duree),
                "pages": vues, "gardes": n,
                "fin": (debordement.strip(" —") or "terminée"),
            })
            total += n
            agences += 1
            # Écrit APRÈS CHAQUE AGENCE, et non une fois à la fin : tué par le
            # garde-fou, le collecteur laissait dans le dépôt le déroulé du
            # checkout précédent, présenté comme celui du passage courant.
            _consigner_deroule(deroule, round((time.monotonic() - depart) / 60, 1))

        navigateur.close()
    conn.close()
    ecoule = (time.monotonic() - depart) / 60
    _consigner_deroule(deroule, round(ecoule, 1))
    print(f"\nTerminé : {total} bien(s) réel(s) ajouté(s) chez {agences} agence(s) "
          f"en {ecoule:.1f} min. Rechargez l'application.")


if __name__ == "__main__":
    main()
