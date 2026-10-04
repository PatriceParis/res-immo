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

from app import db, exclusions, historique, robot, robots  # noqa: E402
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
# Les rubriques éditoriales qu'un sitemap mêle aux annonces. Le motif ci-dessus
# ne retient que ce qui ressemble à une annonce, et « /blog/revue-de-presse-1/
# vendre-votre-bien-en-48h » lui ressemble. Mesuré au déroulé du 4 octobre
# 2026 : chez Benedic, 25 pages ouvertes sur 30 étaient des articles de blog,
# et le budget de l'agence y est passé ; la veille, Apirem 13 sur 19. Un
# segment entier du chemin, jamais un fragment : une annonce dont le slug
# contiendrait « guide » ou « news » n'est pas visée.
MOTIF_HORS_BIEN = re.compile(
    r"(^|/)(blog|actualites?|actus?|conseils?|revue-de-presse|guides?|articles?|news|magazine|agenda)(/|$)",
    re.IGNORECASE,
)


def _est_page_de_bien(url: str) -> bool:
    """Ressemble à une annonce, et ne vit pas dans une rubrique éditoriale."""
    return bool(MOTIF_BIEN.search(url)) and not MOTIF_HORS_BIEN.search(urlparse(url).path)
# Le robot dit son nom (voir app/robot.py) ; REFUGE_USER_AGENT y est honoré.
UA = robot.USER_AGENT
RE_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)


def _slug(nom: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (nom or "agence").lower()).strip("-")


JOURNAL_VISITES = RACINE / "data" / "agences_visitees.json"


# La rotation et la règle de sortie de l'historique posent la MÊME question —
# « sommes-nous passés chez cette agence ? » — et doivent y répondre pareil.
# Elles ne le faisaient pas : la rotation comparait des domaines, l'historique
# des noms, et cinquante et une annonces Century 21 en ligne ont disparu du
# catalogue. Une seule définition, désormais, dans app/historique.py.
_cle_agence = historique.cle_agence


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


def _configurees(toutes: bool = False) -> list[dict]:
    """Les agences de la configuration, hors celles mises en veille.

    Une agence en veille (`"actif": false`) reste écrite, avec la raison, pour
    qu'on puisse la réveiller d'un mot — la supprimer perdrait l'information.
    Le drapeau existe parce que quelques sites coûtent leur budget entier sans
    jamais rien rapporter : quatre minutes et demie chacun, sur les vingt-huit
    du passage. Cinq d'entre eux se suivent dans l'alphabet, donc tombent dans
    la même tournée : le 11 août, le passage y a laissé quatre-vingts pour
    cent de sa récolte, et celui du 13 s'est encore fait tuer par le temps.

    La désignation EXPLICITE (`-s`) passe outre : on doit toujours pouvoir
    aller voir ce que donne une agence endormie, c'est ainsi qu'on la
    réveillera.
    """
    try:
        agences = json.loads(CONFIG.read_text(encoding="utf-8")).get("agences", [])
    except (OSError, ValueError):
        print(f"Config illisible : {CONFIG}")
        return []
    # Une agence qui a demandé son retrait n'est plus visitée, quoi que dise
    # la configuration — et `toutes` n'y change rien : la promesse des
    # mentions légales n'a pas d'exception (voir app/exclusions.py).
    exclus = exclusions.domaines_exclus()
    agences = [a for a in agences if not exclusions.est_exclu(a.get("site"), exclus)]
    if toutes:
        return agences
    return [a for a in agences if a.get("actif", True)]


def _cibles(site: str, nom: str, index: str) -> list[dict]:
    if site:
        # Une agence DÉJÀ configurée garde son identité, même désignée par son
        # URL. Sans cela, `-s https://immo-ray.com` la rebaptisait
        # « immo-ray.com » : ses biens repartaient sous un autre identifiant et
        # le catalogue se retrouvait avec 21 doublons — le même bien deux fois,
        # sous deux noms d'agence.
        connue = next((a for a in _configurees(toutes=True)
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


def _chercher_robots(url: str) -> tuple[int, str | None]:
    """(statut, texte) de robots.txt, sous notre nom ; (0, None) si c'est
    NOTRE réseau qui flanche — ce qui ne vaut pas interdiction."""
    if requests is None:
        return 0, None
    try:
        r = requests.get(url, headers=dict(robot.ENTETES), timeout=10)
        return r.status_code, r.text
    except Exception:
        return 0, None


def _autorisees(urls: list[str], permission) -> list[str]:
    """Les adresses que robots.txt nous laisse ouvrir — toutes, sans règles."""
    if permission is None:
        return list(urls)
    return [u for u in urls if permission.autorise(u)]


def _sitemap_urls(base: str, fin_prevue: float = 0.0, permission=None,
                  diag: dict | None = None) -> list[str]:
    """URLs de pages de biens listées dans le sitemap.xml (via requests).

    `fin_prevue` borne la RECHERCHE elle-même. Sans cela, une agence pouvait
    y engloutir des minutes — trois chemins candidats, seize requêtes de
    quinze secondes chacune — pendant que le budget de la collecte filait.
    Quatre passages planifiés de suite ont ainsi dépassé la limite du job et
    ont été tués AVANT l'export : le travail était fait, puis jeté.

    Les sitemaps que robots.txt déclare passent en premier : c'est le site qui
    dit où lire. Et ce qu'il refuse n'est pas ouvert.

    `diag` reçoit ce qui s'est passé — « ok 187 », « HTTP 403 », « sans
    <loc> », « injoignable », « interdit par robots.txt ». Jusqu'au 3 octobre,
    un sitemap refusé en 403 et un sitemap absent se terminaient par la même
    ligne, « index : 0 lien(s) », et AdressImmo comme Mosellane sont passées
    de trente pages à zéro sans qu'une ligne du journal dise pourquoi.
    """
    if requests is None:
        return []
    diag = diag if diag is not None else {}
    entetes = dict(robot.ENTETES)
    candidats = list(getattr(permission, "sitemaps", None) or [])
    candidats += [base + chemin for chemin in
                  ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml")]
    for adresse in dict.fromkeys(candidats):
        if fin_prevue and time.monotonic() > fin_prevue:
            diag.setdefault("sitemap", "temps épuisé")
            return []
        if permission is not None and not permission.autorise(adresse):
            diag.setdefault("sitemap", "interdit par robots.txt")
            continue
        try:
            r = requests.get(adresse, headers=entetes, timeout=10)
        except Exception as e:
            diag.setdefault("sitemap", f"injoignable ({e.__class__.__name__})")
            continue
        diag.setdefault("sitemap_statut", r.status_code)
        if r.status_code != 200:
            diag.setdefault("sitemap", f"HTTP {r.status_code}")
            continue
        if "<loc" not in r.text.lower():
            diag.setdefault("sitemap", "sans <loc>")
            continue
        locs = RE_LOC.findall(r.text)
        detail, sous = [], []
        for u in locs:
            (sous if u.lower().endswith(".xml") else detail).append(u)
        for su in _autorisees(sous[:8], permission):   # suivre les sous-sitemaps une fois
            if fin_prevue and time.monotonic() > fin_prevue:
                break
            try:
                detail += RE_LOC.findall(requests.get(su, headers=entetes, timeout=10).text)
            except Exception:
                pass
        biens = _autorisees([u for u in dict.fromkeys(detail) if _est_page_de_bien(u)],
                            permission)
        if biens:
            diag["sitemap"] = f"ok {len(biens)}"
            return biens
        diag.setdefault("sitemap", "aucune page de bien")
    diag.setdefault("sitemap", "absent")
    return []


def _liens_page(page, base: str) -> list[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))") or []
    # L'hôte se compare À L'IDENTIQUE, « www. » compris. C'est trop strict :
    # cent trente-cinq agences sur deux cent trente-cinq sont déclarées sans
    # le préfixe alors que leurs pages vivent avec, et les liens qu'elles
    # écrivent en ABSOLU sont donc tous jetés. On ne rapporte d'elles que ce
    # que leur sitemap veut bien donner.
    #
    # La comparaison a été assouplie le 11 août, puis REMISE COMME CECI le
    # soir même. Le passage suivant a été tué au bout de ses trente-quatre
    # minutes — dix-huit annonces au lieu de cent, cinq agences ayant brûlé
    # leurs quatre minutes et demie sur une seule page. L'explication tient
    # au repli : sur un site SANS sitemap, l'index passait de zéro lien
    # retenu à quatre-vingts, dont la plupart ne mènent à aucun bien, et
    # chaque navigation perdue coûte jusqu'à vingt-cinq secondes.
    #
    # Le correctif n'est pas faux, il est incomplet : il faut d'abord savoir
    # ce que contiennent ces quatre-vingts adresses, et cela demande d'ouvrir
    # les sites — impossible depuis la sandbox, qui n'a pas de réseau. La
    # mesure se fera par une sonde GitHub Actions, comme pour les photos.
    # En attendant, une agence peut être déclarée AVEC son « www. » dans
    # agences_sites.json : c'est ce qui a été fait pour l'Agence Saint-Joseph,
    # et c'est sans risque puisque cela ne touche qu'elle.
    urls, vus, hote = [], set(), urlparse(base).netloc
    for h in hrefs:
        if not h:
            continue
        u = urljoin(base, h).split("#")[0]
        if urlparse(u).netloc == hote and _est_page_de_bien(u) and u not in vus:
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


def _vivier(maxi: int) -> int:
    """Combien d'adresses on met en réserve. Bien plus que de biens voulus :
    beaucoup de pages sont écartées ensuite. Mais c'est un PLAFOND — atteint,
    il signifie qu'on n'a pas vu toute la liste du site, et la règle de sortie
    doit alors s'abstenir."""
    return max(maxi * 8, 80)


def _noter_illisible(diag: dict, url: str, cause: str, html: str = "") -> None:
    """Garde la PREMIÈRE page illisible de l'agence : adresse, cause, <title>
    réellement servi et taille de la page.

    Les 2 et 3 octobre 2026 : Echinard 45 pages illisibles sur 45, Nathalie
    Forest 33 sur 45, Mikit 16 sur 30, ABL Gestion 15 sur 20 — cent neuf pages
    en deux jours, et le déroulé n'en disait que le nombre. Rien pour
    distinguer un mur anti-robot, qui sert au robot une page d'attente, d'un
    gabarit que l'extracteur ne connaît pas : le premier se respecte, le
    second se corrige. Le titre servi tranche en général à lui seul.
    """
    if "illisible_exemple" in diag:
        return
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    diag["illisible_exemple"] = {
        "url": url, "cause": cause,
        "titre": re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else "",
        "octets": len(html or ""),
    }


def _urls_a_visiter(page, cible: dict, base: str, maxi: int,
                    fin_prevue: float = 0.0, permission=None,
                    diag: dict | None = None) -> list[str]:
    # On récupère BEAUCOUP plus d'URL que de biens voulus : beaucoup de pages
    # sont écartées ensuite (biens vendus, appartements, pages catalogue). La
    # boucle d'appel s'arrête d'elle-même une fois `maxi` biens VALIDES gardés.
    diag = diag if diag is not None else {}
    vivier = _vivier(maxi)
    urls = _sitemap_urls(base, fin_prevue, permission, diag)
    if urls:
        print(f"  sitemap : {len(urls)} page(s) de biens")
        return urls[:vivier]
    print(f"  sitemap : {diag.get('sitemap', '?')}")
    # repli : on parcourt les pages « nos biens »
    urls = []
    for idx in _autorisees(cible.get("index") or [base], permission):
        # Seule boucle du collecteur qui n'avait pas d'échéance. Une agence
        # déclarant plusieurs pages d'index pouvait y passer tout le temps de
        # la collecte — trente secondes de navigation chacune — sans que le
        # budget par agence, vérifié seulement DANS la boucle des biens, ait
        # jamais son mot à dire.
        if fin_prevue and time.monotonic() > fin_prevue:
            print("  ⏱ temps épuisé pendant la recherche des pages de biens")
            break
        try:
            reponse = page.goto(idx, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1800)
        except Exception as e:
            print(f"  ✘ index injoignable {idx} ({e.__class__.__name__})")
            diag.setdefault("index_statut", e.__class__.__name__)
            continue
        # Le statut et le titre de la page d'index : une page d'attente
        # anti-robot répond souvent 200 ou 202 avec un titre qui n'est pas
        # celui du site, et zéro lien. Sans ces deux champs, elle est
        # indiscernable d'une agence sans biens.
        diag.setdefault("index_statut", reponse.status if reponse else None)
        try:
            diag.setdefault("index_titre", (page.title() or "")[:60])
        except Exception:
            pass
        for u in _autorisees(_liens_page(page, base), permission):
            if u not in urls:
                urls.append(u)
    # depuis un index, on ne garde que les liens qui ressemblent à un détail
    # (un chiffre dans le chemin) pour éviter les pages de catégorie.
    details = [u for u in urls if re.search(r"\d", urlparse(u).path)]
    choix = details or urls
    print(f"  index : {len(choix)} lien(s) de bien repéré(s)"
          + (f" (HTTP {diag['index_statut']}, « {diag.get('index_titre', '')} »)"
             if diag.get("index_statut") is not None else ""))
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
    tronquees: set = set()
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
            n, vendus, ecartes, vues, illisibles = 0, 0, 0, 0, 0
            debordement = ""
            # Ce qui s'est passé AVANT la première page de bien : sitemap,
            # index, robots.txt. Consigné dans le déroulé, car c'est là que se
            # décide « zéro page », et le journal du run ne disait rien.
            diag: dict = {}
            # Vrai dès qu'on s'arrête AVANT d'avoir épuisé la liste du site.
            # C'est la seule chose qui permette à la règle de sortie de
            # distinguer « ce bien a disparu » de « on n'a pas été jusqu'à lui ».
            tronquee = False
            # robots.txt d'abord, sous notre nom. Un site qui nous ferme sa
            # racine n'est pas visité — pas une page, pas le sitemap. La page
            # /robot le promettait depuis le 1er octobre ; le collecteur de
            # production ne lisait rien. Ses biens ne sont pas protégés par
            # la règle de sortie : on ne publie pas ce qu'on n'a plus le droit
            # de lire, et ils sortiront comme des biens disparus.
            permission = robots.lire(base, _chercher_robots)
            diag["robots"] = ("interdit" if permission.tout_interdit(base)
                              else "absent" if permission.statut in robots.ABSENT
                              else "illisible" if not permission.statut
                              else "ok")
            if permission.tout_interdit(base):
                print("  ⛔ robots.txt nous interdit ce site : on n'y touche pas.")
                _noter_visite(cible["site"], date.today().isoformat())
                deroule.append({"agence": cible["nom"], "secondes": 0,
                                "pages": 0, "gardes": 0, "fin": "robots.txt interdit",
                                **diag})
                agences += 1
                _consigner_deroule(deroule, round((time.monotonic() - depart) / 60, 1))
                continue
            # Le Crawl-delay demandé, s'il y en a un : on ne va jamais plus
            # vite que ce que le site demande. Une page coûte déjà ~1,5 s de
            # navigation ; on attend le complément.
            pause = max(0.0, (permission.delai() or 0.0) - 1.5)
            # Trente secondes de marge sur le budget : le temps de finir
            # proprement le bien en cours avant que le réveil ne sonne.
            desarmer = borner(args.minutes_par_agence * 60 + 30)
            try:
                urls = _urls_a_visiter(page, cible, base, maxi, fin_agence, permission, diag)
                if len(urls) >= _vivier(maxi):
                    tronquee = True    # la réserve d'adresses elle-même est coupée
                for u in urls:
                    if n >= maxi:          # on s'arrête sur les biens GARDÉS,
                        tronquee = True    # pas sur les pages visitées
                        break
                    if vues >= pages_max:
                        print(f"  … plafond de {pages_max} pages atteint pour cette agence")
                        tronquee = True
                        break
                    if time.monotonic() > fin_agence:
                        debordement = (" — temps de l'agence épuisé"
                                       if time.monotonic() <= fin_prevue
                                       else " — budget global épuisé")
                        tronquee = True
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
                    except Exception as e:
                        illisibles += 1
                        _noter_illisible(diag, u, f"navigation : {e.__class__.__name__}")
                        continue
                    if pause:
                        time.sleep(pause)
                    brut = extraire_annonce(html, u, source=_slug(cible["nom"]),
                                            agence=cible["nom"], agence_url=base)
                    if not brut:
                        # Une page ouverte où l'on ne lit aucune annonce. Quarante-
                        # cinq fois de suite chez Echinard les 1er et 3 octobre, là
                        # où la semaine d'avant en donnait sept sur quarante-cinq :
                        # la signature d'une page servie au robot qui n'est pas
                        # celle servie au visiteur. Comptée, pour qu'on la voie —
                        # et pour la distinguer d'une agence dont tout est vendu,
                        # qui compte ses pages dans `vendus`.
                        illisibles += 1
                        _noter_illisible(diag, u, "aucune annonce lue", html)
                        continue
                    # Rejette les pages où l'extraction n'a pas trouvé un vrai titre
                    # d'annonce (titre = nom de l'agence / du site) : peu exploitables.
                    titre_bas = (brut.get("titre") or "").strip().lower()
                    hote = urlparse(base).netloc.replace("www.", "")
                    if not titre_bas or titre_bas in (cible["nom"].lower(), hote):
                        illisibles += 1
                        _noter_illisible(diag, u, "titre = nom du site", html)
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
                tronquee = True
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
                  f" — {vendus} déjà vendu(s), {ecartes} hors cible, {illisibles} illisible(s)"
                  f" — {vues} page(s) en {duree / 60:.1f} min{debordement}")
            _noter_visite(cible["site"], date.today().isoformat())
            if tronquee:
                tronquees.add(historique.identite(
                    {"agence": cible["nom"], "agence_url": base}))
            historique.noter_visite_tronquee(tronquees)
            # Et consigné dans le dépôt, pas seulement imprimé. Le journal du
            # run n'est lisible que depuis l'onglet Actions ; ce fichier-ci
            # est committé, donc lisible depuis git seul — c'est ce qui a
            # permis de comprendre les quatre passages précédents.
            #
            # Avec, depuis le 3 octobre, le sort de chaque page et ce qui s'est
            # passé avant la première : « 45 pages, 0 gardé » ne suffisait pas
            # à distinguer une agence dont tout est vendu d'une agence qui sert
            # au robot une page qui n'est pas la sienne.
            deroule.append({
                "agence": cible["nom"], "secondes": round(duree),
                "pages": vues, "gardes": n,
                "vendus": vendus, "ecartes": ecartes, "illisibles": illisibles,
                "fin": (debordement.strip(" —") or "terminée"),
                **diag,
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
