"""Audit de l'interface telle que l'utilisateur la voit.

`app/coherence.py` vérifie les promesses au niveau de l'API. Ça ne suffit
pas : le défaut le plus grave trouvé jusqu'ici — « 📷 1 / 9 » et « 8 autres
photos + le dossier complet » — était **entièrement dans le JavaScript**.
L'API était irréprochable ; c'est la page qui inventait un nombre à partir
d'un hachage de l'identifiant du bien, et le présentait comme un fait.

Ce script ouvre donc la vraie page dans un vrai navigateur et compare **ce
qui est écrit à l'écran** avec ce que l'API répond. Trois familles :

    1. Les nombres affichés (compteur, pastilles) disent la vérité.
    2. Les contrôles font ce qu'ils annoncent (cocher une case change la
       liste, cliquer une pastille donne le compte promis).
    3. Aucune promesse chiffrée n'est fabriquée : tout nombre que la page
       présente comme une quantité doit venir des données.

Usage :
    python scripts/auditer_interface.py            # démarre le serveur lui-même
    python scripts/auditer_interface.py --url https://res-immo.vercel.app
    python scripts/auditer_interface.py --strict   # sort en erreur si un
                                                   # manquement est constaté
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import coherence  # noqa: E402

# Promesses chiffrées repérables dans le texte de la page. Chacune doit
# pouvoir être justifiée par les données ; sinon elle est fabriquée.
PROMESSES_CHIFFREES = (
    (re.compile(r"(\d+)\s*/\s*(\d+)\s*photos?", re.I), "un compte de photos"),
    (re.compile(r"(\d+)\s+autres?\s+photos?", re.I), "un nombre d'autres photos"),
    (re.compile(r"\+\s*(\d+)\s*$"), "un compte de vignettes supplémentaires"),
)

# Fabrication d'une valeur affichée : un hachage ou un tirage aléatoire n'a
# rien à faire dans un nombre présenté à l'utilisateur comme un fait. C'est
# exactement d'où venait `nbPhotos()`.
SOURCES_FABRIQUEES = (
    (re.compile(r"Math\.random"), "un tirage aléatoire"),
    (re.compile(r"empreinte\s*\([^)]*\)\s*%"), "un hachage de l'identifiant"),
)
# L'illustration de repli a le droit de varier selon le bien : c'est un décor
# assumé, pas une affirmation. Elle est la seule exception.
FONCTIONS_DECORATIVES = ("illustration",)


class Constat:
    def __init__(self) -> None:
        self.manquements: list[tuple[str, str]] = []
        self.verifies: list[str] = []

    def promesse(self, nom: str) -> None:
        self.verifies.append(nom)

    def manque(self, nom: str, detail: str) -> None:
        self.manquements.append((nom, detail))


# --- Démarrage du serveur ---------------------------------------------------


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _attendre(url: str, secondes: int = 40) -> bool:
    fin = time.time() + secondes
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url + "/api/meta", timeout=2):
                return True
        except Exception:
            time.sleep(0.4)
    return False


# --- Vérifications DOM ------------------------------------------------------


def _nombre(texte: str) -> int | None:
    m = re.search(r"(\d[\d   ]*)", texte or "")
    if not m:
        return None
    return int(re.sub(r"\D", "", m.group(1)) or 0)


def verifier_page(page, appeler, constat: Constat) -> None:
    """Compare ce qui est écrit à l'écran avec ce que l'API répond."""

    # 1. Le compteur décrit la liste réellement affichée.
    page.wait_for_selector(".fiche, .liste .vide", timeout=20_000)
    compteur = page.text_content("#compteur") or ""
    annonce = _nombre(compteur)
    cartes = page.locator(".fiche").count()
    total_api = appeler("/api/annonces", {"limit": coherence.PLAFOND_API})["total"]
    if annonce != total_api:
        constat.manque("compteur affiché",
                       f"la page écrit « {compteur.strip()} », l'API en compte {total_api}")
    elif cartes != annonce and "premiers affichés" not in compteur:
        constat.manque("compteur affiché",
                       f"« {compteur.strip()} » mais {cartes} fiche(s) à l'écran, "
                       "sans mention de troncature")
    else:
        constat.promesse("le compteur décrit la liste réellement affichée")

    # 2. Les pastilles de terroir affichées somment au compteur. On lit le
    #    compte de biens (.nb), pas le rang ni l'indice sur 100 qui figurent
    #    aussi sur la pastille.
    nbs = page.locator(".terroir .nb")
    if nbs.count():
        somme = sum(_nombre(nbs.nth(i).text_content() or "") or 0
                    for i in range(nbs.count()))
        if somme != annonce:
            constat.manque("pastilles de terroir",
                           f"somme affichée {somme} ≠ compteur {annonce}")
        else:
            constat.promesse("la somme des pastilles affichées égale le compteur")

        # Cliquer une pastille doit donner exactement le nombre qu'elle annonce
        # — c'est le bug d'origine, vu depuis l'écran.
        premiere = page.locator(".terroir").first
        promis = _nombre(premiere.locator(".nb").text_content() or "")
        premiere.click()
        page.wait_for_timeout(800)
        obtenu = _nombre(page.text_content("#compteur") or "")
        premiere.click()          # on désélectionne pour la suite
        page.wait_for_timeout(600)
        if promis != obtenu:
            constat.manque("pastille cliquée",
                           f"la pastille annonçait {promis} bien(s), le clic en donne {obtenu}")
        else:
            constat.promesse("cliquer une pastille donne exactement le nombre annoncé")

    # 3. Cocher une case change vraiment ce qui est affiché.
    for param, (libelle, _) in coherence.CASES_A_COCHER.items():
        case = page.locator(f"#f-{param.replace('_', '-')}")
        if not case.count():
            continue
        avant = page.locator(".fiche").count()
        case.check()
        page.wait_for_timeout(700)
        apres = page.locator(".fiche").count()
        attendu = appeler("/api/annonces",
                          {param: 1, "limit": coherence.PLAFOND_API})["total"]
        case.uncheck()
        page.wait_for_timeout(500)
        if apres != min(attendu, coherence.PLAFOND_API):
            constat.manque(f"case « {libelle} »",
                           f"{apres} fiche(s) affichée(s) pour {attendu} attendue(s)")
        elif apres == avant and avant > 20:
            constat.manque(f"case « {libelle} »",
                           f"ne retire aucun bien ({avant} avant comme après)")
        else:
            constat.promesse(f"la case « {libelle} » filtre réellement l'affichage")

    # 4. Aucune promesse chiffrée fabriquée dans le corps de la page.
    corps = page.text_content("body") or ""
    for motif, quoi in PROMESSES_CHIFFREES:
        trouve = motif.search(corps)
        if trouve:
            constat.manque("promesse chiffrée non sourcée",
                           f"la page annonce {quoi} (« {trouve.group(0).strip()} ») "
                           "alors que les données ne portent qu'une photo par bien")
    if not any(m.search(corps) for m, _ in PROMESSES_CHIFFREES):
        constat.promesse("aucune promesse chiffrée fabriquée dans la liste")

    # 5. Une fiche ouverte ne fabrique rien non plus (c'est là que vivait
    #    « 8 autres photos + le dossier complet »).
    if cartes:
        page.locator(".fiche").first.click()
        page.wait_for_timeout(900)
        fiche = page.text_content("#modale-contenu") or ""
        fautes = [(m.search(fiche), quoi) for m, quoi in PROMESSES_CHIFFREES]
        fautes = [(t, q) for t, q in fautes if t]
        for trouve, quoi in fautes:
            constat.manque("promesse chiffrée non sourcée (fiche détaillée)",
                           f"la fiche annonce {quoi} : « {trouve.group(0).strip()} »")
        if not fautes:
            constat.promesse("aucune promesse chiffrée fabriquée sur la fiche détaillée")


def verifier_source_js(constat: Constat) -> None:
    """Interdit qu'un nombre affiché soit tiré d'un hachage ou du hasard.

    C'est la garde statique : `nbPhotos()` renvoyait
    `6 + empreinte(identifiant) % 7`, affiché tel quel. Une valeur présentée
    comme un fait ne peut pas venir d'un calcul sans rapport avec le bien.
    """
    source = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")
    for i, ligne in enumerate(source.splitlines(), start=1):
        if ligne.lstrip().startswith("//"):
            continue
        for motif, quoi in SOURCES_FABRIQUEES:
            if motif.search(ligne):
                contexte = source[:source.index(ligne)]
                fonction = re.findall(r"function\s+(\w+)", contexte)
                if fonction and fonction[-1] in FONCTIONS_DECORATIVES:
                    continue  # décor assumé (illustration de repli)
                constat.manque(
                    "valeur fabriquée dans l'interface",
                    f"app.js:{i} — une valeur vient {quoi} "
                    f"(fonction « {fonction[-1] if fonction else '?'} »)")
    if not any(n == "valeur fabriquée dans l'interface" for n, _ in constat.manquements):
        constat.promesse("aucune valeur affichée ne vient d'un hachage ou du hasard")


# --- Programme --------------------------------------------------------------


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--url", help="site déjà en ligne à auditer")
    parseur.add_argument("--strict", action="store_true",
                        help="sortir en erreur si une promesse n'est pas tenue")
    args = parseur.parse_args()

    serveur = None
    if args.url:
        base = args.url.rstrip("/")
    else:
        port = _port_libre()
        base = f"http://127.0.0.1:{port}"
        serveur = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=RACINE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def appeler(chemin: str, params: dict) -> dict:
        from urllib.parse import urlencode
        url = base + chemin + ("?" + urlencode(params) if params else "")
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())

    constat = Constat()
    try:
        if not _attendre(base):
            print(f"Serveur injoignable : {base}")
            return 2

        print(f"Audit de l'interface — {base}\n")

        # a) Le contrat de cohérence, au niveau de l'API.
        for rapport in coherence.verifier(appeler):
            if rapport.tenue:
                constat.promesse(rapport.promesse)
            else:
                for m in rapport.manquements:
                    constat.manque(rapport.invariant, m)

        # b) La garde statique sur le JavaScript.
        verifier_source_js(constat)

        # c) Ce que l'utilisateur voit vraiment, dans un vrai navigateur.
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("⚠ Playwright absent : la vérification dans le navigateur est "
                  "sautée (pip install playwright).\n")
        else:
            with sync_playwright() as p:
                # Même convention que scripts/collecter_navigateur.py : un
                # Chromium déjà présent sur la machine peut être désigné, sans
                # avoir à retélécharger celui de Playwright.
                navigateur = p.chromium.launch(
                    executable_path=os.environ.get("REFUGE_CHROMIUM") or None,
                    headless=True)
                page = navigateur.new_page(viewport={"width": 1280, "height": 900})
                try:
                    page.goto(base, wait_until="networkidle", timeout=45_000)
                    verifier_page(page, appeler, constat)
                finally:
                    navigateur.close()
    finally:
        if serveur:
            serveur.terminate()
            serveur.wait(timeout=10)

    for p in constat.verifies:
        print(f"  ✔ {p}")
    if constat.manquements:
        print()
        for nom, detail in constat.manquements:
            print(f"  ✘ {nom}\n      {detail}")
        print(f"\n{len(constat.manquements)} promesse(s) non tenue(s) "
              f"sur {len(constat.verifies) + len(constat.manquements)} vérifiée(s).")
        return 1 if args.strict else 0

    print(f"\nLes {len(constat.verifies)} promesses de l'interface sont tenues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
