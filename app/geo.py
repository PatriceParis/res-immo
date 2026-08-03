"""Calculs géographiques : distance et temps de route depuis Paris, centrales nucléaires.

Le temps de trajet est une ESTIMATION calculée sans service externe :
distance à vol d'oiseau × 1,25 (détour routier moyen), puis vitesse moyenne
porte-à-porte. Suffisant pour filtrer et comparer des biens dans un POC ;
une version production brancherait un vrai calculateur d'itinéraires (OSRM…).
"""

from __future__ import annotations

import math

# Point de référence : centre de Paris (parvis Notre-Dame, "kilomètre zéro").
PARIS = (48.8530, 2.3499)

# Facteur de détour route/vol d'oiseau et vitesses moyennes retenues.
FACTEUR_ROUTE = 1.25
VITESSE_URBAINE_KMH = 27.0   # sortie d'agglomération parisienne
VITESSE_ROUTE_KMH = 95.0     # mix autoroute + nationale


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance à vol d'oiseau (formule de haversine), en kilomètres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_paris_km(lat: float, lon: float) -> float:
    return round(haversine_km(PARIS[0], PARIS[1], lat, lon), 1)


def temps_voiture_min(distance_vol_oiseau_km: float) -> float:
    """Temps de route estimé depuis Paris, en minutes (arrondi à 5 min)."""
    route = distance_vol_oiseau_km * FACTEUR_ROUTE
    if route <= 20:
        minutes = route / VITESSE_URBAINE_KMH * 60
    else:
        minutes = 20 / VITESSE_URBAINE_KMH * 60 + (route - 20) / VITESSE_ROUTE_KMH * 60
    return round(minutes / 5) * 5


# Centrales nucléaires françaises en activité (nom, latitude, longitude).
# Sert au critère "distance à une centrale" sans appel réseau.
CENTRALES_NUCLEAIRES = [
    ("Gravelines", 51.015, 2.130),
    ("Penly", 49.976, 1.212),
    ("Paluel", 49.858, 0.635),
    ("Flamanville", 49.536, -1.882),
    ("Nogent-sur-Seine", 48.515, 3.518),
    ("Cattenom", 49.416, 6.218),
    ("Chooz", 50.090, 4.789),
    ("Belleville-sur-Loire", 47.510, 2.875),
    ("Dampierre-en-Burly", 47.733, 2.516),
    ("Saint-Laurent-des-Eaux", 47.720, 1.578),
    ("Chinon", 47.231, 0.170),
    ("Civaux", 46.457, 0.654),
    ("Le Blayais", 45.256, -0.693),
    ("Golfech", 44.107, 0.845),
    ("Cruas", 44.633, 4.757),
    ("Tricastin", 44.330, 4.732),
    ("Saint-Alban", 45.404, 4.755),
    ("Bugey", 45.798, 5.271),
]


def centrale_la_plus_proche(lat: float, lon: float) -> tuple[str, float]:
    """Renvoie (nom, distance en km) de la centrale nucléaire la plus proche."""
    nom, dist = min(
        ((n, haversine_km(lat, lon, clat, clon)) for n, clat, clon in CENTRALES_NUCLEAIRES),
        key=lambda x: x[1],
    )
    return nom, round(dist, 1)
