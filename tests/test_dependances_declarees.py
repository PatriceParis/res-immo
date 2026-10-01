"""Tout ce que le code importe doit être déclaré dans les requirements.

Le 1er octobre, la mesure a donné ceci : le workflow « Vérification » était
ROUGE à chaque push depuis le 11 août — cinquante-huit runs consécutifs. La
cause courante : six fichiers de tests importaient PyYAML, qui n'était pas
dans requirements-local.txt. La collecte de pytest s'interrompait avant
d'exécuter un seul test, les deux audits suivants étaient sautés, et personne
n'a lu le journal. Les tests passaient sur chaque machine de développement,
où PyYAML se trouvait installé pour d'autres raisons — c'est précisément ce
qui rendait le trou invisible d'ici.

Ce test ne lit pas une liste écrite à la main : il parcourt les imports de
`app/` et de `tests/`, demande à l'environnement installé quelle distribution
fournit chaque module, et vérifie qu'elle est déclarée — directement ou comme
dépendance d'une déclarée (starlette vient avec fastapi). Un import sous
`try:` est optionnel par construction et n'est pas exigé.
"""

from __future__ import annotations

import ast
import re
import sys
from importlib import metadata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
REQUIREMENTS = (RACINE / "requirements.txt", RACINE / "requirements-local.txt")

# Les paquets du dépôt lui-même, et les scripts chargés par chemin.
LOCAUX = {"app", "scripts", "scraper", "tests", "refuge_scraper"} | {
    p.stem for p in (RACINE / "scripts").glob("*.py")}


def _imports(fichier: Path) -> set[str]:
    """Modules de premier niveau importés hors d'un bloc try."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    optionnels: set[int] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Try):
            optionnels |= {id(n) for n in ast.walk(noeud)}
    modules = set()
    for noeud in ast.walk(arbre):
        if id(noeud) in optionnels:
            continue
        if isinstance(noeud, ast.Import):
            modules |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module and noeud.level == 0:
            modules.add(noeud.module.split(".")[0])
    return modules


def _declarees() -> set[str]:
    """Distributions nommées dans les requirements, normalisées (pep 503)."""
    noms = set()
    for fichier in REQUIREMENTS:
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            ligne = ligne.split("#", 1)[0].strip()
            if not ligne or ligne.startswith("-"):
                continue
            noms.add(_normaliser(re.split(r"[<>=!~;\[\s]", ligne, 1)[0]))
    return noms


def _normaliser(nom: str) -> str:
    return re.sub(r"[-_.]+", "-", nom).lower()


def _fermeture(declarees: set[str], profondeur: int = 3) -> set[str]:
    """Les déclarées et ce qu'elles entraînent, sur quelques niveaux."""
    vues, frontiere = set(declarees), set(declarees)
    for _ in range(profondeur):
        suivantes = set()
        for dist in frontiere:
            try:
                exigences = metadata.requires(dist) or []
            except metadata.PackageNotFoundError:
                continue
            for exigence in exigences:
                if "extra ==" in exigence:
                    continue            # un extra non demandé n'est pas installé
                suivantes.add(_normaliser(re.split(r"[<>=!~;\[\s(]", exigence, 1)[0]))
        frontiere = suivantes - vues
        vues |= suivantes
    return vues


def test_tout_import_tiers_est_declare_dans_les_requirements():
    fournisseurs = metadata.packages_distributions()
    couvertes = _fermeture(_declarees())
    stdlib = set(sys.stdlib_module_names)
    manquants: dict[str, set[str]] = {}
    for dossier in ("app", "tests"):
        for fichier in sorted((RACINE / dossier).glob("*.py")):
            for module in _imports(fichier):
                if module in stdlib or module in LOCAUX:
                    continue
                distributions = {_normaliser(d) for d in fournisseurs.get(module, [])}
                if not distributions:
                    distributions = {f"(non installé : {module})"}
                if not distributions & couvertes:
                    manquants.setdefault(f"{module} ← {', '.join(sorted(distributions))}",
                                         set()).add(fichier.name)
    assert not manquants, (
        "importés mais déclarés dans aucun requirements : "
        + "; ".join(f"{m} [{', '.join(sorted(f))}]" for m, f in sorted(manquants.items())))
