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

Quatre précautions
------------------
- **La confirmation prime sur la trouvaille.** Un domaine mal attribué ferait
  entrer les biens d'autrui sous le nom d'une agence, et la règle de sortie
  effacerait ensuite de vraies annonces en croyant avoir visité sa cible. Le
  seuil est strict, et les rejets sont comptés pour qu'on puisse le juger.
- **Le passage est borné et tourne.** Vingt-six mille agences ne se sondent pas
  d'un coup : on en prend un lot par passage, les jamais essayées d'abord, puis
  les plus anciennement essayées — la même rotation que partout ailleurs, et
  pour la même raison.
- **On publie en chemin, pas seulement à la fin.** Un passage qui n'écrit qu'au
  dernier tour perd tout quand il est interrompu — et un sondage réseau borné à
  quarante-cinq minutes l'est presque toujours. Le journal de rotation
  disparaissait alors avec le reste, si bien que le passage suivant reprenait
  les mêmes premières agences : le script a tourné toutes les nuits sans jamais
  produire une ligne. On écrit donc tous les PAR_PUBLICATION sondages, et l'on
  s'arrête de soi-même avant le couperet.
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

# Tous les combien on verse le travail sur le disque. Assez souvent pour qu'une
# interruption ne coûte qu'une poignée de sondages, assez rare pour ne pas
# réécrire le recensement — six méga-octets — à chaque agence.
PAR_PUBLICATION = 25
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


def publier(recensees: list[dict], trouvees: list[dict], journal: dict) -> int:
    """Verse les sites trouvés dans le recensement et écrit les deux fichiers.

    Appelée en cours de route autant qu'à la fin : c'est elle qui fait qu'un
    passage interrompu laisse quelque chose derrière lui. Le journal est écrit
    à chaque fois — il est petit et c'est lui qui porte la rotation ; le
    recensement seulement quand il a vraiment changé, car il pèse six méga.
    """
    par_cle = {_cle(t): t for t in trouvees}
    remplies = 0
    for agence in recensees:
        trouvee = par_cle.get(_cle(agence))
        if trouvee and not agence.get("site"):
            agence["site"] = trouvee["site"]
            agence["source"] = "registre+domaine"
            remplies += 1
    if remplies:
        _ecrire(RECENSEMENT, recensees)
    _ecrire(JOURNAL, journal)
    return remplies


def main() -> None:
    parametres = argparse.ArgumentParser(description=__doc__)
    parametres.add_argument("--lot", type=int, default=200,
                            help="agences cherchées dans ce passage")
    parametres.add_argument("--delai", type=float, default=0.5,
                            help="secondes entre deux requêtes")
    parametres.add_argument("--minutes", type=float, default=35,
                            help="budget de temps total du passage")
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

    # On REMPLIT le champ manquant sur l'entrée du registre, au lieu d'ajouter
    # une liste de plus. La découverte reprend déjà toute agence recensée
    # « munie d'un site » : rien d'autre à brancher, et le sondage habituel
    # décidera si le site est exploitable. Un dispositif de moins à tenir.
    trouvees, aujourd_hui = [], date.today().isoformat()
    fin = time.monotonic() + args.minutes * 60
    remplies = cherchees = confirmes = 0
    for rang, agence in enumerate(lot, 1):
        if time.monotonic() > fin:
            print(f"  budget de temps atteint après {rang - 1} agence(s) — "
                  f"la suite au prochain passage.")
            break
        # Marquée AVANT le sondage : une agence dont le domaine met quinze
        # secondes à ne pas répondre doit compter comme essayée, sinon la
        # rotation repasserait éternellement sur les mêmes lenteurs.
        journal[_cle(agence)] = aujourd_hui
        cherchees = rang
        site = chercher_le_site(agence, args.delai)
        if site:
            trouvees.append(site)
            confirmes += 1
            print(f"  [{rang}/{len(lot)}] {agence['nom'][:40]} → {site['site']}")
        if rang % PAR_PUBLICATION == 0 and not args.simuler:
            remplies += publier(recensees, trouvees, journal)
            trouvees = []          # déjà versées dans le recensement

    taux = 100 * confirmes / cherchees if cherchees else 0
    print(f"\n{confirmes} site(s) confirmé(s) sur {cherchees} cherchés ({taux:.0f} %)")
    if args.simuler:
        print("Simulation : rien n'a été écrit.")
        return

    remplies += publier(recensees, trouvees, journal)
    print(f"{remplies} entrée(s) du recensement complétée(s) — la découverte "
          f"les sondera au prochain passage.")


if __name__ == "__main__":
    main()
