"""Indice de résilience par région — sert à PRIORISER les terroirs du POC.

Pourquoi pas la moyenne des annonces ? Parce qu'elle dépend des biens
présents (petits échantillons, atouts détectés au hasard dans la démo). Pour
décider « quels terroirs cibler », on raisonne à l'échelle de la région, sur
des facteurs structurels et durables — les mêmes piliers que le score d'un
bien, mais appliqués au territoire :

    eau     potentiel d'autonomie en eau (pluviométrie, nappes, rivières)
            — pénalisé par l'exposition aux crues
    bois    couverture forestière / bocage (chauffage, matériaux)
    terres  terres cultivables et espace (autonomie alimentaire)
    surete  FAIBLE exposition aux risques (nucléaire, Seveso, inondation,
            feux de forêt, industrie lourde)
    acces   accessibilité depuis Paris (un refuge trop loin ne sert pas)

Chaque axe est noté sur 20 (total /100). Les valeurs sont une estimation
experte assumée pour le POC : elles sont transparentes et destinées à être
affinées avec des données ouvertes (Corine Land Cover pour la forêt, INSEE
pour la densité, DRIAS pour le climat 2050, Géorisques pour les risques).

Résultat : on cible les 5 terroirs les mieux notés et on écarte l'Île-de-France
(trop dense, artificialisée, en stress hydrique et îlot de chaleur — la moins
résiliente pour un projet de repli, même si c'est la plus proche).
"""

from __future__ import annotations

AXES = {
    "eau": "Autonomie en eau",
    "bois": "Bois & forêt",
    "terres": "Terres nourricières",
    "surete": "Faible exposition aux risques",
    "acces": "Accès depuis Paris",
}

# Région : zone-cœur, axes /20, argument pour l'utilisateur.
REGIONS = [
    {
        "region": "Normandie",
        "zone": "Le Perche, le bocage ornais et l'Eure",
        "axes": {"eau": 17, "bois": 16, "terres": 15, "surete": 17, "acces": 14},
        "argument": "Collines bocagères pluvieuses, haies et bois partout, "
                    "élevage : eau, chauffage et nourriture de proximité, loin "
                    "du nucléaire et des grandes crues. Le refuge par excellence.",
    },
    {
        "region": "Bourgogne-Franche-Comté",
        "zone": "Le Morvan, la Puisaye et la Nièvre",
        "axes": {"eau": 18, "bois": 18, "terres": 13, "surete": 15, "acces": 12},
        "argument": "Le « château d'eau » du Morvan : lacs, rivières, immenses "
                    "forêts, densité minuscule. Autonomie eau + bois maximale, "
                    "au prix d'un accès un peu plus long.",
    },
    {
        "region": "Hauts-de-France",
        "zone": "Les forêts de l'Oise et la Thiérache",
        "axes": {"eau": 14, "bois": 15, "terres": 14, "surete": 12, "acces": 15},
        "argument": "Grandes forêts (Compiègne, Retz) et bocage de Thiérache, "
                    "très proches de Paris — à trier pour éviter les bassins "
                    "industriels denses du Nord.",
    },
    {
        "region": "Grand Est",
        "zone": "Le Pays d'Othe et l'Aube forestière",
        "axes": {"eau": 14, "bois": 14, "terres": 14, "surete": 12, "acces": 13},
        "argument": "Forêt d'Othe et lacs de l'Aube, terroir équilibré et "
                    "abordable ; vigilance sur la centrale de Nogent-sur-Seine "
                    "et la Champagne intensive.",
    },
    {
        "region": "Centre-Val de Loire",
        "zone": "Le Perche vendômois et les collines du Cher",
        "axes": {"eau": 12, "bois": 13, "terres": 15, "surete": 11, "acces": 15},
        "argument": "Grandes terres et bon accès, mais on évite le couloir "
                    "nucléaire de la Loire, les crues du val et les feux de "
                    "Sologne : la sélection des communes compte beaucoup ici.",
    },
    {
        "region": "Île-de-France",
        "zone": "Brie, Vexin, Hurepoix",
        "axes": {"eau": 9, "bois": 10, "terres": 10, "surete": 9, "acces": 18},
        "argument": "La plus proche, mais la plus dense et artificialisée, en "
                    "stress hydrique et îlot de chaleur : écartée de la cible "
                    "refuge malgré sa proximité.",
    },
]

# Nombre de terroirs retenus pour le POC.
NB_CIBLES = 5


def _total(axes: dict) -> int:
    return sum(axes.values())


def classement() -> list[dict]:
    """Régions triées par indice décroissant, avec rang, total et statut ciblé."""
    tries = sorted(REGIONS, key=lambda r: _total(r["axes"]), reverse=True)
    resultat = []
    for i, r in enumerate(tries, start=1):
        resultat.append({
            **r,
            "total": _total(r["axes"]),
            "rang": i,
            "cible": i <= NB_CIBLES,
        })
    return resultat


def regions_cibles() -> list[str]:
    """Noms des 5 régions les plus résilientes (celles que le POC cible)."""
    return [r["region"] for r in classement() if r["cible"]]
