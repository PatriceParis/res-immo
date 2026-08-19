"""Collecte les annonces des réseaux de mandataires (IAD, Safti, Capifrance).

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

from app import db, historique, mandataires  # noqa: E402
from app.chargement import DEPARTEMENTS_CIBLES, preparer_annonce  # noqa: E402
from app.enrichissement import _altitude, _densite, _geocoder, _geocoder_cp  # noqa: E402
from app.extraction import extraire_annonce  # noqa: E402
from app.qualite import est_bien_valide, est_vendu  # noqa: E402

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


def adresses_du_sitemap(sitemaps: list[str], motif,
                        fin_prevue: float | None = None) -> tuple[list[str], bool]:
    """(adresses trouvées, arbre entièrement parcouru).

    Cette lecture n'était bornée par rien. Un réseau publie son catalogue en
    arbre de sitemaps — des centaines de fichiers chez les gros — et le
    parcours entier se payait HORS budget : le 18 août, Capifrance a consommé
    tout le passage sans visiter une seule annonce, et ni IAD ni Safti n'ont eu
    leur tour. Le processus a fini tué par `timeout`, à mi-parcours.

    D'où l'échéance. Et surtout le second membre du couple : un arbre lu à
    moitié rend moins d'adresses, donc moins d'annonces par département — sans
    rien dire. La règle de sortie prendrait cette liste écourtée pour la liste
    complète et retirerait des annonces qu'on n'a jamais cherchées. C'est la
    faute qui a coûté cent soixante-quinze annonces, transposée à la lecture
    du sitemap. On dit donc toujours si l'on a tout vu, et l'appelant marque
    les départements tronqués quand ce n'est pas le cas.
    """
    a_lire, annonces, vus = list(sitemaps), [], set()
    for _ in range(PROFONDEUR):
        suivants = []
        for sitemap in a_lire:
            if fin_prevue is not None and time.monotonic() > fin_prevue:
                return annonces, False
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
            return annonces, True
    # La profondeur est épuisée alors qu'il restait des sitemaps à ouvrir :
    # on n'a pas tout vu non plus.
    return annonces, not a_lire


DEROULE = RACINE / "data" / "deroule_mandataires.json"
_deroule: list[dict] = []
_depart: float | None = None


def etape(nom: str, **details) -> None:
    """Consigne OÙ en est le passage, à chaque étape, immédiatement.

    Ce passage n'a rien rapporté trois jours de suite. J'ai posé deux
    diagnostics — la rotation qui affamait IAD, puis la lecture de sitemap sans
    borne — et corrigé les deux ; l'un et l'autre étaient réels, aucun n'a
    suffi. Le passage du 19 août n'a même pas écrit sa marque de tentative,
    ce qui veut dire qu'il meurt AVANT le premier réseau, quelque part que je
    ne fais que supposer.

    Deviner une troisième fois serait la même faute : conclure de ce qu'on n'a
    pas cherché. On écrit donc le déroulé à mesure, et le prochain passage dira
    lui-même où part son temps — la trace de passage a déjà tranché une
    question qui tenait depuis trois points d'étape, celle-ci va un cran plus
    bas.

    Écrit à CHAQUE étape, pas à la fin : un processus tué n'écrit rien.
    """
    _deroule.append({
        "etape": nom,
        "seconde": round(time.monotonic() - _depart, 1) if _depart else 0.0,
        **details})
    try:
        DEROULE.parent.mkdir(parents=True, exist_ok=True)
        DEROULE.write_text(json.dumps(_deroule, ensure_ascii=False, indent=1)
                           + "\n", encoding="utf-8")
    except OSError:
        pass


def communes_des_terroirs() -> dict:
    """Communes des départements ciblés, via l'API officielle.

    Le périmètre est celui du CHARGEMENT, pas celui des régions. Le Bas-Rhin,
    le Haut-Rhin et le Territoire de Belfort appartiennent à une région ciblée
    mais sont entièrement au-delà de 350 km : l'application écarte leurs biens
    à l'affichage. Les mettre en file consommait un tour de rotation pour des
    annonces qu'on jetait ensuite — trois départements sur trente-six.
    """
    par_dept = {}
    for dept in sorted(DEPARTEMENTS_CIBLES):
        donnees = lire(f"https://geo.api.gouv.fr/departements/{dept}/communes?fields=nom")
        if not donnees:
            continue
        try:
            par_dept[dept] = [c["nom"] for c in json.loads(donnees)]
        except ValueError:
            continue
    return par_dept


def annonces_deja_connues() -> dict:
    """URL → date de dernière constatation, d'après le catalogue publié.

    Sert à progresser DANS un département au lieu d'en relire éternellement
    les mêmes premières annonces.
    """
    try:
        biens = json.loads(
            (RACINE / "data" / "annonces_reel.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {b["url"]: b.get("revue_le") or "" for b in biens if b.get("url")}


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

    # Le département deviné depuis l'adresse ne fait pas foi : les homonymes
    # existent — Péronne est en Saône-et-Loire ET dans la Somme, Sainte-Hélène
    # en Saône-et-Loire ET en Gironde. Quand la PAGE donne un code postal, il
    # tranche, et l'étiquette d'agence suit. Sans cela le site affichait
    # « IAD France (71) » sous une maison de Bordeaux, et le bien comptait dans
    # le budget de collecte d'un département où il n'est pas.
    vrai = mandataires.departement_du_code_postal(brut.get("code_postal"))
    if vrai and vrai != annonce["departement"]:
        if vrai not in DEPARTEMENTS_CIBLES:
            return "ecarte"            # hors périmètre : l'adresse avait menti
        brut["departement"] = vrai
        brut["agence"] = mandataires.nom_d_agence(reseau, vrai)
    else:
        brut["departement"] = brut.get("departement") or annonce["departement"]
    if not est_bien_valide(brut):
        return "ecarte"

    brut["id"] = "%s-%s" % (mandataires.normaliser(brut["agence"]),
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
    # Céder son tour AVANT de dépenser. Lire les sitemaps d'un réseau coûte
    # plusieurs minutes — vingt mille adresses chez IAD — et ce coût était payé
    # hors budget : un réseau dont la part était déjà vide la dépensait quand
    # même en téléchargement, puis s'arrêtait au premier contrôle sans avoir
    # visité un seul département.
    if time.monotonic() > fin_prevue:
        print("  part de budget déjà consommée : ce réseau passe son tour.")
        noter_visite(mandataires.cle_tentative(cle), date.today().isoformat())
        return 0
    sitemaps = sitemaps_declares(reseau["site"])
    etape("sitemaps_declares", reseau=cle, n=len(sitemaps))
    if not sitemaps:
        print("  robots.txt ne déclare aucun sitemap : on s'abstient.")
        noter_visite(mandataires.cle_tentative(cle), date.today().isoformat())
        return 0
    voulus = reseau.get("sitemaps_voulus")
    if voulus:
        retenus = [s for s in sitemaps if voulus.search(s)]
        if retenus:
            print(f"  {len(retenus)} sitemap(s) retenu(s) sur {len(sitemaps)} "
                  f"— on ne lit que ce qui nous concerne")
            sitemaps = retenus
    # La moitié de la part pour DÉCOUVRIR, l'autre pour VISITER. Sans ce
    # partage, la lecture du sitemap pouvait manger le tour entier et le
    # réseau n'ouvrait pas une annonce — c'est ce qui s'est produit.
    fin_sitemap = min(time.monotonic() + (fin_prevue - time.monotonic()) / 2,
                      fin_prevue)
    adresses, sitemap_complet = adresses_du_sitemap(
        sitemaps, reseau["motif_annonce"], fin_sitemap)
    etape("adresses_du_sitemap", reseau=cle, n=len(adresses),
          complet=sitemap_complet)
    print(f"  {len(adresses)} annonce(s) au sitemap"
          f"{'' if sitemap_complet else ' — LECTURE ÉCOURTÉE'}")
    a_visiter = mandataires.annonces_a_visiter(adresses, reseau, index)
    groupes = mandataires.par_departement(a_visiter)
    if args.departements:
        voulus = {d.strip() for d in args.departements.split(",") if d.strip()}
        groupes = {d: lot for d, lot in groupes.items() if d in voulus}
        print(f"  restreint à {sorted(voulus)} — {len(groupes)} département(s) trouvé(s)")
    print(f"  {len(a_visiter)} dans nos terroirs, sur {len(groupes)} département(s)")

    # La tentative est notée ICI, une fois le sitemap lu et avant le premier
    # département : ce réseau a bel et bien eu sa chance ce passage-ci, qu'il
    # aboutisse ou non. Sans cette marque, un réseau qui n'atteint jamais un
    # département reste « jamais vu » à jamais, repasse en tête à chaque
    # passage, et prend la part de ceux qui produisent.
    noter_visite(mandataires.cle_tentative(cle), date.today().isoformat())
    etape("tentative_notee", reseau=cle, departements=len(groupes))

    vu = derniere_visite()
    deja_vues = annonces_deja_connues()
    etape("catalogue_relu", reseau=cle, connues=len(deja_vues))
    total = 0
    # Les départements dont on n'a PAS vu toute la liste : le plafond par
    # département, le budget de temps, ou — depuis le 18 août — un sitemap lu
    # à moitié. La règle de sortie doit s'y abstenir, sinon elle supprime des
    # annonces qu'elle n'a jamais cherchées — voir app/historique.py.
    tronquees: set = set()
    for dept in mandataires.ordre_des_departements(groupes, vu, cle):
        if time.monotonic() > fin_prevue:
            print("  budget de temps atteint — la suite au prochain passage.")
            break
        candidats = mandataires.ordre_dans_le_departement(groupes[dept], deja_vues)
        lot = candidats[:args.max_par_departement]
        # Un sitemap écourté rend une liste écourtée pour CHAQUE département
        # du réseau : aucun n'a été vu en entier, quand bien même son lot
        # tiendrait sous le plafond.
        tronquee = not sitemap_complet or len(candidats) > len(lot)
        gardes = compteurs = 0
        etats = {"garde": 0, "vendu": 0, "ecarte": 0, "illisible": 0}
        for annonce in lot:
            if time.monotonic() > fin_prevue:
                tronquee = True
                break
            etats[enregistrer_une(conn, annonce, reseau)] += 1
            compteurs += 1
            time.sleep(args.delai)
        gardes = etats["garde"]
        conn.commit()
        noter_visite(mandataires.cle_journal(cle, dept), date.today().isoformat())
        if tronquee:
            tronquees.add(historique.identite(
                {"agence": mandataires.nom_d_agence(reseau, dept),
                 "agence_url": reseau["site"]}))
        historique.noter_visite_tronquee(tronquees)
        etape("departement", reseau=cle, departement=dept, visitees=compteurs,
              gardes=gardes, tronquee=tronquee)
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
    parametres.add_argument("--max-par-departement", type=int, default=50,
                            # Vingt-cinq jusqu'ici. Le tour d'un département
                            # avance deux fois plus vite, au prix d'un tour de
                            # rotation deux fois plus lent : un passage couvre
                            # cinq ou six départements au lieu d'une dizaine.
                            # C'est le bon échange tant que la profondeur est
                            # ce qui manque — la Saône-et-Loire compte 1 333
                            # annonces IAD, et vingt-cinq par visite n'en
                            # faisaient pas le tour en un an.
                            help="annonces visitées par département et par passage")
    parametres.add_argument("--delai", type=float, default=1.5,
                            help="secondes entre deux pages")
    parametres.add_argument("--departements",
                            help="codes séparés par des virgules — pour vérifier "
                                 "un terroir précis sans attendre son tour")
    args = parametres.parse_args()

    global _depart
    _depart = time.monotonic()
    etape("demarrage", minutes=args.minutes)

    print("Communes des terroirs ciblés…")
    # Trente-trois appels à l'API officielle, en file, avant quoi que ce soit
    # d'autre : c'est le premier endroit où un passage peut mourir sans laisser
    # de trace, et l'abstention ci-dessous est silencieuse dans le journal git.
    communes = communes_des_terroirs()
    if not communes:
        etape("communes_indisponibles")
        print("Liste des communes indisponible : sans elle on ne sait pas ce qui")
        print("relève de nos terroirs. On s'arrête plutôt que de tout collecter.")
        raise SystemExit(1)
    index = mandataires.index_des_communes(communes)
    etape("communes", departements=len(communes), communes=len(index))
    print(f"  {len(index)} communes sur {len(communes)} département(s)")

    fin_globale = time.monotonic() + args.minutes * 60
    conn = db.connexion()
    total = 0
    # Les réseaux passaient dans l'ordre alphabétique, avec cette seule
    # échéance commune : Capifrance s'abstenait, IAD prenait tout, et Safti —
    # dernier de l'alphabet — n'a jamais eu son tour. On sert donc le plus
    # anciennement vu d'abord, et on découpe le temps pour que le premier ne
    # mange pas la part des suivants.
    choisis = ([args.reseau] if args.reseau
               else mandataires.ordre_des_reseaux(mandataires.RESEAUX,
                                                  derniere_visite()))
    print(f"\nOrdre des réseaux ce passage : {' → '.join(choisis)}")
    etape("ordre_des_reseaux", ordre=choisis)
    for rang, cle in enumerate(choisis):
        part = mandataires.part_de_budget(fin_globale - time.monotonic(),
                                          len(choisis) - rang)
        fin_reseau = min(time.monotonic() + part, fin_globale)
        etape("reseau_debut", reseau=cle, part_secondes=round(part))
        total += collecter_un_reseau(conn, cle, mandataires.RESEAUX[cle], index,
                                     fin_reseau, args)
    conn.close()
    etape("fin", gardes=total)
    print(f"\nTerminé : {total} bien(s) ajouté(s) depuis les réseaux de mandataires.")


if __name__ == "__main__":
    main()
