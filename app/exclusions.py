"""Les agences qui ont demandé qu'on ne les reprenne plus.

Les mentions légales promettent à toute agence le retrait de ses annonces
« sans discussion et sans délai », et l'ajout de son site à une liste
d'exclusion « pour que la collecte n'y revienne pas ». Jusqu'au 1er octobre,
cette liste n'existait pas : la promesse aurait été tenue à la main, une fois,
et la découverte mensuelle aurait rebranché le site au passage suivant.

La liste vit dans data/agences_exclues.json, versionnée comme le catalogue —
c'est elle qui traverse le temps. Chaque entrée dit QUI, DEPUIS QUAND et
POURQUOI :

    [{"domaine": "agence-exemple.fr", "depuis": "2026-10-01",
      "motif": "demande de l'agence"}]

Elle est consultée partout où une agence peut entrer ou rester :

- par les trois collecteurs, qui ne visitent plus son site ;
- par la découverte, qui ne la rebranche jamais ;
- par l'export, qui retire ses biens du fichier publié ;
- par le chargement, qui ne sert plus ceux qui y seraient encore.

Une seule définition de « ce site est-il exclu ? » pour les quatre usages :
deux copies d'une règle finissent toujours par diverger, et ce projet l'a déjà
payé plusieurs fois (voir app/historique.py).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .historique import cle_agence

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "agences_exclues.json"


def normaliser(url_ou_domaine: str) -> str:
    """« https://www.Agence.fr/x », « www.agence.fr » ou « agence.fr » → « agence.fr »."""
    brut = (url_ou_domaine or "").strip()
    if not brut:
        return ""
    if "//" not in brut:
        brut = "https://" + brut
    return cle_agence(brut)


def lire(chemin: Path | None = None) -> list[dict]:
    """Les entrées de la liste. Absente ou illisible : aucune exclusion — et
    non une erreur, car la collecte ne doit pas s'arrêter pour un fichier qui
    manque. Mais une liste qui manque ne retire rien : voir le test."""
    try:
        entrees = json.loads((chemin or FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in entrees if isinstance(e, dict) and e.get("domaine")]


def domaines_exclus(chemin: Path | None = None) -> set[str]:
    return {normaliser(e["domaine"]) for e in lire(chemin)} - {""}


def est_exclu(url_ou_domaine: str, exclus: set[str] | None = None) -> bool:
    """Vrai si le site est exclu, lui ou l'un de ses domaines parents : exclure
    « reseau.fr » exclut « agence.reseau.fr ». L'inverse n'est pas vrai —
    une agence qui part n'emporte pas son réseau."""
    if exclus is None:
        exclus = domaines_exclus()
    if not exclus:
        return False
    hote = normaliser(url_ou_domaine)
    while hote:
        if hote in exclus:
            return True
        hote = hote.partition(".")[2] if "." in hote else ""
    return False


def site_du_bien(bien: dict) -> str:
    """Le site d'où vient un bien : celui de son agence, sinon celui de sa page."""
    return bien.get("agence_url") or bien.get("url") or ""


def sans_exclues(biens: list[dict], exclus: set[str] | None = None) -> tuple[list[dict], int]:
    """Les biens dont le site n'est pas exclu, et le nombre retiré."""
    if exclus is None:
        exclus = domaines_exclus()
    if not exclus:
        return list(biens), 0
    gardes = [b for b in biens if not est_exclu(site_du_bien(b), exclus)]
    return gardes, len(biens) - len(gardes)


def exclure(domaine: str, motif: str = "demande de l'agence",
            chemin: Path | None = None, aujourd_hui: str = "") -> bool:
    """Ajoute un site à la liste. Renvoie False s'il y était déjà."""
    chemin = chemin or FICHIER
    propre = normaliser(domaine)
    if not propre:
        raise ValueError(f"domaine illisible : {domaine!r}")
    entrees = lire(chemin)
    if any(normaliser(e["domaine"]) == propre for e in entrees):
        return False
    entrees.append({"domaine": propre,
                    "depuis": aujourd_hui or date.today().isoformat(),
                    "motif": motif})
    entrees.sort(key=lambda e: e["domaine"])
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(entrees, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    return True


def retirer_du_catalogue(chemin_catalogue: Path, exclus: set[str]) -> int:
    """Retire du fichier publié les biens des sites exclus. Renvoie le nombre
    retiré. C'est ce qui rend le retrait immédiat : l'export suivant le
    referait, mais il n'a pas à être attendu."""
    biens = json.loads(chemin_catalogue.read_text(encoding="utf-8"))
    gardes, retires = sans_exclues(biens, exclus)
    if retires:
        chemin_catalogue.write_text(
            json.dumps(gardes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return retires
