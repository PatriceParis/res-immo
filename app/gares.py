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
]

# Au-delà de cette distance, on considère qu'il faut de toute façon une voiture
# pour rejoindre la gare : le bien n'est plus « accessible en train ».
RAYON_MAX_KM = 25.0


def gare_la_plus_proche(lat: float, lon: float) -> dict | None:
    """Gare la plus proche d'un point, si elle est à moins de RAYON_MAX_KM.

    Renvoie {"nom", "km", "minutes_paris", "gare_paris"} ou None.
    """
    if lat is None or lon is None:
        return None
    meilleure, distance_min = None, None
    for nom, glat, glon, minutes, depuis in GARES:
        d = haversine_km(lat, lon, glat, glon)
        if distance_min is None or d < distance_min:
            meilleure, distance_min = (nom, minutes, depuis), d
    if meilleure is None or distance_min > RAYON_MAX_KM:
        return None
    nom, minutes, depuis = meilleure
    return {
        "nom": nom,
        "km": round(distance_min, 1),
        "minutes_paris": minutes,
        "gare_paris": f"Paris-{depuis}",
    }
