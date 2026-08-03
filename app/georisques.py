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

    return {
        "inondation": _present(naturels.get("inondation")),
        "argile": 1 if argile_present else 0,
        "feu_foret": _present(naturels.get("feuForet")),
        "seisme": _present(naturels.get("seisme")),
        "radon": _present(naturels.get("radon")),
        "seveso_km": None,  # non fourni par ce point d'accès
        "icpe": _present(technologiques.get("icpe")),
        "source": "georisques",
    }
