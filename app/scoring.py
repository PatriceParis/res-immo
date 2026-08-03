"""Moteur de classification « résilience » des biens immobiliers.

Chaque annonce reçoit un score sur 100, réparti en 6 piliers :

    EAU          (20 pts)  puits/forage/source, récupération d'eau de pluie,
                           cours d'eau ou plan d'eau à proximité
    ABRI         (15 pts)  cave ou sous-sol, grange/dépendances, atelier/garage
    ÉNERGIE      (15 pts)  chauffage au bois, panneaux solaires, bonne isolation (DPE)
    ALIMENTATION (15 pts)  surface du terrain (potager, verger), serre
    RISQUES      (20 pts)  part de 20 puis retire des points : zone inondable,
                           sols argileux, site Seveso proche, centrale nucléaire
                           proche, feux de forêt
    SITUATION    (15 pts)  altitude, faible densité de population,
                           temps de route raisonnable depuis Paris

Les critères « équipements » sont détectés automatiquement dans le texte des
annonces (ex. : la mention d'une cave ou d'un puits dans la description).
Le barème complet est documenté dans docs/CRITERES.md.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Détection des équipements dans le texte des annonces
# ---------------------------------------------------------------------------

def normaliser(texte: str) -> str:
    """Minuscules et suppression des accents, pour une détection robuste."""
    texte = unicodedata.normalize("NFD", texte or "")
    texte = texte.encode("ascii", "ignore").decode("ascii")
    return texte.lower()


# Motifs recherchés dans le texte normalisé (sans accents, en minuscules).
MOTIFS = {
    "cave": r"\bcaves?\b|sous[- ]sols?",
    "puits": r"\bpuits\b|\bforages?\b|source captee|source sur (?:le|la)",
    "eau_proximite": (
        r"rivieres?|ruisseaux?|etangs?|\bmares?\b|\bmoulins?\b"
        r"|bord de l'eau|cours d'eau|\blavoirs?\b"
    ),
    "recuperation_pluie": (
        r"recuperation (?:d'|des? )?eaux?|recuperateurs? d'eau"
        r"|citernes?|cuves? de recuperation"
    ),
    "bois": (
        r"poeles?|cheminees?|inserts?|chaudieres? (?:a )?bois"
        r"|granules|bois de chauffage"
    ),
    "solaire": r"photovoltaiques?|panneaux? solaires?|energie solaire",
    "verger_potager": r"vergers?|potagers?|arbres? fruitiers?|\bfruitiers\b",
    "serre": r"\bserres?\b",
    "grange_dependance": (
        r"granges?|dependances?|appentis|ecuries?|etables?|hangars?"
    ),
    "atelier": r"ateliers?|garages?",
}

_MOTIFS_COMPILES = {cle: re.compile(motif) for cle, motif in MOTIFS.items()}


def extraire_criteres(titre: str, description: str) -> dict:
    """Détecte les équipements « résilience » mentionnés dans une annonce."""
    texte = normaliser(f"{titre} {description}")
    return {cle: bool(motif.search(texte)) for cle, motif in _MOTIFS_COMPILES.items()}


# ---------------------------------------------------------------------------
# Barème
# ---------------------------------------------------------------------------

def _pilier_eau(f: dict) -> float:
    points = 0
    if f.get("puits"):
        points += 12
    if f.get("recuperation_pluie"):
        points += 4
    if f.get("eau_proximite"):
        points += 4
    return min(points, 20)


def _pilier_abri(f: dict) -> float:
    points = 0
    if f.get("cave"):
        points += 8
    if f.get("grange_dependance"):
        points += 4
    if f.get("atelier"):
        points += 3
    return min(points, 15)


def _pilier_energie(f: dict, dpe: str | None) -> float:
    points = 0
    if f.get("bois"):
        points += 6
    if f.get("solaire"):
        points += 5
    if dpe in ("A", "B"):
        points += 4
    elif dpe == "C":
        points += 2
    return min(points, 15)


def _pilier_alimentation(f: dict, terrain_m2: float | None) -> float:
    points = 0
    terrain = terrain_m2 or 0
    if terrain >= 10_000:
        points += 8
    elif terrain >= 5_000:
        points += 6
    elif terrain >= 2_500:
        points += 4
    elif terrain >= 1_000:
        points += 2
    if f.get("verger_potager"):
        points += 4
    if f.get("serre"):
        points += 3
    return min(points, 15)


def _pilier_risques(r: dict) -> float:
    """Part de 20 points, puis retire des points par risque identifié."""
    points = 20.0
    if r.get("inondation"):
        points -= 8
    argile = r.get("argile") or 0
    if argile >= 2:
        points -= 3
    elif argile == 1:
        points -= 1
    seveso = r.get("seveso_km")
    if seveso is not None:
        if seveso < 5:
            points -= 4
        elif seveso < 10:
            points -= 2
    nucleaire = r.get("nucleaire_km")
    if nucleaire is not None:
        if nucleaire < 10:
            points -= 5
        elif nucleaire < 20:
            points -= 3
    if r.get("feu_foret"):
        points -= 2
    return max(points, 0)


def _pilier_situation(altitude, densite, temps_min) -> float:
    points = 0
    if altitude is not None:
        if altitude >= 200:
            points += 3
        elif altitude >= 100:
            points += 2
    if densite is None:
        points += 2  # inconnue : valeur neutre
    elif densite < 30:
        points += 6
    elif densite < 80:
        points += 4
    elif densite < 300:
        points += 2
    if temps_min is not None:
        if temps_min <= 90:
            points += 6
        elif temps_min <= 150:
            points += 4
        elif temps_min <= 210:
            points += 2
    return min(points, 15)


MAX_PILIERS = {
    "eau": 20,
    "abri": 15,
    "energie": 15,
    "alimentation": 15,
    "risques": 20,
    "situation": 15,
}

LIBELLES_PILIERS = {
    "eau": "Autonomie en eau",
    "abri": "Abri & stockage",
    "energie": "Énergie",
    "alimentation": "Autonomie alimentaire",
    "risques": "Exposition aux risques",
    "situation": "Situation & accès",
}


def classe_score(total: float) -> str:
    if total >= 70:
        return "Excellent potentiel refuge"
    if total >= 55:
        return "Bon potentiel"
    if total >= 40:
        return "Potentiel moyen"
    return "Potentiel limité"


def _badges(f: dict, annonce: dict, piliers: dict) -> list[str]:
    badges = []
    if f.get("cave"):
        badges.append("Cave / sous-sol")
    if f.get("puits"):
        badges.append("Puits ou forage")
    if f.get("eau_proximite"):
        badges.append("Eau à proximité")
    if f.get("recuperation_pluie"):
        badges.append("Récupération d'eau")
    if f.get("bois"):
        badges.append("Chauffage au bois")
    if f.get("solaire"):
        badges.append("Panneaux solaires")
    if f.get("verger_potager"):
        badges.append("Verger / potager")
    if f.get("serre"):
        badges.append("Serre")
    if f.get("grange_dependance"):
        badges.append("Dépendances")
    terrain = annonce.get("terrain_m2") or 0
    if terrain >= 2_500:
        badges.append(f"Grand terrain ({int(terrain):,} m²)".replace(",", " "))
    densite = annonce.get("densite_hab_km2")
    if densite is not None and densite < 80:
        badges.append("Zone peu dense")
    temps = annonce.get("temps_voiture_min")
    if temps is not None and temps <= 120:
        badges.append("À moins de 2 h de Paris")
    if piliers["risques"]["points"] >= 18:
        badges.append("Faible exposition aux risques")
    return badges


def _alertes(r: dict, dpe: str | None) -> list[str]:
    alertes = []
    if r.get("inondation"):
        alertes.append("Zone inondable")
    if (r.get("argile") or 0) >= 2:
        alertes.append("Sols argileux (retrait-gonflement)")
    seveso = r.get("seveso_km")
    if seveso is not None and seveso < 10:
        alertes.append(f"Site industriel Seveso à {seveso:.0f} km")
    nucleaire = r.get("nucleaire_km")
    if nucleaire is not None and nucleaire < 20:
        alertes.append(f"Centrale nucléaire à {nucleaire:.0f} km")
    if r.get("feu_foret"):
        alertes.append("Risque feux de forêt")
    if dpe in ("F", "G"):
        alertes.append(f"Passoire thermique (DPE {dpe})")
    return alertes


def calculer_score(annonce: dict) -> dict:
    """Calcule le score de résilience d'une annonce.

    L'annonce doit contenir : features (dict), risques (dict), et si possible
    terrain_m2, altitude, densite_hab_km2, temps_voiture_min, dpe.
    """
    f = annonce.get("features", {})
    r = annonce.get("risques", {})
    valeurs = {
        "eau": _pilier_eau(f),
        "abri": _pilier_abri(f),
        "energie": _pilier_energie(f, annonce.get("dpe")),
        "alimentation": _pilier_alimentation(f, annonce.get("terrain_m2")),
        "risques": _pilier_risques(r),
        "situation": _pilier_situation(
            annonce.get("altitude"),
            annonce.get("densite_hab_km2"),
            annonce.get("temps_voiture_min"),
        ),
    }
    piliers = {
        cle: {"points": round(pts, 1), "max": MAX_PILIERS[cle], "libelle": LIBELLES_PILIERS[cle]}
        for cle, pts in valeurs.items()
    }
    total = round(sum(valeurs.values()))
    return {
        "total": total,
        "classe": classe_score(total),
        "piliers": piliers,
        "badges": _badges(f, annonce, piliers),
        "alertes": _alertes(r, annonce.get("dpe")),
    }
