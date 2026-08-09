"""Compare ce que voit la VÉRIFICATION et ce que voit le NAVIGATEUR.

Pourquoi ce troisième outil de diagnostic
-----------------------------------------
`scripts/verifier_photos.py` ouvre chaque image depuis un runner GitHub, en
direct. Le visiteur, lui, ne voit jamais l'image en direct : elle lui arrive
par `/api/photo`, notre relais hébergé sur Vercel. Deux chemins différents,
deux résultats possibles — et c'est exactement ce qui s'est produit chez
Groupe 123 Immo : l'adresse retenue passait la vérification, et la fiche
restait pourtant illustrée par le dessin de repli.

Tant qu'on ne mesure que le premier chemin, on croit le catalogue illustré
alors qu'il ne l'est pas. Cette sonde interroge les DEUX pour la même image
et met les réponses côte à côte.

Elle ne modifie rien : elle lit et affiche.

Depuis l'examen juridique du relais, elle mesure aussi le HOTLINK HONNÊTE :
l'image demandée avec le Referer de notre propre site, comme le ferait le
navigateur d'un visiteur si l'on retirait le relais. C'est la donnée qui
manque pour décider de l'architecture — combien de photos survivraient.

Usage :
    python scripts/diagnostiquer_relais.py <url d'annonce> [<url> …]
    python scripts/diagnostiquer_relais.py --agence "Groupe123immo"
    python scripts/diagnostiquer_relais.py --echantillon 30
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.chargement import _candidates  # noqa: E402
from app.photos import ressemble_a_une_photo  # noqa: E402

SITE = "https://res-immo.vercel.app"
SECONDES = 15
PLAFOND = 8_000_000
CANDIDATES = 4
_NAVIGATEUR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def _demander(url: str, referer: str | None) -> tuple[str, str, int]:
    """(état, type de contenu, octets) — sans jamais lever."""
    entetes = {
        "User-Agent": _NAVIGATEUR,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }
    if referer:
        entetes["Referer"] = referer
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=entetes), timeout=SECONDES) as r:
            donnees = r.read(PLAFOND)
            return str(r.status), (r.headers.get("Content-Type") or "").split(";")[0], len(donnees)
    except urllib.error.HTTPError as erreur:
        return str(erreur.code), (erreur.headers.get("Content-Type") or "").split(";")[0], 0
    except Exception as erreur:  # DNS, TLS, délai dépassé…
        return type(erreur).__name__, "", 0


def _par_le_relais(image: str, page: str) -> tuple[str, str, int]:
    return _demander(f"{SITE}/api/photo?u={quote(image, safe='')}&p={quote(page, safe='')}",
                     referer=None)


def _origine(page: str) -> str:
    morceaux = urlparse(page)
    return f"{morceaux.scheme}://{morceaux.netloc}/" if morceaux.netloc else ""


def sonder_une(annonce: dict) -> list[dict]:
    page = annonce.get("url") or ""
    retenue = annonce.get("photo") or ""
    lignes = []
    for image in _candidates(annonce)[:CANDIDATES]:
        etat, type_direct, taille = _demander(image, _origine(page))
        photo = ""
        if taille:
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(image, headers={
                            "User-Agent": _NAVIGATEUR,
                            "Referer": _origine(page)}), timeout=SECONDES) as r:
                    bonne, motif = ressemble_a_une_photo(r.read(PLAFOND))
                photo = ("photo" if bonne else motif)[:24]
            except Exception:
                photo = "illisible"
        ligne = {
            "image": image, "retenue": image == retenue,
            "direct": etat, "type": type_direct, "octets": taille, "verdict": photo,
        }
        if image == retenue:
            # Le hotlink HONNÊTE : l'image demandée comme le ferait le
            # navigateur d'un visiteur de notre site — Referer à NOTRE nom,
            # sans déguisement. C'est la seule mesure qui dise si la fiche
            # resterait illustrée une fois le relais retiré. « Sans referer »
            # complète le tableau : certains CDN acceptent tout sauf un
            # referer étranger, d'autres exigent celui de l'agence.
            etat_nous, _tn, octets_nous = _demander(image, SITE + "/")
            etat_nu, _tv, octets_nu = _demander(image, None)
            ligne.update({"nous": etat_nous, "octets_nous": octets_nous,
                          "nu": etat_nu, "octets_nu": octets_nu})
        relais, type_relais, taille_relais = _par_le_relais(image, page)
        ligne.update({"relais": relais, "type_relais": type_relais,
                      "octets_relais": taille_relais})
        lignes.append(ligne)
    return lignes


def _annonces(args) -> list[dict]:
    biens = json.loads(
        (RACINE / "data" / "annonces_reel.json").read_text(encoding="utf-8"))
    if args.urls:
        voulus = set(args.urls)
        return [b for b in biens if b.get("url") in voulus]
    if args.agence:
        cle = args.agence.casefold()
        return [b for b in biens
                if cle in (b.get("agence") or "").casefold()
                or cle in (b.get("url") or "").casefold()]
    # Échantillon PAR HÉBERGEUR, deux annonces chacun, les plus gros hôtes
    # D'ABORD. La première version prenait les hébergeurs dans l'ordre du
    # fichier : le plafond de soixante annonces tombait au milieu de
    # l'alphabet, et IAD — un tiers du catalogue à lui seul — n'était jamais
    # mesuré. Deux passages de sonde ont conclu « tout va bien » sur un
    # échantillon qui ignorait justement le plus gros enjeu.
    par_hote: dict = {}
    for b in biens:
        if not b.get("photo"):
            continue
        hote = urlparse(b["photo"]).hostname or "?"
        par_hote.setdefault(hote, []).append(b)
    choix = []
    for hote in sorted(par_hote, key=lambda h: -len(par_hote[h])):
        choix.extend(par_hote[hote][:2])
    return choix[:args.echantillon]


def main() -> None:
    parametres = argparse.ArgumentParser()
    parametres.add_argument("urls", nargs="*", help="adresses d'annonces à sonder")
    parametres.add_argument("--agence", help="toutes les annonces d'une agence")
    parametres.add_argument("--echantillon", type=int, default=60,
                            help="à défaut, sonder jusqu'à N annonces, deux par "
                                 "hébergeur d'images")
    args = parametres.parse_args()

    annonces = _annonces(args)
    if not annonces:
        print("Aucune annonce ne correspond.")
        raise SystemExit(1)

    print(f"Sonde de {len(annonces)} annonce(s). Pour chaque image : réponse EN DIRECT")
    print(f"(comme la vérification) puis PAR LE RELAIS {SITE}/api/photo")
    print("(comme le navigateur du visiteur).\n")

    desaccords = manquantes = 0
    par_hote: dict = {}
    for annonce in annonces:
        print(f"── {(annonce.get('agence') or '?')} · {(annonce.get('commune') or '?')}")
        print(f"   {annonce.get('url')}")
        lignes = sonder_une(annonce)
        if not lignes:
            print("   (aucune candidate)")
            continue
        aucune_affichable = True
        for ligne in lignes:
            direct_ok = ligne["octets"] > 0 and ligne["verdict"] == "photo"
            relais_ok = ligne["octets_relais"] > 0
            if relais_ok:
                aucune_affichable = False
            if direct_ok != relais_ok:
                desaccords += 1
            marque = "◀ retenue" if ligne["retenue"] else ""
            print(f"   direct {ligne['direct']:>12} {ligne['octets']:>8} o "
                  f"{ligne['verdict'][:22]:22} │ relais {ligne['relais']:>12} "
                  f"{ligne['octets_relais']:>8} o  {marque}")
            print(f"     {ligne['image'][:118]}")
            if "nous" in ligne:
                print(f"     hotlink honnête {ligne['nous']:>9} "
                      f"{ligne['octets_nous']:>8} o · sans referer "
                      f"{ligne['nu']:>9} {ligne['octets_nu']:>8} o")
                hote = urlparse(ligne["image"]).hostname or "?"
                testes, ok = par_hote.get(hote, (0, 0))
                reussi = ligne["nous"] == "200" and ligne["octets_nous"] > 0
                par_hote[hote] = (testes + 1, ok + (1 if reussi else 0))
        if aucune_affichable:
            manquantes += 1
            print("   ⚠ AUCUNE candidate ne passe le relais : la fiche restera sans photo.")
        print()

    print(f"Bilan : {desaccords} désaccord(s) entre le direct et le relais, "
          f"{manquantes} annonce(s) qu'aucune image n'illustre côté visiteur.")

    if par_hote:
        total = sum(t for t, _ in par_hote.values())
        vivants = sum(o for _, o in par_hote.values())
        print("\nHotlink honnête (Referer = notre site), hébergeur par hébergeur :")
        for hote, (testes, ok) in sorted(par_hote.items(), key=lambda kv: -kv[1][0]):
            print(f"   {ok:>2}/{testes:<2} {hote}")
        print(f"\nSans le relais, {vivants} photo(s) retenue(s) sur {total} "
              f"resteraient affichées.")


if __name__ == "__main__":
    main()
