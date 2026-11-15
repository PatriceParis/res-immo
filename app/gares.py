"""Accessibilité en train depuis Paris — critère de résilience à part entière.

Pourquoi le train compte pour un refuge : la voiture suppose du carburant, un
véhicule en état et des routes praticables. Une commune desservie par une gare
reste **atteignable sans voiture** — en cas de pénurie de carburant, de prix de
l'énergie qui s'envole, ou tout simplement pour qui n'a pas de voiture. C'est
aussi ce qui rend un repli **compatible avec un travail à Paris** (aller-retour
possible), donc un projet réaliste plutôt qu'un rêve.

Vendôme en est l'exemple parfait : 42 min de Paris-Montparnasse en TGV, au cœur
d'un terroir rural. Château-Thierry (~50 min) et Noyon (~1 h) jouent le même rôle
dans l'Aisne et l'Oise.

Les temps sont ceux des liaisons directes courantes (TGV, Intercités ou TER),
arrondis ; ils servent à *classer* les communes, pas à réserver un billet.
"""

from __future__ import annotations

import json
from pathlib import Path

from .geo import haversine_km

# (nom de la gare, latitude, longitude, minutes depuis Paris, gare parisienne)
# Gares des 5 régions cibles offrant un accès direct raisonnable.
GARES = [
    # --- Centre-Val de Loire (Montparnasse / Austerlitz) ---
    ("Vendôme–Villiers-sur-Loir TGV", 47.8228, 1.0353, 42, "Montparnasse"),
    ("Châteaudun", 48.0725, 1.3253, 75, "Austerlitz"),
    ("Blois–Chambord", 47.5906, 1.3253, 85, "Austerlitz"),
    ("Chartres", 48.4472, 1.4817, 65, "Montparnasse"),
    ("Nogent-le-Rotrou", 48.3197, 0.8194, 70, "Montparnasse"),
    ("Orléans", 47.9083, 1.9058, 65, "Austerlitz"),
    ("Gien", 47.6906, 2.6333, 95, "Bercy"),
    # --- Hauts-de-France (Nord / Est) ---
    ("Noyon", 49.5806, 3.0011, 65, "Nord"),
    ("Compiègne", 49.4256, 2.8258, 45, "Nord"),
    ("Creil", 49.2633, 2.4694, 30, "Nord"),
    ("Beauvais", 49.4283, 2.0894, 75, "Nord"),
    ("Saint-Quentin", 49.8483, 3.2953, 75, "Nord"),
    ("Laon", 49.5644, 3.6231, 95, "Nord"),
    # --- Grand Est (Est) ---
    ("Château-Thierry", 49.0397, 3.4028, 50, "Est"),
    ("Épernay", 49.0442, 3.9553, 75, "Est"),
    ("Romilly-sur-Seine", 48.5147, 3.7275, 80, "Est"),
    ("Troyes", 48.2947, 4.0653, 90, "Est"),
    ("Nogent-sur-Seine", 48.4919, 3.5033, 65, "Est"),
    # --- Normandie (Saint-Lazare / Montparnasse) ---
    ("Évreux–Normandie", 49.0208, 1.1428, 60, "Saint-Lazare"),
    ("Vernon–Giverny", 49.0908, 1.4756, 45, "Saint-Lazare"),
    ("Bernay", 49.0906, 0.5983, 90, "Saint-Lazare"),
    ("L'Aigle", 48.7592, 0.6317, 105, "Montparnasse"),
    ("Alençon", 48.4331, 0.0947, 115, "Montparnasse"),
    ("Argentan", 48.7444, -0.0197, 120, "Montparnasse"),
    ("Lisieux", 49.1447, 0.2264, 105, "Saint-Lazare"),
    # --- Bourgogne-Franche-Comté (Bercy / Lyon) ---
    ("Sens", 48.1978, 3.2778, 55, "Bercy"),
    ("Joigny", 47.9803, 3.3936, 75, "Bercy"),
    ("Migennes", 47.9656, 3.5122, 65, "Bercy"),
    ("Auxerre–Saint-Gervais", 47.7961, 3.5822, 105, "Bercy"),
    ("Avallon", 47.4886, 3.9058, 145, "Bercy"),
    ("Montbard", 47.6236, 4.3369, 60, "Lyon"),
    ("Clamecy", 47.4589, 3.5194, 150, "Bercy"),
    ("Nevers", 46.9906, 3.1567, 120, "Bercy"),
    # Saône-et-Loire. Le cas d'école de ce que le train change : Chalon est à
    # 4 h 25 de route, mais Le Creusot TGV met Paris à 1 h 20 — ce bassin est
    # donc bien plus proche qu'il n'y paraît sur une carte routière.
    ("Le Creusot–Montceau–Montchanin TGV", 46.8003, 4.4331, 80, "Lyon"),
    ("Chalon-sur-Saône", 46.7806, 4.8536, 95, "Lyon"),
    ("Montceau-les-Mines", 46.6739, 4.3661, 100, "Lyon"),
    # --- Pays de la Loire (Montparnasse) ---
    # Le Mans est la MEILLEURE desserte de toute la sélection : 55 min de
    # Montparnasse, mieux que Vendôme. Les biens du Perche sarthois étaient
    # pourtant notés comme si aucune gare n'existait — la table s'arrêtait à
    # la frontière de l'Orne.
    ("Le Mans", 47.9953, 0.1925, 55, "Montparnasse"),
    ("La Ferté-Bernard", 48.1875, 0.6503, 80, "Montparnasse"),
    ("Sablé-sur-Sarthe", 47.8397, -0.3311, 90, "Montparnasse"),
    ("Laval", 48.0772, -0.7614, 80, "Montparnasse"),
    ("Mayenne", 48.3033, -0.6167, 145, "Montparnasse"),
]

# Au-delà de cette distance, on considère qu'il faut de toute façon une voiture
# pour rejoindre la gare : le bien n'est plus « accessible en train ».
RAYON_MAX_KM = 25.0

# Le référentiel SNCF des gares de voyageurs (Licence Ouverte), importé par
# scripts/importer_gares.py. Les 41 gares ci-dessus ne couvraient que les
# régions d'origine du projet : mesuré le 15 novembre 2026, 72 % des biens
# n'avaient aucune gare à moins de 25 km, et les départements découverts
# étaient ceux de Lille, Nancy, Rouen, Caen et Tours. Ce n'était pas une
# absence de desserte, c'était notre ignorance — et le filtre « gare la plus
# proche » écartait les biens sur elle. Avec le référentiel : 95 %.
_FICHIER_SNCF = Path(__file__).resolve().parent.parent / "data" / "gares_sncf.json"
# Un degré de latitude fait 111 km, un degré de longitude au moins 68 aux
# latitudes du périmètre : chercher dans la cellule du point et ses huit
# voisines couvre donc largement les 25 km du rayon. Sans cette grille, un
# chargement comparerait 17 000 biens à 2 792 gares — quarante-sept millions
# de distances, plusieurs minutes, à chaque démarrage.
_GRILLE: dict[tuple[int, int], list[tuple[str, float, float, str]]] = {}


def _charger_referentiel() -> None:
    if _GRILLE:
        return
    try:
        brut = json.loads(_FICHIER_SNCF.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        brut = []                      # le fichier manque : on garde les 41
    for gare in brut:
        try:
            lat, lon = float(gare["lat"]), float(gare["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        _GRILLE.setdefault((int(lat), int(lon)), []).append(
            (gare.get("nom") or "", lat, lon, gare.get("segment") or ""))


def _plus_proche_du_referentiel(lat: float, lon: float):
    """(nom, km, segment) de la gare la plus proche, toutes gares confondues."""
    _charger_referentiel()
    meilleure, distance_min = None, None
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            for nom, glat, glon, segment in _GRILLE.get(
                    (int(lat) + dlat, int(lon) + dlon), ()):
                d = haversine_km(lat, lon, glat, glon)
                if distance_min is None or d < distance_min:
                    meilleure, distance_min = (nom, segment), d
    if meilleure is None:
        return None
    return meilleure[0], distance_min, meilleure[1]


def _plus_proche_vers_paris(lat: float, lon: float):
    """(nom, km, minutes, gare parisienne) parmi les gares au temps connu.

    Le référentiel SNCF ne porte AUCUN temps de trajet, et il ne faut pas en
    inventer : Vendôme est à 42 min pour 160 km, Creil à 30 min pour 50 — le
    rapport varie du simple au triple selon la ligne. Les 41 gares saisies à
    la main gardent donc leur rôle, et c'est le seul : dire « Paris en ».
    """
    meilleure, distance_min = None, None
    for nom, glat, glon, minutes, depuis in GARES:
        d = haversine_km(lat, lon, glat, glon)
        if distance_min is None or d < distance_min:
            meilleure, distance_min = (nom, minutes, depuis), d
    if meilleure is None or distance_min > RAYON_MAX_KM:
        return None
    nom, minutes, depuis = meilleure
    return nom, distance_min, minutes, depuis


def gare_la_plus_proche(lat: float, lon: float) -> dict | None:
    """La desserte ferroviaire d'un point, si une gare est dans le rayon.

    DEUX questions, et elles n'ont pas la même réponse depuis l'import du
    référentiel :

    - « une gare à portée ? » — le pilier « accès sans voiture ». Toutes les
      gares comptent, halte comprise, et `segment` dit laquelle on a trouvée
      (A : grande gare nationale, B : régionale, C : halte). Annoncer « gare
      à 2 km » sans dire que c'est une halte serait la demi-vérité que ce
      site évite ailleurs.
    - « Paris en combien ? » — seules les gares au temps saisi savent
      répondre. Si c'en est une autre que la plus proche, `nom_vers_paris` le
      dit, pour que la fiche n'attribue pas à l'une le temps de l'autre.

    Renvoie None si aucune gare n'est dans le rayon : pour ce bien, la
    question ne se pose pas.
    """
    if lat is None or lon is None:
        return None

    proche = _plus_proche_du_referentiel(lat, lon)
    vers_paris = _plus_proche_vers_paris(lat, lon)
    if proche is None or proche[1] > RAYON_MAX_KM:
        # Aucune gare du référentiel à portée. Les 41 en connaissent-elles
        # une ? Le référentiel les couvre toutes, donc non en pratique ;
        # le repli existe pour le jour où le fichier manquerait.
        if vers_paris is None:
            return None
        nom, km, minutes, depuis = vers_paris
        proche = (nom, km, "")

    nom, km, segment = proche
    resultat = {
        "nom": nom,
        "km": round(km, 1),
        "segment": segment,
        "minutes_paris": None,
        "gare_paris": "",
        "nom_vers_paris": "",
        "km_vers_paris": None,
    }
    if vers_paris is not None:
        nom_p, km_p, minutes, depuis = vers_paris
        resultat.update({
            "minutes_paris": minutes,
            "gare_paris": f"Paris-{depuis}",
            "nom_vers_paris": nom_p,
            "km_vers_paris": round(km_p, 1),
        })
    return resultat
