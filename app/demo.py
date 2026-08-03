"""Générateur du jeu de démonstration — biens FICTIFS mais réalistes.

Les communes, coordonnées, altitudes et niveaux de prix sont plausibles ;
les biens eux-mêmes sont inventés. Utilisé de deux façons :
- `scripts/generer_demo.py` écrit data/annonces_demo.json (usage local) ;
- sur un hébergement serverless (Vercel), les annonces sont générées en
  mémoire au premier appel, sans fichier.

La graine aléatoire est fixe : le jeu produit est toujours identique.
"""

from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Communes cibles : (nom, code postal, département, région, lat, lon,
#   altitude m, densité hab/km², prix maison €/m², risques particuliers)
# `inondation` marque les communes traversées par un cours d'eau à crues ;
# `argile` : 0 faible, 1 moyen, 2 fort (retrait-gonflement des argiles) ;
# `feu_foret` : proximité d'un massif sensible ; `seveso_km` : site industriel.
# ---------------------------------------------------------------------------
COMMUNES = [
    ("Provins", "77160", "Seine-et-Marne", "Île-de-France", 48.559, 3.299, 150, 130, 2200, {"argile": 2}),
    ("Bray-sur-Seine", "77480", "Seine-et-Marne", "Île-de-France", 48.414, 3.239, 60, 90, 1900, {"inondation": True, "argile": 1}),
    ("Rozay-en-Brie", "77540", "Seine-et-Marne", "Île-de-France", 48.685, 2.960, 110, 180, 2500, {"argile": 2}),
    ("Jouarre", "77640", "Seine-et-Marne", "Île-de-France", 48.925, 3.129, 150, 120, 2300, {"argile": 2}),
    ("Château-Landon", "77570", "Seine-et-Marne", "Île-de-France", 48.148, 2.697, 100, 80, 1900, {"argile": 1}),
    ("Milly-la-Forêt", "91490", "Essonne", "Île-de-France", 48.403, 2.470, 70, 100, 2800, {"feu_foret": True, "argile": 1}),
    ("Dourdan", "91410", "Essonne", "Île-de-France", 48.529, 2.011, 130, 300, 2900, {"argile": 1}),
    ("Houdan", "78550", "Yvelines", "Île-de-France", 48.790, 1.600, 110, 250, 2900, {"argile": 1}),
    ("La Roche-Guyon", "95780", "Val-d'Oise", "Île-de-France", 49.080, 1.630, 30, 90, 2600, {"inondation": True}),
    ("Magny-en-Vexin", "95420", "Val-d'Oise", "Île-de-France", 49.155, 1.786, 110, 150, 2400, {"argile": 1}),
    ("Senonches", "28250", "Eure-et-Loir", "Centre-Val de Loire", 48.562, 1.031, 250, 40, 1500, {"feu_foret": True}),
    ("Illiers-Combray", "28120", "Eure-et-Loir", "Centre-Val de Loire", 48.303, 1.244, 160, 60, 1500, {"argile": 1}),
    ("Nogent-le-Rotrou", "28400", "Eure-et-Loir", "Centre-Val de Loire", 48.322, 0.822, 130, 400, 1500, {}),
    ("Bonneval", "28800", "Eure-et-Loir", "Centre-Val de Loire", 48.183, 1.386, 130, 100, 1500, {"inondation": True, "argile": 2}),
    ("Bellême", "61130", "Orne", "Normandie", 48.373, 0.560, 220, 60, 1500, {}),
    ("Mortagne-au-Perche", "61400", "Orne", "Normandie", 48.521, 0.548, 230, 90, 1500, {}),
    ("Longny-les-Villages", "61290", "Orne", "Normandie", 48.530, 0.752, 200, 25, 1300, {}),
    ("Carrouges", "61320", "Orne", "Normandie", 48.567, -0.148, 300, 20, 1100, {}),
    ("Bagnoles-de-l'Orne", "61140", "Orne", "Normandie", 48.556, -0.404, 220, 90, 1700, {"feu_foret": True}),
    ("L'Aigle", "61300", "Orne", "Normandie", 48.764, 0.628, 220, 500, 1300, {}),
    ("Lyons-la-Forêt", "27480", "Eure", "Normandie", 49.399, 1.474, 100, 30, 2200, {}),
    ("Verneuil-d'Avre-et-d'Iton", "27130", "Eure", "Normandie", 48.740, 0.927, 170, 150, 1600, {}),
    ("Bernay", "27300", "Eure", "Normandie", 49.089, 0.599, 110, 400, 1500, {}),
    ("Gerberoy", "60380", "Oise", "Hauts-de-France", 49.532, 1.848, 180, 25, 1900, {}),
    ("Chaumont-en-Vexin", "60240", "Oise", "Hauts-de-France", 49.265, 1.885, 90, 150, 2200, {"argile": 1}),
    ("Pierrefonds", "60350", "Oise", "Hauts-de-France", 49.347, 2.980, 90, 80, 2300, {}),
    ("Crépy-en-Valois", "60800", "Oise", "Hauts-de-France", 49.234, 2.888, 130, 900, 2400, {"seveso_km": 8.0}),
    ("Château-Thierry", "02400", "Aisne", "Hauts-de-France", 49.046, 3.403, 70, 500, 1800, {"inondation": True}),
    ("Villers-Cotterêts", "02600", "Aisne", "Hauts-de-France", 49.253, 3.090, 130, 300, 1900, {}),
    ("Sézanne", "51120", "Marne", "Grand Est", 48.721, 3.723, 120, 130, 1500, {"argile": 1}),
    ("Montmirail", "51210", "Marne", "Grand Est", 48.870, 3.540, 200, 90, 1400, {"argile": 2}),
    ("Nogent-sur-Seine", "10400", "Aube", "Grand Est", 48.493, 3.502, 70, 150, 1700, {"inondation": True}),
    ("Aix-Villemaur-Pâlis", "10160", "Aube", "Grand Est", 48.223, 3.734, 170, 50, 1300, {}),
    ("Bar-sur-Seine", "10110", "Aube", "Grand Est", 48.113, 4.377, 160, 90, 1400, {}),
    ("Joigny", "89300", "Yonne", "Bourgogne-Franche-Comté", 47.982, 3.397, 90, 190, 1400, {"inondation": True}),
    ("Toucy", "89130", "Yonne", "Bourgogne-Franche-Comté", 47.736, 3.294, 230, 50, 1300, {}),
    ("Saint-Fargeau", "89170", "Yonne", "Bourgogne-Franche-Comté", 47.641, 3.072, 230, 30, 1200, {}),
    ("Chablis", "89800", "Yonne", "Bourgogne-Franche-Comté", 47.813, 3.798, 140, 60, 1700, {}),
    ("Noyers-sur-Serein", "89310", "Yonne", "Bourgogne-Franche-Comté", 47.695, 3.995, 180, 20, 1400, {}),
    ("Avallon", "89200", "Yonne", "Bourgogne-Franche-Comté", 47.490, 3.908, 250, 260, 1400, {}),
    ("Vézelay", "89450", "Yonne", "Bourgogne-Franche-Comté", 47.466, 3.749, 300, 40, 1800, {}),
    ("Clamecy", "58500", "Nièvre", "Bourgogne-Franche-Comté", 47.460, 3.519, 150, 80, 1100, {"inondation": True}),
    ("Lormes", "58140", "Nièvre", "Bourgogne-Franche-Comté", 47.289, 3.817, 350, 25, 1000, {}),
    ("Corbigny", "58800", "Nièvre", "Bourgogne-Franche-Comté", 47.257, 3.683, 230, 40, 1100, {}),
    ("Château-Chinon", "58120", "Nièvre", "Bourgogne-Franche-Comté", 47.065, 3.933, 530, 40, 1000, {}),
    ("La Charité-sur-Loire", "58400", "Nièvre", "Bourgogne-Franche-Comté", 47.178, 3.017, 170, 250, 1300, {"inondation": True}),
    ("Sancerre", "18300", "Cher", "Centre-Val de Loire", 47.329, 2.834, 300, 90, 1500, {}),
    ("Aubigny-sur-Nère", "18700", "Cher", "Centre-Val de Loire", 47.489, 2.440, 160, 60, 1400, {"feu_foret": True}),
    ("Lamotte-Beuvron", "41600", "Loir-et-Cher", "Centre-Val de Loire", 47.601, 2.026, 120, 90, 1700, {"feu_foret": True}),
    ("Vendôme", "41100", "Loir-et-Cher", "Centre-Val de Loire", 47.793, 1.066, 85, 700, 1800, {"inondation": True}),
    ("Gien", "45500", "Loiret", "Centre-Val de Loire", 47.686, 2.630, 130, 400, 1600, {"inondation": True}),
    ("Montargis", "45200", "Loiret", "Centre-Val de Loire", 47.997, 2.733, 90, 1600, 1800, {"inondation": True, "argile": 1, "seveso_km": 4.5}),
    ("Malesherbes", "45330", "Loiret", "Centre-Val de Loire", 48.295, 2.409, 100, 300, 2100, {"argile": 1}),
    ("Beaugency", "45190", "Loiret", "Centre-Val de Loire", 47.777, 1.626, 90, 900, 1900, {"inondation": True}),
]

# ---------------------------------------------------------------------------
# Types de biens : facteur de prix, surfaces habitables et terrains typiques,
# et probabilité de chaque équipement selon le type.
# ---------------------------------------------------------------------------
TYPES = {
    "longère": dict(facteur=0.95, surf=(120, 220), terrain=(1500, 8000),
                    equip=dict(cave=0.5, puits=0.45, bois=0.75, solaire=0.10,
                               verger=0.5, serre=0.10, grange=0.65, atelier=0.4,
                               pluie=0.15, eau=0.15)),
    "corps de ferme": dict(facteur=0.90, surf=(150, 300), terrain=(2500, 30000),
                    equip=dict(cave=0.6, puits=0.55, bois=0.7, solaire=0.12,
                               verger=0.55, serre=0.12, grange=0.9, atelier=0.5,
                               pluie=0.2, eau=0.2)),
    "fermette": dict(facteur=0.85, surf=(90, 160), terrain=(1000, 6000),
                    equip=dict(cave=0.45, puits=0.4, bois=0.7, solaire=0.08,
                               verger=0.45, serre=0.1, grange=0.55, atelier=0.35,
                               pluie=0.15, eau=0.15)),
    "maison de bourg": dict(facteur=1.0, surf=(90, 180), terrain=(100, 800),
                    equip=dict(cave=0.7, puits=0.1, bois=0.5, solaire=0.05,
                               verger=0.1, serre=0.03, grange=0.15, atelier=0.3,
                               pluie=0.05, eau=0.1)),
    "maison de campagne": dict(facteur=1.0, surf=(100, 200), terrain=(800, 4000),
                    equip=dict(cave=0.4, puits=0.3, bois=0.6, solaire=0.1,
                               verger=0.4, serre=0.1, grange=0.35, atelier=0.35,
                               pluie=0.12, eau=0.12)),
    "propriété": dict(facteur=1.25, surf=(200, 350), terrain=(5000, 30000),
                    equip=dict(cave=0.7, puits=0.5, bois=0.7, solaire=0.2,
                               verger=0.6, serre=0.2, grange=0.7, atelier=0.5,
                               pluie=0.2, eau=0.3)),
    "moulin": dict(facteur=1.10, surf=(150, 280), terrain=(2000, 15000),
                    equip=dict(cave=0.5, puits=0.2, bois=0.6, solaire=0.08,
                               verger=0.35, serre=0.08, grange=0.5, atelier=0.4,
                               pluie=0.1, eau=1.0)),
    "pavillon": dict(facteur=1.0, surf=(90, 140), terrain=(400, 1500),
                    equip=dict(cave=0.25, puits=0.05, bois=0.35, solaire=0.15,
                               verger=0.15, serre=0.05, grange=0.05, atelier=0.4,
                               pluie=0.08, eau=0.05)),
}

PHRASES = {
    "cave": ["Belle cave voûtée en pierre.", "Cave saine sous toute la maison.",
             "Sous-sol total offrant un grand volume de stockage."],
    "puits": ["Puits en état de fonctionnement dans la cour.",
              "Un forage alimente l'arrosage du jardin."],
    "eau": ["Un ruisseau borde la propriété.", "Étang en fond de parcelle.",
            "À deux pas de la rivière."],
    "pluie": ["Cuve de récupération d'eau de pluie enterrée."],
    "bois": ["Poêle à bois récent dans le séjour.", "Cheminée avec insert.",
             "Chaudière à bois, hangar à bois de chauffage."],
    "solaire": ["Panneaux solaires photovoltaïques en autoconsommation."],
    "verger": ["Verger d'arbres fruitiers (pommiers, poiriers, noyers).",
               "Grand potager déjà en place, exposition sud."],
    "serre": ["Serre de jardin adossée au mur sud."],
    "grange": ["Grange attenante d'environ {dep} m².",
               "Nombreuses dépendances : écurie, appentis, four à pain."],
    "atelier": ["Atelier lumineux avec établi.", "Garage double et atelier."],
}

ETATS = [
    ("rénovée avec goût", 1.08, None),
    ("en bon état général", 1.0, None),
    ("habitable immédiatement", 1.0, None),
    ("à rafraîchir", 0.9, None),
    ("avec travaux à prévoir", 0.72, "Prévoir un budget de rénovation."),
]

DPE_PONDERATION = [("B", 1), ("C", 2), ("D", 4), ("E", 4), ("F", 2), ("G", 1)]

# Agences FICTIVES (suffixe « démo ») pour illustrer l'attribution par agence :
# dans la vraie collecte, ces noms viennent des sites d'agences réels.
AGENCES_DEMO = {
    "Normandie": "Terres du Perche · démo",
    "Centre-Val de Loire": "Sologne & Beauce Immobilier · démo",
    "Bourgogne-Franche-Comté": "Morvan Propriétés · démo",
    "Grand Est": "Champagne Rurale Immo · démo",
    "Hauts-de-France": "Oise Campagne · démo",
    "Île-de-France": "Brie & Vexin Immobilier · démo",
}


def _choix_dpe(equipements: set, rng: random.Random) -> str:
    dpe = rng.choices([d for d, _ in DPE_PONDERATION],
                      weights=[p for _, p in DPE_PONDERATION])[0]
    if "solaire" in equipements and dpe in ("F", "G"):
        dpe = "C"
    return dpe


def generer_annonce(i: int, rng: random.Random) -> dict:
    nom, cp, dept, region, lat, lon, alt, densite, prix_m2, extra = rng.choice(COMMUNES)
    type_bien, profil = rng.choice(list(TYPES.items()))

    surf = rng.randrange(*profil["surf"], 5)
    terrain = rng.randrange(*profil["terrain"], 50)
    pieces = max(2, round(surf / 32) + rng.randint(-1, 1))

    equipements = {e for e, proba in profil["equip"].items() if rng.random() < proba}
    etat, coef_etat, phrase_etat = rng.choice(ETATS)
    dpe = _choix_dpe(equipements, rng)

    prix = int(surf * prix_m2 * profil["facteur"] * coef_etat
               * rng.uniform(0.85, 1.15) // 1000 * 1000)

    # Risques : ceux de la commune, ajustés par le type de bien.
    risques = {}
    if extra.get("inondation") and (type_bien == "moulin" or rng.random() < 0.5):
        risques["inondation"] = True
    if type_bien == "moulin" and rng.random() < 0.7:
        risques["inondation"] = True
    if extra.get("argile"):
        risques["argile"] = extra["argile"]
    if extra.get("feu_foret") and rng.random() < 0.7:
        risques["feu_foret"] = True
    if extra.get("seveso_km") and rng.random() < 0.6:
        risques["seveso_km"] = extra["seveso_km"] + round(rng.uniform(-1, 3), 1)
    risques["source"] = "démo"

    # Description construite phrase par phrase (les équipements y figurent
    # en toutes lettres : c'est là que le moteur de score les détecte).
    dep_surface = rng.randrange(40, 160, 10)
    phrases = [
        f"{type_bien.capitalize()} {etat} de {surf} m² sur un terrain de "
        f"{terrain} m², à {nom} ({dept})."
    ]
    for cle in ("cave", "puits", "eau", "pluie", "bois", "solaire",
                "verger", "serre", "grange", "atelier"):
        if cle in equipements:
            phrases.append(rng.choice(PHRASES[cle]).format(dep=dep_surface))
    if phrase_etat:
        phrases.append(phrase_etat)
    phrases.append(f"DPE : {dpe}.")

    # Titre : le type, un ou deux atouts, la commune.
    atouts = []
    if "cave" in equipements:
        atouts.append("cave")
    if "puits" in equipements:
        atouts.append("puits")
    if not atouts and "grange" in equipements:
        atouts.append("dépendances")
    if not atouts and terrain >= 5000:
        atouts.append("grand terrain")
    milieu = f" avec {' et '.join(atouts)}" if atouts else f" de {surf} m²"
    titre = f"{type_bien.capitalize()}{milieu} — {nom} ({cp[:2]})"

    return {
        "id": f"demo-{i:03d}",
        "source": "démo",
        "url": "",
        "agence": AGENCES_DEMO.get(region, "Agence locale · démo"),
        "agence_url": "",
        "titre": titre,
        "description": " ".join(phrases),
        "type_bien": type_bien,
        "prix": prix,
        "surface_m2": surf,
        "terrain_m2": terrain,
        "pieces": pieces,
        "commune": nom,
        "code_postal": cp,
        "departement": dept,
        "region": region,
        "lat": round(lat + rng.uniform(-0.02, 0.02), 4),
        "lon": round(lon + rng.uniform(-0.02, 0.02), 4),
        "altitude": alt + rng.randint(-15, 25),
        "densite_hab_km2": densite,
        "dpe": dpe,
        "risques": risques,
    }


# Trois annonces « vitrines » écrites à la main pour illustrer les extrêmes.
VITRINES = [
    {
        "id": "demo-901", "source": "démo", "url": "",
        "agence": "Terres du Perche · démo", "agence_url": "",
        "titre": "Fermette autonome avec cave, puits et verger — Bellême (61)",
        "description": (
            "Fermette percheronne rénovée de 140 m² sur un terrain clos de "
            "7 500 m². Belle cave voûtée en pierre, saine et fraîche. Puits "
            "en état de fonctionnement et cuve de récupération d'eau de pluie. "
            "Verger d'arbres fruitiers, grand potager et serre. Poêle à bois "
            "récent et panneaux solaires photovoltaïques en autoconsommation. "
            "Grange attenante de 90 m² et atelier. Hameau très calme à 5 "
            "minutes de Bellême. DPE : C."
        ),
        "type_bien": "fermette", "prix": 285000, "surface_m2": 140,
        "terrain_m2": 7500, "pieces": 5, "commune": "Bellême",
        "code_postal": "61130", "departement": "Orne", "region": "Normandie",
        "lat": 48.381, "lon": 0.547, "altitude": 225, "densite_hab_km2": 45,
        "dpe": "C", "risques": {"source": "démo"},
    },
    {
        "id": "demo-902", "source": "démo", "url": "",
        "agence": "Morvan Propriétés · démo", "agence_url": "",
        "titre": "Ancien moulin au bord de l'eau — Joigny (89)",
        "description": (
            "Ancien moulin de 210 m² sur 9 000 m² traversés par la rivière. "
            "Cave, cheminée avec insert, dépendances. Cadre exceptionnel au "
            "bord de l'eau ; une partie de la parcelle est classée en zone "
            "inondable. Travaux à prévoir. DPE : E."
        ),
        "type_bien": "moulin", "prix": 320000, "surface_m2": 210,
        "terrain_m2": 9000, "pieces": 7, "commune": "Joigny",
        "code_postal": "89300", "departement": "Yonne",
        "region": "Bourgogne-Franche-Comté",
        "lat": 47.975, "lon": 3.410, "altitude": 85, "densite_hab_km2": 190,
        "dpe": "E", "risques": {"inondation": True, "source": "démo"},
    },
    {
        "id": "demo-903", "source": "démo", "url": "",
        "agence": "Sologne & Beauce Immobilier · démo", "agence_url": "",
        "titre": "Pavillon des années 80 — Bonneval (28)",
        "description": (
            "Pavillon de plain-pied de 95 m² sur une parcelle de 450 m² en "
            "lotissement, proche du centre de Bonneval. Chauffage électrique. "
            "Secteur concerné par le retrait-gonflement des argiles. "
            "DPE : F."
        ),
        "type_bien": "pavillon", "prix": 148000, "surface_m2": 95,
        "terrain_m2": 450, "pieces": 4, "commune": "Bonneval",
        "code_postal": "28800", "departement": "Eure-et-Loir",
        "region": "Centre-Val de Loire",
        "lat": 48.180, "lon": 1.390, "altitude": 128, "densite_hab_km2": 100,
        "dpe": "F", "risques": {"argile": 2, "source": "démo"},
    },
]


def generer_annonces() -> list[dict]:
    """Renvoie le jeu de démonstration complet (toujours identique, graine fixe)."""
    rng = random.Random(42)
    return [generer_annonce(i, rng) for i in range(1, 73)] + [dict(v) for v in VITRINES]
