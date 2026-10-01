"""L'identité sous laquelle nos robots se présentent aux sites qu'ils visitent.

Jusqu'au 1er octobre 2026, onze scripts se faisaient passer pour un navigateur
Chrome, chacun avec sa propre copie de la chaîne. docs/LEGAL.md le justifiait
par un usage de « veille personnelle » qui n'était plus la réalité d'un site
public. Un robot qui dit son nom, avec un lien vers la page qui explique ce
qu'il fait et comment l'arrêter, est la posture loyale — et la seule qu'un
juge regarde quand une agence se plaint d'avoir été lue.

Le changement n'a pas été fait à l'aveugle. Mesuré le 1er octobre sur les
292 sites de la configuration et les trois réseaux de mandataires, depuis
GitHub Actions (scripts/sonder_user_agent.py, .github/workflows/sonder-ua.yml) :
289 sites acceptent le navigateur, 289 acceptent le robot déclaré, et UN seul
refuse le second en acceptant le premier. On respecte ce refus : il ne sera
pas visité sous un autre nom. La mesure porte sur la page d'accueil de chaque
site, une requête par identité ; un pare-feu qui compterait les requêtes
pourrait réagir autrement sur la durée, et c'est le catalogue des jours
suivants qui le dira.

Une seule définition, importée partout : la chaîne vivait en onze copies, et
deux copies d'une règle finissent toujours par diverger.
"""

from __future__ import annotations

import os

from . import seo

NOM = "RefugeImmoBot"
VERSION = "1.0"

# La page qui dit ce que fait le robot, comment le bloquer et comment obtenir
# un retrait. Son adresse figure dans l'identité, comme chez les moteurs de
# recherche : l'administrateur qui voit passer le robot sait où lire.
PAGE = f"{seo.SITE}{seo.URL_ROBOT}"

# Surchargeable par l'environnement, comme avant — pour un essai, jamais pour
# se déguiser : la valeur par défaut est celle que les sites voient.
USER_AGENT = os.environ.get("REFUGE_USER_AGENT", f"{NOM}/{VERSION} (+{PAGE})")

# Ce qu'un client français envoie aussi : la langue voulue.
ENTETES = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}
