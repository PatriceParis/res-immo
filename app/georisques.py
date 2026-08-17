"""Client de l'API Géorisques (www.georisques.gouv.fr) — données officielles
de l'État sur les risques naturels et technologiques d'une adresse.

L'appel est facultatif : sans réseau (ou si l'API évolue), l'application
fonctionne avec les risques déjà stockés en base. Voir
scripts/enrichir_risques.py pour lancer l'enrichissement.
"""

from __future__ import annotations

import requests

URL_RAPPORT = "https://www.georisques.gouv.fr/api/v1/resultats_rapport_risque"

# Point d'accès DÉDIÉ au retrait-gonflement des argiles. Le rapport général
# ci-dessus ne dit que « documenté sur la commune », et le client traduisait ce
# booléen en « niveau moyen par prudence » : mesuré sur le catalogue, 1 298
# biens sur 1 311 portaient exactement la même valeur. Un critère qui vaut 1
# pour 99 % des biens ne trie personne, et la branche « niveau élevé » du
# barème — avec l'alerte qui en dépend — n'a jamais été atteinte.
#
# Celui-ci rend le NIVEAU d'exposition, c'est-à-dire la carte du BRGM, révisée
# au 1er juillet 2026 pour intégrer les projections climatiques à 2050 : des
# milliers de communes y passent de l'orange au rouge.
URL_ARGILE = "https://georisques.gouv.fr/api/v1/rga"

# Les intitulés de la carte, du plus grave au plus anodin. L'ordre compte :
# « très faible » contient « faible », et serait lu comme lui si l'on
# cherchait les libellés du moins grave au plus grave.
_NIVEAUX_ARGILE = (
    (3, ("fort", "forte", "eleve", "elevee")),
    (0, ("tres faible", "nul", "nulle", "aucun", "aucune", "absent")),
    (2, ("moyen", "moyenne", "modere", "moderee")),
    (1, ("faible",)),
)


def _sans_accents(texte) -> str:
    import unicodedata
    brut = unicodedata.normalize("NFD", str(texte or ""))
    return brut.encode("ascii", "ignore").decode().lower().strip()


def niveau_argile(reponse) -> int | None:
    """0 à 3 selon l'exposition au retrait-gonflement, ou None si illisible.

    None, et surtout pas 0 : traduire l'ignorance en « aucun risque »
    rassurerait à tort sur des biens que personne n'a vérifiés. C'est la même
    faute que celle qu'on corrige ici, prise dans l'autre sens.

    Le parseur encaisse plusieurs écritures parce que la forme exacte de la
    réponse n'a pas pu être observée : cette session n'a pas de réseau, et une
    sonde ira relever la vraie. Mieux vaut accepter large et refuser ce qu'on
    ne comprend pas que deviner un niveau.
    """
    if isinstance(reponse, list):
        return niveau_argile(reponse[0]) if reponse else None
    if not isinstance(reponse, dict):
        return None
    for enveloppe in ("data", "results", "resultats"):
        if enveloppe in reponse:
            return niveau_argile(reponse[enveloppe])

    for cle in ("exposition", "niveauExposition", "niveau_exposition",
                "alea", "niveau"):
        texte = _sans_accents(reponse.get(cle))
        if texte:
            for niveau, libelles in _NIVEAUX_ARGILE:
                if any(mot in texte for mot in libelles):
                    return niveau
    for cle in ("codeExposition", "code_exposition", "codeAlea"):
        code = reponse.get(cle)
        if code is not None and str(code).strip() in ("0", "1", "2", "3"):
            return int(str(code).strip())
    return None


def _present(noeud) -> bool:
    """L'API signale chaque risque par un objet {"present": true/false}."""
    return bool(isinstance(noeud, dict) and noeud.get("present"))


def exposition_argile(lat: float, lon: float, timeout: int = 10) -> int | None:
    """Le NIVEAU d'exposition au retrait-gonflement pour un point (0 à 3).

    None si l'API est injoignable ou sa réponse illisible : l'appelant laisse
    alors le niveau inconnu plutôt que d'inventer un zéro rassurant.
    """
    try:
        reponse = requests.get(
            URL_ARGILE,
            params={"latlon": f"{lon},{lat}"},
            timeout=timeout,
            headers={"User-Agent": "RefugeImmo-POC/0.1"},
        )
        reponse.raise_for_status()
        return niveau_argile(reponse.json())
    except (requests.RequestException, ValueError):
        return None


def risques_pour(lat: float, lon: float, timeout: int = 10) -> dict | None:
    """Interroge Géorisques pour un point donné.

    Renvoie un dictionnaire au format interne de l'application, ou None si
    l'API est injoignable (l'appelant garde alors les données existantes).
    """
    try:
        reponse = requests.get(
            URL_RAPPORT,
            params={"latlon": f"{lon},{lat}"},
            timeout=timeout,
            headers={"User-Agent": "RefugeImmo-POC/0.1"},
        )
        reponse.raise_for_status()
        data = reponse.json()
    except (requests.RequestException, ValueError):
        return None

    naturels = data.get("risquesNaturels") or {}
    technologiques = data.get("risquesTechnologiques") or {}

    # Ce rapport ne dit que « documenté sur la commune » : on ne l'utilise plus
    # comme un niveau. Le niveau vient de `niveau_argile`, qui interroge le
    # point d'accès dédié — voir URL_ARGILE. Sans lui, `argile` reste None, et
    # le barème n'en tient alors aucun compte, ni en bien ni en mal.
    argile_documente = any(
        _present(naturels.get(cle))
        for cle in ("retraitGonflementsDesArgiles", "retraitGonflementArgile", "argiles")
    )

    # ATTENTION à la portée : ce point d'accès dit qu'un risque est **documenté
    # sur la commune**, pas que CE bien y est exposé. Mesuré sur nos annonces :
    # séisme et radon ressortent à 100 % (toute commune française a un zonage),
    # l'inondation à 80 % (presque toute commune a une rivière). Traiter ces
    # signaux comme une exposition du bien pénaliserait tout le monde à tort :
    # on les nomme donc « _commune » et on les utilise comme points de
    # vigilance à vérifier à l'adresse, pas comme une condamnation.
    return {
        "inondation_commune": _present(naturels.get("inondation")),
        "argile_commune": argile_documente,
        "argile": None,
        "feu_foret_commune": _present(naturels.get("feuForet")),
        "seisme_commune": _present(naturels.get("seisme")),
        "radon_commune": _present(naturels.get("radon")),
        "seveso_km": None,  # non fourni par ce point d'accès
        "icpe_commune": _present(technologiques.get("icpe")),
        "portee": "commune",
        "source": "georisques",
    }
