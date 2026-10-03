"""Ce que le site nous permet de lire : robots.txt, interprété pour notre nom.

Jusqu'au 3 octobre 2026, seul le spider Scrapy — qui ne tourne pas en
production — honorait robots.txt (ROBOTSTXT_OBEY). Le collecteur Playwright,
celui que lance collecte.yml six fois par jour, ne le lisait pas : il ouvrait
sitemap.xml et les pages de biens sans regarder si le site les lui interdisait.
La page /robot promettait pourtant « il lit d'abord votre fichier robots.txt et
le respecte », et donnait les deux lignes qui l'arrêtent. Une promesse que le
code ne tenait pas — exactement ce que LEGAL.md s'était engagé à ne plus faire.

Ce module interprète un robots.txt pour notre nom (voir app/robot.py) selon
la convention : le groupe « RefugeImmoBot » s'il existe, sinon le groupe « * ».
Il ne fait aucun appel réseau lui-même : `lire` reçoit la fonction qui va
chercher le fichier, ce qui rend tout testable hors ligne.

Deux cas que la convention tranche et qu'on suit :
- robots.txt ABSENT (404) : tout est permis ;
- robots.txt REFUSÉ (401, 403) : rien n'est permis — un site qui ne nous laisse
  pas lire ses règles ne nous laisse rien lire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urljoin, urlparse

from . import robot

# Statuts pour lesquels la convention impose d'interpréter l'absence.
ABSENT = (404, 410)
REFUSE = (401, 403)


@dataclass
class Permission:
    """Les règles d'un site, lues une fois par passage."""

    parseur: robotparser.RobotFileParser
    statut: int | None = None          # None : fichier illisible (réseau)
    sitemaps: list[str] = field(default_factory=list)

    def autorise(self, url: str) -> bool:
        return self.parseur.can_fetch(robot.NOM, url)

    def tout_interdit(self, base: str) -> bool:
        """Vrai si le site nous ferme sa racine : on ne le visite pas du tout,
        et le déroulé doit le dire."""
        return not self.autorise(urljoin(base.rstrip("/") + "/", "/"))

    def delai(self) -> float | None:
        """Le Crawl-delay demandé, s'il y en a un — on ne va jamais plus vite."""
        valeur = self.parseur.crawl_delay(robot.NOM)
        return float(valeur) if valeur else None


def interpreter(texte: str | None, statut: int, base: str = "") -> Permission:
    """Les règles à partir du texte reçu et du statut HTTP qui l'accompagnait."""
    parseur = robotparser.RobotFileParser()
    if statut in REFUSE:
        parseur.disallow_all = True
    elif statut in ABSENT or statut >= 500 or texte is None:
        parseur.allow_all = True
    else:
        parseur.parse(texte.splitlines())
    sitemaps = list(parseur.site_maps() or []) if not (parseur.allow_all or parseur.disallow_all) else []
    return Permission(parseur, statut, [urljoin(base, s) for s in sitemaps])


def lire(base: str, chercher) -> Permission:
    """Lit <base>/robots.txt avec `chercher(url) -> (statut, texte)`.

    `chercher` doit se présenter sous notre nom et ne jamais lever : une
    panne de notre côté (statut 0) vaut « illisible », et on reste prudent
    sans être paranoïaque — tout permis, comme pour un fichier absent, car la
    convention ne connaît pas de « peut-être ».
    """
    hote = urlparse(base)
    racine = f"{hote.scheme}://{hote.netloc}"
    statut, texte = chercher(racine + "/robots.txt")
    if not statut:
        return interpreter(None, 0, racine)
    return interpreter(texte, statut, racine)
