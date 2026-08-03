"""Préparation et insertion des annonces en base.

C'est ici qu'une annonce « brute » (venant du jeu de démonstration ou des
robots de collecte) est enrichie : distance et temps de route depuis Paris,
détection des équipements dans le texte, distance à la centrale nucléaire la
plus proche, puis calcul du score de résilience.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import db, geo, regions, scoring
from .qualite import est_bien_valide


def preparer_annonce(brut: dict) -> dict:
    annonce = dict(brut)
    titre = annonce.get("titre", "")
    description = annonce.get("description", "")

    # Région : déduite du département (les annonces d'agences ne la donnent pas).
    if not annonce.get("region"):
        dept = annonce.get("departement") or (str(annonce["code_postal"])[:2]
                                              if annonce.get("code_postal") else None)
        region = regions.region_du_departement(dept)
        if region:
            annonce["region"] = region
            annonce.setdefault("departement", dept)

    lat, lon = annonce.get("lat"), annonce.get("lon")
    if lat is not None and lon is not None:
        distance = geo.distance_paris_km(lat, lon)
        annonce["distance_km"] = distance
        annonce["temps_voiture_min"] = geo.temps_voiture_min(distance)

    # Détection sur le titre + la description + le texte complet de la page
    # (`texte`) : les descriptions d'agences sont souvent très courtes, l'essentiel
    # (cave, puits, troglodyte…) est ailleurs dans la page.
    detection = f"{description} {annonce.get('texte', '')}"
    features = scoring.extraire_criteres(titre, detection)
    annonce["features"] = features

    risques = dict(annonce.get("risques") or {})
    if lat is not None and lon is not None and risques.get("nucleaire_km") is None:
        nom, dist = geo.centrale_la_plus_proche(lat, lon)
        risques["nucleaire_km"] = dist
        risques["nucleaire_nom"] = nom
    annonce["risques"] = risques

    detail = scoring.calculer_score(annonce)
    annonce["score_total"] = detail["total"]
    annonce["score_detail"] = detail
    annonce["badges"] = detail["badges"]
    annonce["alertes"] = detail["alertes"]

    annonce["has_cave"] = int(features.get("cave", False))
    annonce["has_puits"] = int(features.get("puits", False))
    annonce["has_bois"] = int(features.get("bois", False))
    annonce["has_solaire"] = int(features.get("solaire", False))
    annonce["has_dependances"] = int(features.get("grange_dependance", False))
    annonce["has_potager"] = int(features.get("verger_potager", False))
    annonce["hors_inondation"] = 0 if risques.get("inondation") else 1
    return annonce


def charger_liste(conn, annonces: list[dict]) -> int:
    """Enrichit et insère les annonces VALIDES (filtre qualité). Renvoie le nombre chargé."""
    n = 0
    for brut in annonces:
        if not est_bien_valide(brut):
            continue  # blog, page catalogue, appartement, parking… : écarté
        db.upsert_annonce(conn, preparer_annonce(brut))
        n += 1
    conn.commit()
    return n


def charger_annonces_json(conn, chemin: Path | str) -> int:
    """Charge un fichier JSON (liste d'annonces brutes) en base."""
    return charger_liste(conn, json.loads(Path(chemin).read_text(encoding="utf-8")))
