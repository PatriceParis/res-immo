"""Laisse une trace du passage, même quand il n'a rien changé.

Pourquoi ce script existe
-------------------------
Le journal git est le seul signal de surveillance des tâches programmées :
un commit du robot qui manque à l'appel vaut alerte. Encore faut-il que
l'absence VEUILLE dire quelque chose.

Or trois passages sur quatre ne committaient que s'ils avaient trouvé du
neuf. Un passage qui n'a rien trouvé et un passage qui a planté laissaient
donc exactement la même trace — aucune. Le 17 août, `mandataires.yml` n'a
rien poussé à 15 h ; deux points d'étape plus tard, la cause était toujours
indécidable, non par manque de journaux mais parce que le silence était
ambigu par construction.

`collecte.yml` avait déjà rencontré et réglé cela pour son propre compte
(voir `data/dernier_passage.json` et le commentaire qui l'accompagne). Ce
script généralise le remède aux autres passages : chacun écrit son propre
fichier, ce qui suffit à garantir un commit par exécution — et rend donc
l'absence de commit enfin lisible.

Un fichier par passage, et non une entrée dans un fichier commun : deux
passages sérialisés par le même verrou peuvent tout de même se replacer l'un
après l'autre sur la version distante, et un fichier partagé se ferait alors
écraser. Séparés, ils ne peuvent pas se marcher dessus.

Usage :
    python scripts/marquer_passage.py mandataires
    python scripts/marquer_passage.py liens annonces=2407 retires=3
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def chemin_du_passage(nom: str) -> Path:
    """Un nom de passage ne doit pas pouvoir désigner un autre fichier."""
    propre = re.sub(r"[^a-z0-9_]+", "", nom.lower())
    if not propre:
        raise SystemExit("Nom de passage vide après nettoyage.")
    return RACINE / "data" / f"dernier_passage_{propre}.json"


def fichiers_touches() -> list[str]:
    """Ce que le passage a réellement modifié — vide veut dire « rien trouvé »,
    et c'est une information, pas un silence."""
    try:
        vus = subprocess.run(["git", "status", "--porcelain", "--", "data/"],
                             cwd=RACINE, capture_output=True, text=True,
                             timeout=60).stdout.split("\n")
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted(ligne[3:].strip() for ligne in vus
                  if ligne.strip() and "dernier_passage_" not in ligne)


def marquer(nom: str, precisions: dict) -> Path:
    chemin = chemin_du_passage(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({
        "passage": nom,
        "quand": datetime.datetime.now(datetime.timezone.utc)
                 .replace(microsecond=0).isoformat(),
        "fichiers_modifies": fichiers_touches(),
        **precisions,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return chemin


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    precisions = {}
    for argument in sys.argv[2:]:
        cle, _, valeur = argument.partition("=")
        precisions[cle] = int(valeur) if valeur.lstrip("-").isdigit() else valeur
    chemin = marquer(sys.argv[1], precisions)
    print(f"Passage marqué : {chemin.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
