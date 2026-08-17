"""Retrouve le site des agences que le registre nomme sans les adresser.

Le chaînon qui manquait
-----------------------
Le recensement connaît 26 452 agences du registre dans notre périmètre, et pas
une seule avec un site : SIRENE donne un nom, une commune et un SIRET, jamais
d'adresse en ligne. Ces agences étaient donc parfaitement connues et
parfaitement injoignables — CBF Conseils, qui vendait une maison au Creusot,
était dans nos données depuis des semaines.

OpenStreetMap, la seule source qui donnait des sites, n'en recense que 577 sur
30 432 : c'est ce que des contributeurs ont bien voulu y déclarer. Chercher là
seulement, c'était conclure de ce qu'on n'avait pas cherché.

Ce que fait ce script
---------------------
Pour chaque agence du registre encore sans site : fabriquer les adresses
plausibles de son nom (app/domaines.py), les sonder, et ne retenir que celles
dont la page CONFIRME l'agence — nom distinctif plus commune ou SIRET. Les
adresses confirmées rejoignent data/agences_candidates.json, où le sondage de
la découverte décide ensuite si le site est exploitable.

Ce script ne branche donc rien tout seul : il remplit l'entonnoir existant par
le haut. C'est voulu — un domaine confirmé n'est pas encore un site collectable.

Trois précautions
-----------------
- **La confirmation prime sur la trouvaille.** Un domaine mal attribué ferait
  entrer les biens d'autrui sous le nom d'une agence, et la règle de sortie
  effacerait ensuite de vraies annonces en croyant avoir visité sa cible. Le
  seuil est strict, et les rejets sont comptés pour qu'on puisse le juger.
- **Le passage est borné et tourne.** Vingt-six mille agences ne se sondent pas
  d'un coup : on en prend un lot par passage, les jamais essayées d'abord, puis
  les plus anciennement essayées — la même rotation que partout ailleurs, et
  pour la même raison.
- **On frappe doucement.** Une seule requête par adresse, un délai entre
  chacune, et l'on s'arrête à la première confirmée pour une agence donnée.

Usage :
    python scripts/resoudre_sites.py                 # un lot
    python scripts/resoudre_sites.py --lot 500       # plus large
    python scripts/resoudre_sites.py --departements 71,21
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

try:
    import requests
except ImportError:                                    # pragma: no cover
    print("Le module 'requests' est nécessaire :  pip install requests")
    sys.exit(1)

from app import decouverte, domaines, sirene  # noqa: E402
from app.chargement import DEPARTEMENTS_CIBLES  # noqa: E402

RECENSEMENT = RACINE / "data" / "agences_recensees.json"
JOURNAL = RACINE / "data" / "sites_cherches.json"
ENTETES = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/140.0.0.0 Safari/537.36"),
    "Accept-Language": "fr-FR,fr;q=0.9",
}


def _charger(chemin: Path, defaut):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin: Path, donnees) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")


def a_chercher(recensees: list[dict], departements: set | None) -> list[dict]:
    """Les agences du registre qui méritent qu'on cherche leur site.

    On écarte d'emblée ce qu'on ne collecterait pas : constructeurs de maisons
    neuves et syndics purs. Inutile de frapper à leur porte pour les refuser
    ensuite.
    """
    voulus = departements or DEPARTEMENTS_CIBLES
    gardees = []
    for agence in recensees:
        if agence.get("source") != "registre" or agence.get("site"):
            continue
        if agence.get("departement") not in voulus:
            continue
        nom = agence.get("nom", "")
        if decouverte.est_constructeur(nom) or sirene.HORS_CIBLE.search(nom):
            continue
        if not domaines.domaines_plausibles(nom):
            continue
        gardees.append(agence)
    return gardees


def ordre_de_recherche(agences: list[dict], journal: dict) -> list[dict]:
    """Les jamais essayées d'abord, puis les plus anciennement essayées.

    Sans cette rotation, un lot borné reprendrait éternellement les mêmes
    premières agences et les dernières ne seraient jamais cherchées. La leçon
    a déjà coûté cher trois fois cette semaine.
    """
    return sorted(agences, key=lambda a: (journal.get(_cle(a), ""), _cle(a)))


def _cle(agence: dict) -> str:
    return agence.get("siret") or f"{agence.get('nom','')}|{agence.get('commune','')}"


def chercher_le_site(agence: dict, delai: float) -> dict | None:
    """Sonde les adresses plausibles ; renvoie la première CONFIRMÉE.

    « Confirmée » ne veut pas dire « joignable » : une page qui répond mais ne
    prouve pas qu'elle est celle de cette agence est écartée. Voir
    app/domaines.est_le_bon_site.
    """
    for candidat in domaines.domaines_plausibles(agence.get("nom", "")):
        for schema in ("https://", "http://"):
            url = schema + candidat
            try:
                reponse = requests.get(url, headers=ENTETES, timeout=15,
                                       allow_redirects=True)
            except Exception:
                continue
            finally:
                time.sleep(delai)
            if reponse.status_code >= 400 or not reponse.text:
                continue
            if domaines.est_le_bon_site(agence, reponse.text):
                return {"nom": agence["nom"], "site": f"https://{candidat}",
                        "zone": f"registre {agence.get('departement','')}",
                        "departement": agence.get("departement"),
                        "commune": agence.get("commune"),
                        "siret": agence.get("siret"),
                        "source": "registre+domaine"}
            break        # le domaine répond mais n'est pas elle : inutile d'insister
    return None


def main() -> None:
    parametres = argparse.ArgumentParser(description=__doc__)
    parametres.add_argument("--lot", type=int, default=200,
                            help="agences cherchées dans ce passage")
    parametres.add_argument("--delai", type=float, default=0.5,
                            help="secondes entre deux requêtes")
    parametres.add_argument("--departements",
                            help="codes séparés par des virgules")
    parametres.add_argument("--simuler", action="store_true",
                            help="n'écrit rien, dit seulement ce qui serait fait")
    args = parametres.parse_args()

    voulus = ({d.strip() for d in args.departements.split(",") if d.strip()}
              if args.departements else None)
    recensees = _charger(RECENSEMENT, [])
    journal = _charger(JOURNAL, {})
    candidates = a_chercher(recensees, voulus)
    print(f"{len(candidates)} agence(s) du registre sans site connu")

    lot = ordre_de_recherche(candidates, journal)[:args.lot]
    jamais = sum(1 for a in lot if _cle(a) not in journal)
    print(f"  ce passage en cherche {len(lot)}, dont {jamais} jamais essayée(s)")

    trouvees, aujourd_hui = [], date.today().isoformat()
    for rang, agence in enumerate(lot, 1):
        journal[_cle(agence)] = aujourd_hui
        site = chercher_le_site(agence, args.delai)
        if site:
            trouvees.append(site)
            print(f"  [{rang}/{len(lot)}] {agence['nom'][:40]} → {site['site']}")

    taux = 100 * len(trouvees) / len(lot) if lot else 0
    print(f"\n{len(trouvees)} site(s) confirmé(s) sur {len(lot)} cherchés ({taux:.0f} %)")
    if args.simuler:
        print("Simulation : rien n'a été écrit.")
        return

    # On REMPLIT le champ manquant sur l'entrée du registre, au lieu d'ajouter
    # une liste de plus. La découverte reprend déjà toute agence recensée
    # « munie d'un site » : rien d'autre à brancher, et le sondage habituel
    # décidera si le site est exploitable. Un dispositif de moins à tenir.
    par_cle = {_cle(t): t for t in trouvees}
    remplies = 0
    for agence in recensees:
        trouvee = par_cle.get(_cle(agence))
        if trouvee and not agence.get("site"):
            agence["site"] = trouvee["site"]
            agence["source"] = "registre+domaine"
            remplies += 1
    _ecrire(RECENSEMENT, recensees)
    _ecrire(JOURNAL, journal)
    print(f"{remplies} entrée(s) du recensement complétée(s) — la découverte "
          f"les sondera au prochain passage.")


if __name__ == "__main__":
    main()
