"""Mémoire des annonces d'une collecte à l'autre.

Sans mémoire, chaque collecte repart de zéro : impossible de dire ce qui est
nouveau, de repérer une baisse de prix, ni de savoir qu'une annonce a disparu
du site de l'agence. Or c'est précisément ce qu'on attend d'un outil de veille :
être prévenu, plutôt que de tout relire chaque semaine.

L'historique ne peut pas vivre dans la base : elle est recréée à chaque
exécution (et remise à zéro à chaque démarrage sur l'hébergement). Il vit donc
dans le fichier exporté `data/annonces_reel.json`, qui est versionné — c'est
lui qui traverse le temps.

Trois informations sont conservées pour chaque bien :

    vue_le          première fois qu'on a vu cette annonce
    revue_le        dernière collecte où elle était encore en ligne
    prix_precedent  prix d'avant la dernière baisse (et `prix_baisse_le`)

Et une règle de sortie : une annonce que l'agence a retirée disparaît à son
tour — mais seulement si son agence a bien été visitée, sinon une collecte
écourtée ferait disparaître des biens parfaitement valides.
"""

from __future__ import annotations

# Une annonce absente de la dernière collecte de SON agence est considérée
# retirée. On tolère une absence (page en erreur, site momentanément lent) :
# c'est la deuxième qui l'élimine.
ABSENCES_TOLEREES = 1


def _index(annonces: list[dict]) -> dict:
    return {a["id"]: a for a in annonces or [] if a.get("id")}


def fusionner(precedentes: list[dict], nouvelles: list[dict],
              agences_visitees: set | None = None, aujourd_hui: str = "") -> list[dict]:
    """Reporte l'historique des annonces précédentes sur la collecte du jour.

    `agences_visitees` : noms des agences réellement parcourues cette fois. Les
    biens des autres agences sont conservés tels quels — ne pas les avoir revus
    ne prouve rien, la collecte s'est simplement arrêtée avant elles.
    """
    avant = _index(precedentes)
    gardees: list[dict] = []

    for bien in nouvelles:
        ancien = avant.get(bien.get("id"))
        enrichi = dict(bien)
        enrichi["revue_le"] = aujourd_hui
        enrichi["absences"] = 0
        if ancien is None:
            enrichi["vue_le"] = aujourd_hui          # annonce inédite
        else:
            enrichi["vue_le"] = ancien.get("vue_le") or aujourd_hui
            # Baisse de prix : le signal d'achat le plus parlant, et celui
            # qu'aucun portail n'affiche clairement.
            ancien_prix, nouveau_prix = ancien.get("prix"), bien.get("prix")
            if ancien_prix and nouveau_prix and nouveau_prix < ancien_prix:
                enrichi["prix_precedent"] = ancien_prix
                enrichi["prix_baisse_le"] = aujourd_hui
            elif ancien.get("prix_precedent") and nouveau_prix == ancien.get("prix"):
                enrichi["prix_precedent"] = ancien["prix_precedent"]
                enrichi["prix_baisse_le"] = ancien.get("prix_baisse_le")
        gardees.append(enrichi)

    vus = {b.get("id") for b in nouvelles}
    for identifiant, ancien in avant.items():
        if identifiant in vus:
            continue
        # Agence non visitée cette fois : on n'a rien appris, on conserve.
        if agences_visitees is not None and ancien.get("agence") not in agences_visitees:
            gardees.append(ancien)
            continue
        absences = int(ancien.get("absences") or 0) + 1
        if absences > ABSENCES_TOLEREES:
            continue                                  # retirée par l'agence
        garde = dict(ancien)
        garde["absences"] = absences
        gardees.append(garde)
    return gardees


def est_nouveau(bien: dict, aujourd_hui: str, jours: int = 10) -> bool:
    """Vrai si l'annonce est apparue récemment (comparaison de dates ISO)."""
    vue = bien.get("vue_le")
    if not vue or not aujourd_hui:
        return False
    from datetime import date
    try:
        d1, d2 = date.fromisoformat(vue), date.fromisoformat(aujourd_hui)
    except ValueError:
        return False
    return 0 <= (d2 - d1).days <= jours
