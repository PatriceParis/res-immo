"""Découverte automatique d'agences immobilières par zone géographique.

Pourquoi pas un annuaire de réseau (IAD, Orpi, FNAIM…) ? Parce qu'il faudrait
deviner et suivre la structure HTML de chaque annuaire, qui change sans
prévenir. **OpenStreetMap** recense les agences immobilières comme n'importe
quel commerce (`office=estate_agent`, `shop=estate_agent`) avec leur nom et
souvent leur **site web** : c'est de l'open data, interrogeable par rayon
autour d'une ville via l'API Overpass, sans anti-bot ni structure fragile.

Le chemin est donc :
  1. Overpass → agences (nom + site) autour de chaque ville visée ;
  2. sondage de chaque site : est-il joignable ? publie-t-il un sitemap avec
     des pages de biens ? des données schema.org ?
  3. les sites exploitables sont ajoutés à la liste de collecte.

Ce module ne contient que des fonctions pures (parsing, filtrage, score),
testables hors ligne ; les appels réseau sont dans
scripts/decouvrir_agences_osm.py.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Villes visées, avec le rayon de recherche. Ce sont les bassins accessibles
# en train depuis Paris, plus ceux déjà couverts qu'on veut densifier.
ZONES = [
    {"nom": "Château-Thierry", "lat": 49.0450, "lon": 3.4028, "rayon_km": 30},
    {"nom": "Soissons",        "lat": 49.3817, "lon": 3.3236, "rayon_km": 25},
    {"nom": "Noyon",           "lat": 49.5836, "lon": 3.0000, "rayon_km": 25},
    # Rayon porté de 25 à 30 km : seize biens du catalogue tombaient dans
    # l'anneau manquant. Élargir vaut mieux qu'ajouter un second cercle
    # à côté — deux centres voisins paient deux fois le même territoire.
    {"nom": "Compiègne",       "lat": 49.4179, "lon": 2.8261, "rayon_km": 30},
    {"nom": "Beauvais",        "lat": 49.4295, "lon": 2.0807, "rayon_km": 30},
    {"nom": "Vendôme",         "lat": 47.7931, "lon": 1.0656, "rayon_km": 30},
    {"nom": "Nogent-le-Rotrou", "lat": 48.3230, "lon": 0.8175, "rayon_km": 25},
    {"nom": "Sens",            "lat": 48.1977, "lon": 3.2836, "rayon_km": 25},
    # Vallées du Loir et du Cher : le pays du tuffeau, où l'habitat troglodyte
    # est courant. Une maison creusée dans le coteau reste fraîche l'été et
    # tempérée l'hiver — précisément ce qu'on cherche face aux canicules.
    # Toutes ces communes sont à 2 h 40 – 3 h 10 de Paris, en Centre-Val de
    # Loire : le troglodyte n'oblige donc pas à sortir du périmètre.
    {"nom": "Montoire-sur-le-Loir", "lat": 47.7539, "lon": 0.8672, "rayon_km": 30},
    {"nom": "Château-Renault",  "lat": 47.5919, "lon": 0.9114, "rayon_km": 25},
    {"nom": "Montrichard",      "lat": 47.3428, "lon": 1.1892, "rayon_km": 25},
    {"nom": "Amboise",          "lat": 47.4131, "lon": 0.9821, "rayon_km": 25},
    {"nom": "Vouvray",          "lat": 47.4108, "lon": 0.7967, "rayon_km": 20},
    # Yonne : la Puisaye et l'Auxerrois, à 2 h 30 de route et desservis depuis
    # Paris-Bercy (Sens 55 min, Joigny 75 min, Auxerre 1 h 45).
    {"nom": "Auxerre",          "lat": 47.7982, "lon": 3.5734, "rayon_km": 30},
    {"nom": "Toucy (Puisaye)",  "lat": 47.7333, "lon": 3.2944, "rayon_km": 25},
    {"nom": "Avallon",          "lat": 47.4900, "lon": 3.9086, "rayon_km": 25},
    # Saône-et-Loire : loin par la route (4 h 25) mais **1 h 20 de Paris par
    # Le Creusot TGV**. C'est exactement ce que le pilier « accès sans
    # voiture » est fait pour reconnaître.
    {"nom": "Chalon-sur-Saône", "lat": 46.7806, "lon": 4.8536, "rayon_km": 30},
    {"nom": "Le Creusot",       "lat": 46.8003, "lon": 4.4331, "rayon_km": 30},

    # Les vingt-cinq zones qui suivent comblent le reste du périmètre. Les
    # dix-neuf premières ne couvraient que HUIT des trente-six départements
    # visés : la présence des autres au catalogue était accidentelle — le
    # Calvados et la Meurthe-et-Moselle, nos deux mieux pourvus avec 174 et
    # 171 biens, n'avaient aucune zone. Leurs agences sont arrivées par des
    # ajouts à la main ou par les mandataires, jamais par la découverte.
    #
    # Chaque centre est une COMMUNE RÉELLE du département, prise dans le
    # catalogue : ses coordonnées viennent de la Base Adresse Nationale, donc
    # vérifiées. Vesoul fait seule exception — la Haute-Saône est dans le
    # périmètre mais n'a aucun bien, donc aucune coordonnée à emprunter. Les
    # vingt-cinq distances à Paris ont été contrôlées avec
    # app.geo.distance_paris_km : toutes sous les 350 km de l'application.
    {"nom": "Acquigny (27)",            "lat": 49.1677, "lon": 1.1813, "rayon_km": 30},
    {"nom": "Amiens (80)",              "lat": 49.9030, "lon": 2.2926, "rayon_km": 30},
    {"nom": "Baugy (18)",               "lat": 47.0771, "lon": 2.7481, "rayon_km": 30},
    {"nom": "Champéon (53)",            "lat": 48.3591, "lon": -0.5182, "rayon_km": 30},
    {"nom": "Charny-sur-Meuse (55)",    "lat": 49.2068, "lon": 5.3602, "rayon_km": 30},
    {"nom": "Châteauneuf-sur-Loire (45)", "lat": 47.8727, "lon": 2.2232, "rayon_km": 30},
    {"nom": "Gouville-sur-Mer (50)",    "lat": 49.1090, "lon": -1.5336, "rayon_km": 30},
    {"nom": "La Charité-sur-Loire (58)", "lat": 47.1823, "lon": 3.0315, "rayon_km": 30},
    {"nom": "Le Poinçonnet (36)",       "lat": 46.7785, "lon": 1.7112, "rayon_km": 30},
    {"nom": "Montreuil (62)",           "lat": 50.4745, "lon": 1.7800, "rayon_km": 30},
    {"nom": "Nouvion-sur-Meuse (08)",   "lat": 49.7024, "lon": 4.7932, "rayon_km": 30},
    {"nom": "Orchies (59)",             "lat": 50.4705, "lon": 3.2408, "rayon_km": 30},
    {"nom": "Pompey (54)",              "lat": 48.7710, "lon": 6.1249, "rayon_km": 30},
    {"nom": "Ranville (14)",            "lat": 49.2333, "lon": -0.2500, "rayon_km": 30},
    {"nom": "Roche-lez-Beaupré (25)",   "lat": 47.2772, "lon": 6.1080, "rayon_km": 30},
    {"nom": "Saint-André-les-Vergers (10)", "lat": 48.2772, "lon": 4.0509, "rayon_km": 30},
    {"nom": "Saint-Romain-de-Colbosc (76)", "lat": 49.5300, "lon": 0.3648, "rayon_km": 30},
    {"nom": "Sainte-Sabine (21)",       "lat": 47.1912, "lon": 4.6237, "rayon_km": 30},
    {"nom": "Tavaux (39)",              "lat": 47.0433, "lon": 5.4117, "rayon_km": 30},
    {"nom": "Vesoul (70)",              "lat": 47.6236, "lon": 6.1556, "rayon_km": 30},
    {"nom": "Vigy (57)",                "lat": 49.2084, "lon": 6.2980, "rayon_km": 30},
    {"nom": "Villiers-le-Sec (52)",     "lat": 48.1065, "lon": 5.0661, "rayon_km": 30},
    {"nom": "Écommoy (72)",             "lat": 47.8267, "lon": 0.2868, "rayon_km": 30},
    {"nom": "Épernay (51)",             "lat": 49.0402, "lon": 3.9605, "rayon_km": 30},
    {"nom": "Épinal (88)",              "lat": 48.1702, "lon": 6.4849, "rayon_km": 30},

    # Les quinze zones qui suivent ne sont pas devinées : elles sont CALCULÉES
    # sur les biens que le catalogue contient déjà et qu'aucune zone ne
    # couvrait. Mesuré le 17 août : 443 des 1 459 biens servis et géolocalisés
    # — trente pour cent — étaient hors de toute zone. Pas dans des lieux
    # obscurs : Rouen, Bayeux, Lisieux, Charolles, Digoin. Ils étaient arrivés
    # par les réseaux de mandataires, qui travaillent par département, ou par
    # des ajouts à la main. La découverte par OpenStreetMap, elle, n'avait
    # jamais regardé là — et n'y trouvait donc aucune agence locale.
    #
    # Le placement est glouton : on prend la commune qui couvre le plus de
    # biens orphelins, on la retire du décompte, on recommence. Les
    # coordonnées viennent du catalogue, donc de la Base Adresse Nationale.
    # Résultat mesuré : l'angle mort tombe de 443 à 147 biens.
    {"nom": "Vitry-en-Charollais (71)",  "lat": 46.4607, "lon": 4.0676, "rayon_km": 30},
    {"nom": "Le Trait (76)",             "lat": 49.4842, "lon": 0.8023, "rayon_km": 30},
    {"nom": "Villers-Bocage (14)",       "lat": 49.0798, "lon": -0.6560, "rayon_km": 30},
    {"nom": "Saint-Georges-sur-Eure (28)", "lat": 48.4178, "lon": 1.3555, "rayon_km": 30},
    {"nom": "Plottes (71)",              "lat": 46.5431, "lon": 4.8875, "rayon_km": 30},
    {"nom": "Lignières (18)",            "lat": 46.7618, "lon": 2.1959, "rayon_km": 30},
    {"nom": "Saint-Valery-sur-Somme (80)", "lat": 50.1751, "lon": 1.6320, "rayon_km": 30},
    {"nom": "Broglie (27)",              "lat": 49.0012, "lon": 0.5316, "rayon_km": 30},
    {"nom": "Mussy-sur-Seine (10)",      "lat": 47.9794, "lon": 4.4972, "rayon_km": 30},
    {"nom": "Villerupt (54)",            "lat": 49.4644, "lon": 5.9269, "rayon_km": 30},
    {"nom": "Rosières-en-Santerre (80)", "lat": 49.8162, "lon": 2.7018, "rayon_km": 30},
    {"nom": "Thénioux (18)",             "lat": 47.2610, "lon": 1.9396, "rayon_km": 30},
    {"nom": "Crouzilles (37)",           "lat": 47.1309, "lon": 0.4787, "rayon_km": 30},
    # Le bassin de Montbard, ajouté nommément et non par le calcul : le
    # catalogue n'y contient aucun bien, donc aucun orphelin à couvrir — et
    # c'est précisément le symptôme. Montbard est à 1 h de Paris par TGV, ce
    # que le pilier « accès sans voiture » est fait pour reconnaître, et une
    # agence de Venarey-les-Laumes y vendait une maison que nous ne voyions
    # pas. Le centre est Saint-Rémy, à quatre kilomètres, parce que ses
    # coordonnées sont dans notre catalogue donc vérifiées — celles de
    # Montbard, non.
    {"nom": "Montbard – Saint-Rémy (21)", "lat": 47.6450, "lon": 4.2974, "rayon_km": 30},
]

# Portails nationaux et réseaux sociaux : ce ne sont pas des sites d'agence
# locale, et la plupart bloquent la collecte automatisée.
PORTAILS_EXCLUS = {
    "seloger.com", "bienici.com", "leboncoin.fr", "pap.fr", "logic-immo.com",
    "avendrealouer.fr", "figaro.fr", "ouestfrance-immo.com", "paruvendu.fr",
    "facebook.com", "google.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "youtube.com", "wa.me", "immobilier.notaires.fr", "meilleursagents.com",
}

# Sites « tête de réseau » : OpenStreetMap donne souvent l'adresse nationale
# pour une agence locale de franchise. Y collecter ramènerait des biens de
# toute la France — hors sujet, et le budget de collecte y passerait entier.
# On exclut le domaine EXACT, mais on garde les déclinaisons locales
# (compiegne.arthurimmo.com, century21-vandome-crepy.com, quentimmo.fr…),
# qui sont, elles, de vraies agences de terrain.
RESEAUX_NATIONAUX = {
    "orpi.com", "laforet.com", "eraimmobilier.com", "era-immobilier.fr",
    "century21.fr", "guy-hoquet.com", "nestenn.com", "iadfrance.fr",
    "iad-france.fr", "stephaneplazaimmobilier.com", "ladresse.com",
    "humanimmobilier.fr", "arthurimmo.com", "sergic.com", "foncia.com",
    "citya.com", "square-habitat.fr", "squarehabitat.fr", "safti.fr", "capifrance.fr",
    "optimhome.com", "bellesdemeures.com", "proprieteslefigaro.com",
}

# Au-delà, ce n'est plus une agence de terroir mais un portail : une agence
# locale n'a pas des milliers de biens en vitrine. Garde-fou indépendant de
# la liste ci-dessus, qui ne peut pas être exhaustive.
PLAFOND_BIENS_LOCAL = 2000

# Indices d'une page de bien dans une URL (mêmes repères que le collecteur).
MOTIF_BIEN = re.compile(
    r"/(annonces?|biens?|vente|vendre|a-vendre|property|properties|nos-biens"
    r"|detail|ref|maison|propriete|achat)[-/]",
    re.IGNORECASE,
)


def requete_overpass(zone: dict) -> str:
    """Requête Overpass QL : les agences immobilières autour d'une ville."""
    rayon = int(zone["rayon_km"] * 1000)
    autour = f"(around:{rayon},{zone['lat']},{zone['lon']})"
    return (
        "[out:json][timeout:90];("
        f'node["office"="estate_agent"]{autour};'
        f'way["office"="estate_agent"]{autour};'
        f'node["shop"="estate_agent"]{autour};'
        f'way["shop"="estate_agent"]{autour};'
        ");out center tags;"
    )


def requete_overpass_departement(code: str) -> str:
    """Toutes les agences d'un DÉPARTEMENT, pas seulement autour d'une ville.

    Les 19 zones en cercle laissaient de côté tout ce qui n'était pas à moins
    de 25 ou 30 km d'un chef-lieu choisi à la main — c'est-à-dire l'essentiel
    de la campagne, précisément là où se trouvent les biens qu'on cherche. On
    interroge donc la limite administrative du département (admin_level 6 en
    France, portant le code INSEE).
    """
    return (
        "[out:json][timeout:180];"
        f'area["boundary"="administrative"]["admin_level"="6"]'
        f'["ref:INSEE"="{code}"]->.d;'
        '(node["office"="estate_agent"](area.d);'
        'way["office"="estate_agent"](area.d);'
        'node["shop"="estate_agent"](area.d);'
        'way["shop"="estate_agent"](area.d);'
        ");out center tags;"
    )


def domaine(url: str) -> str:
    """Domaine nu, sans www ni sous-chemin ('https://www.a.fr/x' → 'a.fr')."""
    if not url:
        return ""
    if "//" not in url:
        url = "https://" + url
    hote = (urlparse(url).netloc or "").lower().strip()
    return hote[4:] if hote.startswith("www.") else hote


def est_portail_exclu(url: str) -> bool:
    """True pour un portail national, un réseau social ou un domaine vide.

    Les portails sont exclus jusque dans leurs sous-domaines ; les têtes de
    réseau seulement sur le domaine exact, pour laisser passer les agences
    locales de franchise (compiegne.arthurimmo.com est une vraie agence,
    arthurimmo.com est le site national).
    """
    d = domaine(url)
    if not d or "." not in d:
        return True
    if any(d == p or d.endswith("." + p) for p in PORTAILS_EXCLUS):
        return True
    return d in RESEAUX_NATIONAUX


def agences_depuis_overpass(reponse: dict, zone_nom: str) -> list[dict]:
    """Réponse Overpass → agences {nom, site, zone}, dédoublonnées par domaine."""
    vues, agences = set(), []
    for element in (reponse or {}).get("elements", []):
        tags = element.get("tags") or {}
        site = (tags.get("website") or tags.get("contact:website")
                or tags.get("url") or "").strip()
        nom = (tags.get("name") or "").strip()
        if not site or not nom or est_portail_exclu(site):
            continue
        d = domaine(site)
        if d in vues:
            continue
        vues.add(d)
        agences.append({"nom": nom, "site": f"https://{d}", "zone": zone_nom})
    return agences


def agences_sans_site(reponse: dict, zone_nom: str) -> list[dict]:
    """Agences repérées par OpenStreetMap mais SANS site web déclaré.

    Elles étaient purement écartées. C'est pourtant la majorité des points :
    une agence de village a rarement pris la peine de renseigner son site dans
    OSM, ce qui ne veut pas dire qu'elle n'en a pas. On les conserve donc —
    avec leur commune et leur téléphone quand ils sont là — comme pistes à
    résoudre, et pour savoir ce qu'on ne couvre pas.
    """
    trouvees, vues = [], set()
    for element in (reponse or {}).get("elements", []):
        tags = element.get("tags") or {}
        nom = (tags.get("name") or "").strip()
        site = (tags.get("website") or tags.get("contact:website")
                or tags.get("url") or "").strip()
        if not nom or site:
            continue
        commune = (tags.get("addr:city") or "").strip()
        cle = (nom.lower(), commune.lower())
        if cle in vues:
            continue
        vues.add(cle)
        trouvees.append({
            "nom": nom,
            "commune": commune,
            "code_postal": (tags.get("addr:postcode") or "").strip(),
            "telephone": (tags.get("phone") or tags.get("contact:phone") or "").strip(),
            "zone": zone_nom,
        })
    return trouvees


def urls_de_biens(urls: list[str], hote: str) -> list[str]:
    """Parmi des URLs de sitemap, celles qui ressemblent à une page de bien."""
    gardees, vues = [], set()
    for u in urls or []:
        if not u or domaine(u) != domaine(hote):
            continue
        if MOTIF_BIEN.search(u) and u not in vues:
            vues.add(u)
            gardees.append(u)
    return gardees


def score_candidat(sonde: dict) -> int:
    """Note un site sondé : plus il expose de biens proprement, mieux c'est.

    Sert à trier les candidats — on branche d'abord ceux qui rapporteront le
    plus de biens exploitables, pas ceux dont le nom sonne bien.

    Un catalogue démesuré n'est PAS un bon signe : c'est un portail national
    (Orpi, ERA… : des dizaines de milliers de biens dans toute la France).
    Y collecter serait hors sujet et engloutirait le budget de collecte.
    """
    if not sonde.get("joignable"):
        return 0
    nb = sonde.get("nb_biens", 0)
    site = sonde.get("site")
    if nb > PLAFOND_BIENS_LOCAL or (site and est_portail_exclu(site)):
        return 0
    note = min(nb, 60)                                # jusqu'à 60 points
    if sonde.get("sitemap"):
        note += 20        # un sitemap = collecte fiable et peu coûteuse
    if sonde.get("schema_org"):
        note += 20        # données structurées = extraction propre
    return note


# Constructeurs de maisons neuves : ils vendent du terrain + plan, pas des
# biens existants. Une maison neuve de lotissement n'a ni cave, ni dépendance,
# ni terrain nourricier — l'inverse d'un refuge.
CONSTRUCTEURS = re.compile(
    r"maisons? (france confort|pierre|d'en france|balency|axcess|phenix|club)"
    r"|constructeur|maisons? neuves?|villas? club|trecobat|geoxia"
    # « Bourgogne Bâtir » a été branchée comme agence — OpenStreetMap la
    # classe office=estate_agent — et a livré 7 offres de construction
    # (« Maison + Terrain à Oslon », 55 000 €), toutes géolocalisées au siège
    # du constructeur. Un nom en « bâtir » ou « construction » suffit à s'en
    # méfier : on cherche des maisons existantes, pas des chantiers.
    r"|b[âa]tir\b|constructions?\b|maisons? \+ terrain",
    re.IGNORECASE,
)


def est_constructeur(nom: str) -> bool:
    """True pour un constructeur de maisons neuves (hors cible refuge)."""
    return bool(CONSTRUCTEURS.search(nom or ""))


def fusionner_rapports(ancien: list[dict], nouveau: list[dict]) -> list[dict]:
    """Cumule les sondages de plusieurs passes, en gardant le meilleur par site.

    L'API Overpass est capricieuse : d'une passe à l'autre, ce ne sont pas les
    mêmes zones qui répondent (Compiègne un coup, Vendôme le suivant). Écraser
    le rapport à chaque fois ferait perdre la moitié du travail. En cumulant,
    la couverture s'enrichit à chaque passage au lieu de faire du sur-place.
    """
    par_domaine: dict[str, dict] = {}
    for sonde in list(ancien or []) + list(nouveau or []):
        d = domaine(sonde.get("site", ""))
        if not d:
            continue
        garde = par_domaine.get(d)
        # Le sondage le plus concluant l'emporte (un site injoignable un jour
        # peut très bien répondre le lendemain).
        if garde is None or sonde.get("note", 0) > garde.get("note", 0):
            par_domaine[d] = sonde
    return sorted(par_domaine.values(), key=lambda s: -s.get("note", 0))


def fusionner(existantes: list[dict], candidates: list[dict],
              note_mini: int = 25) -> tuple[list[dict], list[dict]]:
    """Ajoute les candidates retenues aux agences déjà configurées.

    Renvoie (liste complète, nouvelles ajoutées). Le dédoublonnage se fait sur
    le domaine : une agence déjà suivie n'est jamais ajoutée deux fois.
    """
    connus = {domaine(a.get("site", "")) for a in existantes}
    ajoutees = []
    for c in sorted(candidates, key=lambda x: -x.get("note", 0)):
        d = domaine(c.get("site", ""))
        if not d or d in connus or c.get("note", 0) < note_mini:
            continue
        if est_constructeur(c.get("nom", "")):
            continue    # maisons neuves : pas de cave, pas de dépendances
        connus.add(d)
        ajoutees.append({
            "nom": c["nom"],
            "site": c["site"],
            "zone": c.get("zone", ""),
            "index": [],
            "max": 8,
            "pages": 45,
        })
    return existantes + ajoutees, ajoutees
