"""Préparation et insertion des annonces en base.

C'est ici qu'une annonce « brute » (venant du jeu de démonstration ou des
robots de collecte) est enrichie : distance et temps de route depuis Paris,
détection des équipements dans le texte, distance à la centrale nucléaire la
plus proche, puis calcul du score de résilience.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import db, gares, geo, marche, regions, scoring
from .qualite import PRIX_MINI, est_bien_valide


def preparer_annonce(brut: dict) -> dict:
    annonce = dict(brut)
    titre = annonce.get("titre", "")
    description = annonce.get("description", "")

    # Prix aberrant (< 15 000 € pour une maison = référence ou n° pris pour un
    # prix) : on l'efface plutôt que d'afficher « 3 480 € » sur une propriété.
    prix = annonce.get("prix")
    if prix is not None and prix < PRIX_MINI:
        annonce["prix"] = None

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
        # Accès sans voiture : gare la plus proche et temps de train vers Paris.
        annonce["train"] = gares.gare_la_plus_proche(lat, lon)

    # Détection sur le titre + la description + le texte complet de la page
    # (`texte`) : les descriptions d'agences sont souvent très courtes, l'essentiel
    # (cave, puits, troglodyte…) est ailleurs dans la page.
    detection = f"{description} {annonce.get('texte', '')}"
    features = scoring.extraire_criteres(titre, detection)
    annonce["features"] = features

    risques = dict(annonce.get("risques") or {})
    # Données Géorisques collectées avant la distinction de portée : leurs
    # drapeaux étaient déjà **communaux** (séisme et radon ressortaient à 100 %).
    # On les requalifie pour ne pas pénaliser le bien comme s'il était exposé.
    if risques.get("source") == "georisques" and not risques.get("portee"):
        for ancien, nouveau in (("inondation", "inondation_commune"),
                                ("feu_foret", "feu_foret_commune"),
                                ("seisme", "seisme_commune"),
                                ("radon", "radon_commune"),
                                ("icpe", "icpe_commune")):
            if ancien in risques:
                risques[nouveau] = risques.pop(ancien)
        risques["portee"] = "commune"
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
    annonce["has_troglodyte"] = int(features.get("troglodyte", False))
    # Mémoire portée par le fichier exporté (app/historique.py) : on la
    # laisse telle quelle, c'est elle qui dit ce qui est nouveau.
    # Le filtre d'inondation lisait encore la clé `inondation`, disparue quand
    # les risques Géorisques ont été renommés `*_commune` (leur portée réelle).
    # Plus aucun bien n'était donc marqué en zone inondable : la case « Hors
    # zone inondable » ne filtrait PLUS RIEN — 133 biens sur 133 la passaient,
    # dont 86 dans une commune où l'inondation est documentée.
    #
    # On accepte les deux clés : `inondation` quand l'information est connue à
    # la parcelle, `inondation_commune` (le cas courant) quand elle ne l'est
    # qu'à l'échelle de la commune. L'intitulé de la case le dit.
    annonce["hors_inondation"] = 0 if (
        risques.get("inondation") or risques.get("inondation_commune")) else 1
    return annonce


# Au-delà, ce n'est plus une base de repli depuis Paris — et c'est en pratique
# le signe d'une géolocalisation ratée (un numéro de référence pris pour un code
# postal envoyait des biens du Perche dans la Creuse ou le Cantal).
DISTANCE_MAX_KM = 350

# Départements des terroirs ciblés. Un bien annoncé hors de cette liste par une
# agence du Perche trahit une erreur de lecture, pas une vraie annonce
# lointaine : on l'écarte même sans coordonnées.
#
# L'Île-de-France en est exclue **volontairement** : elle est dernière au
# classement des terroirs (trop dense, artificialisée, en stress hydrique) et
# ne fait donc pas partie de la cible. Sans cette exclusion, les agences
# frontalières y ramenaient des biens — La Ferté-sous-Jouarre, Nangis — que
# l'application est précisément censée écarter.
#
# La liste se déduit ENTIÈREMENT du classement des terroirs : la Sarthe et la
# Mayenne y figuraient auparavant en dur, si bien que leurs biens étaient
# comptés dans le total mais rattachés à aucune pastille — introuvables par
# le filtre de région. Elles relèvent désormais du terroir « Pays de la Loire ».
DEPARTEMENTS_CIBLES = {
    dept for dept, region in regions.REGION_PAR_DEPT.items()
    if region in set(regions.regions_cibles())
}


def _signatures_suspectes(annonces: list[dict], seuil: int = 3) -> set:
    """Repère les (agence, prix, surface, terrain) qui reviennent à l'identique.

    Quand une agence sort plusieurs biens avec EXACTEMENT le même prix, la même
    surface et le même terrain, ce ne sont pas des biens : l'extraction a lu un
    bandeau commun à toutes les pages du site (cas réel : 10 annonces à
    530 000 €, 265 m², dans dix communes différentes). On préfère ne rien
    afficher plutôt que des biens fantômes aux prix faux.
    """
    compte: dict = {}
    for a in annonces:
        cle = (a.get("agence"), a.get("prix"), a.get("surface_m2"), a.get("terrain_m2"))
        if cle[1] is None and cle[2] is None:
            continue
        compte[cle] = compte.get(cle, 0) + 1
    return {cle for cle, n in compte.items() if n >= seuil}


def charger_liste(conn, annonces: list[dict]) -> int:
    """Enrichit et insère les annonces VALIDES (filtre qualité). Renvoie le nombre chargé.

    Deux temps : on prépare d'abord tous les biens retenus, car situer un prix
    par rapport à son secteur suppose de connaître l'ensemble ; on écrit
    ensuite.
    """
    retenues = _preparer_toutes(conn, annonces)
    medianes = marche.medianes_par_secteur(retenues)
    for annonce in retenues:
        db.upsert_annonce(conn, marche.situer(annonce, medianes))
    conn.commit()
    return len(retenues)


def _preparer_toutes(conn, annonces: list[dict]) -> list[dict]:
    """Applique tous les filtres de qualité et de périmètre, sans écrire."""
    suspectes = _signatures_suspectes(annonces)
    retenues = []
    for brut in annonces:
        if (brut.get("agence"), brut.get("prix"), brut.get("surface_m2"),
                brut.get("terrain_m2")) in suspectes:
            continue  # doublons issus d'un bandeau de site, pas de vrais biens
        if not est_bien_valide(brut):
            continue  # blog, page catalogue, appartement, parking, vendu… : écarté
        annonce = preparer_annonce(brut)
        distance = annonce.get("distance_km")
        if distance is not None and distance > DISTANCE_MAX_KM:
            continue  # hors zone de repli, ou géolocalisation aberrante
        dept = annonce.get("departement")
        if not dept:
            # Sans localisation, on ne peut ni situer le bien, ni calculer sa
            # distance de Paris, sa densité ou sa gare : la moitié du score est
            # indéterminable et l'acheteur ne sait même pas où c'est. En
            # pratique, ce sont des pages d'agence ou de constructeur.
            continue
        if str(dept) not in DEPARTEMENTS_CIBLES:
            continue  # hors des terroirs ciblés (souvent une réf. lue comme un CP)
        retenues.append(annonce)
    return retenues


def charger_annonces_json(conn, chemin: Path | str) -> int:
    """Charge un fichier JSON (liste d'annonces brutes) en base."""
    return charger_liste(conn, json.loads(Path(chemin).read_text(encoding="utf-8")))
