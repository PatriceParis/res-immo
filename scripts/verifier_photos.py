"""Vérifie que chaque annonce affiche une VRAIE photo — avant publication.

Jusqu'ici, la photo d'une annonce était choisie sur la seule foi de son
adresse, et personne ne l'avait jamais ouverte. Deux conséquences, toutes
deux signalées par l'utilisateur :

  - des fiches sans image alors que la photo existait, parce que l'adresse
    trouvée dans les données structurées du site ne répondait pas
    (Groupe 123 Immo annonçait `/600xauto/images/1/…` quand ses photos
    vivent sous `/580xauto/images/biens/1/…`) ;
  - une étiquette DPE affichée en guise de maison, servie par le même script
    que les vraies photos — donc impossible à écarter sur l'adresse.

Ce script ouvre chaque candidate, dans l'ordre de confiance, et retient la
première qui se charge ET ressemble à une photographie (voir app/photos.py).
Les autres sont écartées. Une annonce sans aucune candidate valable garde son
illustration de repli, qui ne prétend rien — mais elle est comptée et
signalée, car ce cas doit rester rare.

Usage :  python scripts/verifier_photos.py [--limite N] [--journal]
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db  # noqa: E402
from app.chargement import _candidates, _photos_de_mobilier  # noqa: E402
from app.photos import ressemble_a_une_photo  # noqa: E402

# Au-delà, ce n'est plus une vignette d'annonce et on ne veut pas la charger.
PLAFOND_OCTETS = 8_000_000
SECONDES = 10
# On ne teste pas indéfiniment : si les six premières candidates d'une annonce
# échouent, la septième n'a aucune raison de réussir.
CANDIDATES_MAX = 6
# Les agences tolèrent mal une rafale ; huit fils suffisent à tenir le budget
# de temps d'une collecte sans les brusquer.
FILS = 8
# En deçà de cette proportion d'images qui répondent, on suspecte le réseau
# plutôt que les photos, et on n'enregistre rien (voir le garde-fou).
PART_MINIMALE = 0.4

_NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def telecharger(url: str, page: str | None) -> bytes | None:
    """L'image, telle qu'un navigateur affichant `page` la recevrait."""
    cible = urlparse(url)
    origine = urlparse(page or "")
    referer = (f"{origine.scheme}://{origine.netloc}/"
               if origine.scheme in ("http", "https") and origine.netloc
               else f"{cible.scheme}://{cible.netloc}/")
    requete = urllib.request.Request(url, headers={
        "User-Agent": _NAVIGATEUR,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": referer,
    })
    try:
        with urllib.request.urlopen(requete, timeout=SECONDES) as reponse:
            type_contenu = (reponse.headers.get("Content-Type") or "").lower()
            if not type_contenu.startswith("image/"):
                return None
            return reponse.read(PLAFOND_OCTETS)
    except Exception:
        return None


def verifier_une(annonce: dict, journal: bool = False,
                 mobilier: set | None = None) -> tuple[str | None, str]:
    """La première candidate qui se charge et ressemble à une photo.

    Le mobilier de site est écarté ici, et non plus seulement au chargement.
    Sans cela, la photo publiée n'était pas celle que le site affichait : le
    catalogue comptait 47 annonces « illustrées » par une image que le
    chargement rejetait ensuite comme répétée — dix maisons de l'Agence du
    Terroir partageaient un même cliché. Le visiteur voyait le dessin de
    repli, le décompte annonçait une photo.
    """
    mobilier = mobilier or set()
    for url in _candidates(annonce)[:CANDIDATES_MAX]:
        if url in mobilier:
            if journal:
                print(f"      ✗ mobilier de site {url[:80]}")
            continue
        donnees = telecharger(url, annonce.get("url"))
        if donnees is None:
            if journal:
                print(f"      ✗ injoignable  {url[:88]}")
            continue
        bonne, motif = ressemble_a_une_photo(donnees)
        if journal:
            print(f"      {'✓' if bonne else '✗'} {motif:52} {url[:70]}")
        if bonne:
            return url, motif
    return None, "aucune candidate valable"


def _verifier_export(fichier: Path, args) -> None:
    """Repasse sur TOUT le catalogue publié, pas seulement la dernière collecte.

    La vérification s'insère dans la collecte, qui ne voit que les annonces
    du jour. Les autres — la grande majorité — ont été publiées avant qu'elle
    n'existe : ce mode les rattrape en une fois.
    """
    import json

    annonces = json.loads(fichier.read_text(encoding="utf-8"))
    mobilier = _photos_de_mobilier(annonces)
    a_verifier = [a for a in annonces if _candidates(a)]
    if args.limite:
        a_verifier = a_verifier[:args.limite]

    def travail(annonce):
        if args.journal:
            print(f"  {(annonce.get('titre') or '')[:60]}")
        return annonce, *verifier_une(annonce, args.journal, mobilier)

    with ThreadPoolExecutor(max_workers=FILS) as executeur:
        resultats = list(executeur.map(travail, a_verifier))

    reussites = [r for r in resultats if r[1]]
    if len(resultats) >= 20 and len(reussites) < PART_MINIMALE * len(resultats):
        print(f"ARRÊT : {len(reussites)}/{len(resultats)} images seulement ont "
              f"répondu. C'est un problème de réseau, pas de photos — "
              f"aucune modification enregistrée.")
        raise SystemExit(1)

    changees = 0
    for annonce, retenue, _motif in resultats:
        if retenue != annonce.get("photo"):
            annonce["photo"] = retenue
            changees += 1
    fichier.write_text(json.dumps(annonces, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
    sans = len(resultats) - len(reussites)
    print(f"{len(resultats)} annonce(s) vérifiée(s) : {len(reussites)} avec une vraie "
          f"photo, {sans} sans. {changees} corrigée(s).")


def main() -> None:
    parametres = argparse.ArgumentParser()
    parametres.add_argument("--limite", type=int, default=0,
                            help="n'en vérifier que N (mise au point)")
    parametres.add_argument("--journal", action="store_true",
                            help="détailler chaque candidate testée")
    parametres.add_argument("--json", metavar="FICHIER",
                            help="vérifier l'export plutôt que la base — pour "
                                 "repasser sur tout le catalogue déjà publié")
    args = parametres.parse_args()

    if args.json:
        return _verifier_export(Path(args.json), args)

    conn = db.connexion()
    lignes = conn.execute(
        "SELECT id, url, photo, photos_json, titre, agence FROM annonces "
        "WHERE source IS NOT NULL AND source <> 'démo'").fetchall()
    annonces = []
    for ligne in lignes:
        import json
        annonce = dict(ligne)
        try:
            annonce["photos"] = json.loads(annonce.pop("photos_json") or "[]")
        except ValueError:
            annonce["photos"] = []
        annonces.append(annonce)
    mobilier = _photos_de_mobilier(annonces)
    if args.limite:
        annonces = annonces[:args.limite]

    def travail(annonce):
        if not _candidates(annonce):
            return annonce, None, "aucune image trouvée sur la page"
        if args.journal:
            print(f"  {(annonce.get('titre') or '')[:60]}")
        retenue, motif = verifier_une(annonce, args.journal, mobilier)
        return annonce, retenue, motif

    with ThreadPoolExecutor(max_workers=FILS) as executeur:
        resultats = list(executeur.map(travail, annonces))

    avaient_une_photo = [r for r in resultats if r[0].get("photo")]
    reussites = [r for r in avaient_une_photo if r[1]]
    # GARDE-FOU. Ce script décide de ce qu'on affiche à partir de ce que le
    # réseau répond : coupé, il conclurait que TOUTES les photos sont mortes
    # et viderait le catalogue. Un échec massif ne prouve rien sur les images
    # — il prouve qu'on n'a pas pu les voir. On ne touche à rien.
    if len(avaient_une_photo) >= 20 and len(reussites) < PART_MINIMALE * len(avaient_une_photo):
        conn.close()
        print(f"ARRÊT : {len(reussites)}/{len(avaient_une_photo)} images seulement ont "
              f"répondu. C'est un problème de réseau, pas de photos — "
              f"aucune modification enregistrée.")
        raise SystemExit(1)

    changees = orphelines = 0
    for annonce, retenue, motif in resultats:
        if retenue != annonce.get("photo"):
            conn.execute("UPDATE annonces SET photo = ? WHERE id = ?",
                         (retenue or "", annonce["id"]))
            changees += 1
        if not retenue:
            orphelines += 1
    conn.commit()
    conn.close()

    verifiees = len(resultats) - orphelines
    print(f"{len(resultats)} annonce(s) vérifiée(s) : {verifiees} avec une vraie photo "
          f"({verifiees * 100 // max(len(resultats), 1)} %), {orphelines} sans.")
    print(f"  {changees} photo(s) corrigée(s) par la vérification.")
    if orphelines:
        print("  Sans photo utilisable :")
        for annonce, retenue, motif in resultats:
            if not retenue:
                print(f"    {(annonce.get('agence') or '?')[:22]:22} "
                      f"{(annonce.get('titre') or '')[:46]:46} — {motif}")


if __name__ == "__main__":
    main()
