"""Client de l'API Géorisques (www.georisques.gouv.fr) — données officielles
de l'État sur les risques naturels et technologiques d'une adresse.

L'appel est facultatif : sans réseau (ou si l'API évolue), l'application
fonctionne avec les risques déjà stockés en base. Voir
scripts/enrichir_risques.py pour lancer l'enrichissement.
"""

from __future__ import annotations

import requests

URL_RAPPORT = "https://www.georisques.gouv.fr/api/v1/resultats_rapport_risque"


def _present(noeud) -> bool:
    """L'API signale chaque risque par un objet {"present": true/false}."""
    return bool(isinstance(noeud, dict) and noeud.get("present"))


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

    # Niveau argile : l'API expose le retrait-gonflement des argiles comme un
    # risque présent/absent ; on le traduit en niveau moyen (1) par prudence.
    argile_present = any(
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
        "argile": 1 if argile_present else 0,
        "feu_foret_commune": _present(naturels.get("feuForet")),
        "seisme_commune": _present(naturels.get("seisme")),
        "radon_commune": _present(naturels.get("radon")),
        "seveso_km": None,  # non fourni par ce point d'accès
        "icpe_commune": _present(technologiques.get("icpe")),
        "portee": "commune",
        "source": "georisques",
    }
