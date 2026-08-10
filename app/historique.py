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
tour — mais seulement si son SITE a bien été visité, sinon une collecte
écourtée ferait disparaître des biens parfaitement valides.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Une annonce absente de la dernière collecte de SON agence est considérée
# retirée. On tolère une absence (page en erreur, site momentanément lent) :
# c'est la deuxième qui l'élimine.
ABSENCES_TOLEREES = 1


def cle_agence(url: str) -> str:
    """Identifie une agence par son DOMAINE, jamais par son nom.

    « Century 21 » désigne douze sites distincts — Chalon, Compiègne, Amboise,
    Caen… La rotation de la collecte avait déjà appris cette leçon et s'indexe
    sur le domaine depuis. La règle de sortie ci-dessous, elle, comparait
    encore des noms : passer chez cinq Century 21 marquait les douze comme
    visitées, et les biens des sept autres étaient comptés absents « chez leur
    agence ». Cinquante et un ont ainsi été retirés du catalogue le 10 août
    alors que leurs pages étaient parfaitement en ligne.

    Une seule définition pour les deux usages, importée par le collecteur :
    deux copies de cette règle avaient déjà divergé une fois.
    """
    hote = urlparse(url or "").netloc.lower()
    return hote[4:] if hote.startswith("www.") else hote


def identite(bien: dict) -> str:
    """Ce qui désigne le site d'où vient un bien, pour savoir si l'on y est
    passé. Le domaine quand il est connu ; à défaut le nom de l'agence, pour
    les enregistrements antérieurs à `agence_url`."""
    return cle_agence(bien.get("agence_url")) or (bien.get("agence") or "")


def _index(annonces: list[dict]) -> dict:
    return {a["id"]: a for a in annonces or [] if a.get("id")}


def fusionner(precedentes: list[dict], nouvelles: list[dict],
              sites_visites: set | None = None, aujourd_hui: str = "") -> list[dict]:
    """Reporte l'historique des annonces précédentes sur la collecte du jour.

    `sites_visites` : les SITES réellement parcourus cette fois — voir
    `cle_agence`, un nom d'agence peut en couvrir douze. Les biens des autres
    sites sont conservés tels quels : ne pas les avoir revus ne prouve rien,
    la collecte s'est simplement arrêtée avant eux.
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
        # Site non visité cette fois : on n'a rien appris, on conserve.
        if sites_visites is not None and identite(ancien) not in sites_visites:
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
