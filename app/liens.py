"""Un lien d'annonce mort est une promesse morte — et rien ne le voyait.

Le cas qui a tout déclenché : une maison de Saint-Bérain-sur-Dheune vendue
chez IAD, son lien redirigé, et sa fiche toujours servie chez nous. La règle
de sortie ne pouvait rien y faire : elle s'abstient sur les cibles tronquées,
et un département de six cents annonces parcouru cinquante par cinquante est
tronqué À CHAQUE passage. Un bien vendu d'un gros département ne serait donc
JAMAIS parti tout seul — l'abstention, correcte pour protéger les vivants,
immortalisait les morts.

Ce module juge un lien à partir de ce que le réseau a répondu ; il ne fait
aucun appel lui-même (scripts/verifier_liens.py s'en charge). Trois verdicts :

    vivant   la page répond, au même endroit, sans annoncer la vente
    vendu    la page répond mais dit « vendu » ou « sous compromis »
    mort     erreur HTTP, ou redirection vers une AUTRE page — le sort le
             plus courant d'une annonce retirée : renvoyer vers la liste

Une seule constatation ne suffit pas : un site peut tousser, une maintenance
peut répondre 404 une heure. C'est la philosophie d'ABSENCES_TOLEREES,
appliquée aux liens : deux constats, à deux passages distincts, avant de
retirer. Et un lien revenu vivant efface tout — le doute profite à l'annonce.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .qualite import est_vendu

# Deux constats de mort, à deux passages distincts, avant le retrait.
CONSTATS_REQUIS = 2


def _chemin(url: str) -> str:
    morceaux = urlparse(url or "")
    return (morceaux.netloc.lower().removeprefix("www.")
            + (morceaux.path or "/").rstrip("/"))


def verdict(statut: int, url_demandee: str, url_finale: str,
            texte: str) -> tuple[str, str]:
    """(état, motif) pour une réponse observée.

    La redirection est jugée sur le CHEMIN : passer de http à https ou gagner
    une barre finale n'est pas déménager. Atterrir sur la page de recherche,
    si — c'est le sort le plus courant d'une annonce retirée.
    """
    if statut >= 400:
        return "mort", f"HTTP {statut}"
    if url_finale and _chemin(url_finale) != _chemin(url_demandee):
        return "mort", f"redirigé vers {url_finale[:90]}"
    if est_vendu({"texte": texte or ""}):
        return "vendu", "la page annonce la vente"
    return "vivant", ""


def noter(journal: dict, url: str, etat: str, jour: str, motif: str) -> None:
    """Reporte un constat dans le journal des liens morts.

    Un lien revenu vivant est INNOCENTÉ entièrement : garder un demi-constat
    ferait qu'une vraie panne d'un jour, des mois plus tard, achèverait une
    annonce parfaitement en ligne.
    """
    if etat == "vivant":
        journal.pop(url, None)
        return
    constat = journal.get(url) or {"constats": 0}
    # Deux passages du même jour ne font qu'un constat : la mort se confirme
    # dans la durée, pas en rappuyant sur le même bouton.
    if constat.get("dernier") == jour:
        constat["motif"] = motif
        journal[url] = constat
        return
    journal[url] = {"constats": int(constat.get("constats", 0)) + 1,
                    "dernier": jour, "motif": motif}


def morts_confirmes(journal: dict, seuil: int = CONSTATS_REQUIS) -> set:
    return {url for url, constat in (journal or {}).items()
            if int(constat.get("constats", 0)) >= seuil}


def sans_liens_morts(annonces: list[dict], journal: dict,
                     seuil: int = CONSTATS_REQUIS) -> tuple[list[dict], int]:
    """Écarte les annonces au lien mort confirmé. (gardées, retirées)."""
    morts = morts_confirmes(journal, seuil)
    if not morts:
        return annonces, 0
    gardees = [a for a in annonces if a.get("url") not in morts]
    return gardees, len(annonces) - len(gardees)


def ordre_de_verification(annonces: list[dict], verifies: dict,
                          journal: dict) -> list[dict]:
    """Les suspects d'abord, puis les plus anciennement vérifiés.

    Sans la priorité aux suspects, le second constat attendrait un tour
    complet de rotation — huit jours pour confirmer une mort déjà vue une
    fois. Avec elle, un bien vendu sort en deux passages.
    """
    return sorted(
        (a for a in annonces if a.get("url")),
        key=lambda a: (a["url"] not in journal,
                       verifies.get(a["url"], ""), a["url"]))


def nettoyer(journal: dict, urls_du_fichier: set) -> dict:
    """Les entrées d'annonces déjà sorties du fichier n'ont plus d'objet."""
    return {url: constat for url, constat in (journal or {}).items()
            if url in urls_du_fichier}
