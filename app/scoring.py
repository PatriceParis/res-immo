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
    # --- critères de résilience ajoutés ---
    # Habitat troglodyte : inertie thermique + abri. Au-delà du mot savant, on
    # reconnaît le vocabulaire du pays du tuffeau (vallée du Loir, Vendômois),
    # où l'on dit « cave demeurante » pour une cave habitée.
    "troglodyte": (
        r"troglodyt|caves? demeurantes?|demeurante"
        r"|creuse\w* dans (la roche|le coteau|le tuffeau|la falaise|le rocher)"
        r"|habitat de coteau|maisons? de coteau"
    ),
    "source": r"\bsources?\b|captage|resurgence",
    "prairie": r"prairies?|paturages?|patures?|pacages?|herbages?|\bfoin\b",
    "poulailler": r"poulaillers?|clapiers?",
    "vigne": r"\bvignes?\b|vignoble",
    "ruches": r"ruches?|apicult",
    "pierre": r"\bpierres?\b|tuffeau|colombages?|torchis",   # inertie thermique
    "pompe_chaleur": r"pompe a chaleur|geothermie|aerothermie",
    "assainissement": r"assainissement autonome|phytoepuration|toilettes seches",
    "isolement": r"hameau|sans vis-a-vis|pleine campagne|a l'ecart|pleine nature",
    "autonomie": r"\bautonom",
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
    """12 points. Un puits est un vrai plus, mais peu discriminant en pratique :
    les annonces d'agences ne le mentionnent quasiment jamais (0 sur nos 49
    biens réels). Lui donner un poids énorme ne trierait rien — ça ne ferait
    que tasser tout le monde vers le bas. Il vaut donc un bon bonus, pas un
    critère décisif ; c'est un point à vérifier en visite."""
    points = 0
    if f.get("puits"):
        points += 6
    if f.get("source"):
        points += 4      # source / captage : eau gravitaire autonome
    if f.get("recuperation_pluie"):
        points += 3
    if f.get("eau_proximite"):
        points += 3
    return min(points, 12)


def _pilier_abri(f: dict) -> float:
    """18 points. La cave est l'atout signature de l'application — et elle est
    réellement mentionnée dans les annonces, donc elle trie vraiment."""
    points = 0
    if f.get("troglodyte"):
        points += 8      # habitat troglodyte : abri enterré, frais, cellier naturel
    if f.get("cave"):
        points += 9
    if f.get("grange_dependance"):
        points += 5
    if f.get("atelier"):
        points += 3
    return min(points, 18)


def _pilier_energie(f: dict, dpe: str | None) -> float:
    """17 points. Le chauffage au bois est très souvent indiqué (poêle, insert,
    cheminée) : c'est un critère lisible dans les annonces."""
    points = 0
    if f.get("bois"):
        points += 7
    if f.get("solaire"):
        points += 5
    if f.get("pompe_chaleur"):
        points += 3
    if f.get("troglodyte") or f.get("pierre"):
        points += 3      # inertie thermique : frais l'été, tempéré l'hiver
    if dpe in ("A", "B"):
        points += 5
    elif dpe == "C":
        points += 3
    return min(points, 17)


def _pilier_alimentation(f: dict, terrain_m2: float | None) -> float:
    """Capacité à produire sa nourriture : de l'espace (terrain) ET/OU des
    aménagements nourriciers (potager, verger, poulailler, vigne, ruches,
    pâture). Ainsi un bien sans grand terrain mais bien équipé marque des points,
    et un bien au vaste terrain aussi — voir docs/CRITERES.md."""
    points = 0
    terrain = terrain_m2 or 0
    if terrain >= 10_000:        # espace cultivable / élevage
        points += 8
    elif terrain >= 5_000:
        points += 6
    elif terrain >= 2_500:
        points += 4
    elif terrain >= 1_000:
        points += 2
    if f.get("verger_potager"):
        points += 4             # déjà nourricier
    if f.get("prairie"):
        points += 3             # pâture : élevage, foin
    if f.get("serre"):
        points += 2
    if f.get("poulailler"):
        points += 2
    if f.get("vigne"):
        points += 2
    if f.get("ruches"):
        points += 2
    return min(points, 18)


def _pilier_risques(r: dict) -> float:
    """Part de 20 points, puis retire des points par risque identifié.

    Deux portées, à ne pas confondre :
      - `inondation` / `feu_foret` : le BIEN est exposé (zonage à l'adresse) →
        pénalité pleine ;
      - `*_commune` (Géorisques) : le risque est seulement **documenté sur la
        commune**. Presque toute commune française a une rivière, un zonage
        sismique et un potentiel radon : pénaliser pleinement reviendrait à
        pénaliser tout le monde. On retire peu, et on l'affiche comme un point
        à vérifier à l'adresse.
    """
    points = 15.0
    if r.get("inondation"):
        points -= 8
    elif r.get("inondation_commune"):
        points -= 2
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
    elif r.get("feu_foret_commune"):
        points -= 1
    return max(points, 0)


def _pilier_situation(altitude, densite, temps_min, f=None, train=None) -> float:
    """20 points. C'est le pilier le mieux renseigné : densité, altitude, temps
    de route et gare la plus proche sont calculés en open data pour *chaque*
    bien, sans dépendre de ce que l'agence a bien voulu écrire. Il mérite donc
    un poids important — c'est lui qui trie réellement les terroirs."""
    points = 0
    if altitude is not None:
        if altitude >= 200:
            points += 3
        elif altitude >= 100:
            points += 2
    if densite is None:
        points += 2  # inconnue : valeur neutre
    elif densite < 30:
        points += 7
    elif densite < 80:
        points += 5
    elif densite < 300:
        points += 2
    if f and f.get("isolement"):
        points += 2  # hameau, à l'écart, pleine campagne
    if temps_min is not None:
        if temps_min <= 90:
            points += 6
        elif temps_min <= 150:
            points += 4
        elif temps_min <= 210:
            points += 2
    # Accessible SANS VOITURE : une gare proche reste utilisable en cas de
    # pénurie de carburant, et rend le repli compatible avec un travail à Paris.
    if train:
        # Attention : « train.get("km") or 99 » vaut 99 quand km == 0.0 —
        # une gare DANS la commune se retrouvait privée de son bonus.
        minutes = train.get("minutes_paris")
        km = train.get("km")
        km = 99 if km is None else km
        if minutes is not None and km <= 15:
            if minutes <= 60:
                points += 4      # ex. Vendôme (42 min), Château-Thierry (50 min)
            elif minutes <= 90:
                points += 3      # ex. Noyon (65 min)
            elif minutes <= 120:
                points += 2
        elif minutes is not None:  # gare un peu plus loin (15–25 km)
            points += 1
    return min(points, 20)


MAX_PILIERS = {
    "eau": 12,
    "abri": 18,
    "energie": 17,
    "alimentation": 18,
    "risques": 15,
    "situation": 20,
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
    if f.get("troglodyte"):
        badges.append("Habitat troglodyte")
    if f.get("source"):
        badges.append("Source / captage")
    if f.get("prairie"):
        badges.append("Prairie / pâture")
    if f.get("poulailler"):
        badges.append("Poulailler")
    if f.get("vigne"):
        badges.append("Vigne")
    if f.get("ruches"):
        badges.append("Ruches")
    if f.get("pompe_chaleur"):
        badges.append("Pompe à chaleur")
    if f.get("pierre"):
        badges.append("Bâti pierre (inertie)")
    if f.get("autonomie"):
        badges.append("Orienté autonomie")
    if f.get("isolement"):
        badges.append("Hameau isolé")
    terrain = annonce.get("terrain_m2") or 0
    if terrain >= 2_500:
        badges.append(f"Grand terrain ({int(terrain):,} m²)".replace(",", " "))
    densite = annonce.get("densite_hab_km2")
    if densite is not None and densite < 80:
        badges.append("Zone peu dense")
    temps = annonce.get("temps_voiture_min")
    if temps is not None and temps <= 120:
        badges.append("À moins de 2 h de Paris")
    train = annonce.get("train")
    if (train and (train.get("km") if train.get("km") is not None else 99) <= 15
            and train.get("minutes_paris") is not None):
        badges.append(f"Gare à {train['km']} km · Paris en {train['minutes_paris']} min")
    if piliers["risques"]["points"] >= 18:
        badges.append("Faible exposition aux risques")
    return badges


def _alertes(r: dict, dpe: str | None) -> list[str]:
    """Alertes fortes : le bien est concerné. Voir `_vigilances` pour le reste."""
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


def _vigilances(r: dict) -> list[str]:
    """Risques documentés sur la COMMUNE (Géorisques) : à vérifier à l'adresse.

    Ce ne sont pas des défauts du bien : presque toute commune française est
    concernée par au moins l'un d'eux. On les affiche pour que l'acheteur pose
    la question au notaire (l'état des risques est obligatoire à la vente).
    """
    v = []
    if r.get("inondation_commune") and not r.get("inondation"):
        v.append("Inondation documentée sur la commune — à vérifier à l'adresse")
    if r.get("feu_foret_commune") and not r.get("feu_foret"):
        v.append("Feux de forêt documentés sur la commune")
    if r.get("radon_commune"):
        v.append("Potentiel radon sur la commune (fréquent dans le Massif armoricain)")
    if r.get("seisme_commune"):
        v.append("Zonage sismique communal (toute commune en a un)")
    if r.get("icpe_commune"):
        v.append("Installation classée (ICPE) recensée sur la commune")
    return v


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
            f,
            annonce.get("train"),
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
        "vigilances": _vigilances(r),
    }
