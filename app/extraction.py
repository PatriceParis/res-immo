"""Extraction d'une annonce depuis la page d'un site d'agence immobilière.

Idée directrice du POC « collecte via les agences » : les sites d'agences
sont conçus pour être référencés par Google, donc ils publient sur chaque
page d'annonce des **données structurées schema.org** au format JSON-LD
(balise <script type="application/ld+json">). Ces données sont propres,
stables et identiques d'un logiciel d'agence à l'autre — bien plus fiables
que d'analyser la mise en page HTML, qui change tout le temps.

Cette fonction transforme le HTML d'une page d'annonce en dictionnaire
« annonce brute » prêt pour app.chargement.preparer_annonce(). Elle essaie,
dans l'ordre :
  1. les blocs JSON-LD schema.org (RealEstateListing, Product, Residence…) ;
  2. à défaut, les balises OpenGraph (og:title, og:description, prix) ;
  3. en dernier recours, quelques repères dans le texte (prix en €, m²).

Volontairement sans dépendance externe : utilisable aussi bien dans un robot
Scrapy que dans un test hors-ligne.
"""

from __future__ import annotations

import json
import re
from collections import Counter

# Types schema.org qui désignent un bien immobilier ou une offre de vente.
TYPES_IMMO = {
    "realestatelisting", "residence", "house", "singlefamilyresidence",
    "apartment", "accommodation", "place", "product", "offer", "housing",
}

# @type → type de bien affiché dans l'application.
TYPE_VERS_BIEN = {
    "apartment": "appartement",
    "house": "maison",
    "singlefamilyresidence": "maison",
}

# Mots du titre qui précisent le type de bien (prioritaires sur le @type).
MOTS_TYPE = [
    ("longère", "longère"), ("corps de ferme", "corps de ferme"),
    ("fermette", "fermette"), ("ferme", "corps de ferme"),
    ("moulin", "moulin"), ("château", "château"), ("manoir", "manoir"),
    ("propriété", "propriété"), ("pavillon", "pavillon"),
    ("appartement", "appartement"), ("maison", "maison"),
]

RE_JSONLD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
RE_META = re.compile(
    r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
RE_META_INV = re.compile(  # variante : content avant property
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
RE_PRIX = re.compile(r"(\d[\d\s  .]{3,})\s*€")
RE_SURFACE = re.compile(r"(\d{2,4})\s*m[²2]\b", re.IGNORECASE)
RE_TERRAIN = re.compile(
    r"(?:terrain|parcelle|jardin)\D{0,30}?(\d[\d\s  ]{2,})\s*m[²2]", re.IGNORECASE)
RE_TERRAIN_HA = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:ha|hectares?)\b", re.IGNORECASE)
RE_PIECES = re.compile(r"(\d{1,2})\s*pi[eè]ces?", re.IGNORECASE)
RE_DPE = re.compile(r"\b([A-G])\b")
# Code postal de France métropolitaine (01000–95999, Corse comprise).
RE_CP = re.compile(r"\b((?:0[1-9]|[1-8]\d|9[0-5])\d{3})\b")


def _code_postal(titre: str, texte: str) -> str | None:
    """Repère le code postal du bien : priorité au titre (souvent « Ville
    (61130) »), sinon le CP le plus fréquent du texte — c'est celui du bien,
    pas une adresse d'agence en pied de page."""
    m = RE_CP.search(titre or "")
    if m:
        return m.group(1)
    trouves = RE_CP.findall(texte or "")
    return Counter(trouves).most_common(1)[0][0] if trouves else None


def _num(x):
    """Coerce '7 500 m²', '140,5', 140 → nombre (int si entier), sinon None."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return x
    s = str(x).replace(" ", "").replace(" ", "").replace(" ", "")
    m = re.search(r"-?\d+(?:[.,]\d+)?", s)
    if not m:
        return None
    valeur = float(m.group().replace(",", "."))
    return int(valeur) if valeur.is_integer() else valeur


def _types(noeud) -> set[str]:
    t = noeud.get("@type") if isinstance(noeud, dict) else None
    if isinstance(t, str):
        return {t.lower()}
    if isinstance(t, list):
        return {str(x).lower() for x in t}
    return set()


def _aplatir(data):
    """Renvoie tous les objets JSON-LD, en dépliant @graph et les listes."""
    resultats = []
    pile = [data]
    while pile:
        courant = pile.pop()
        if isinstance(courant, list):
            pile.extend(courant)
        elif isinstance(courant, dict):
            resultats.append(courant)
            if isinstance(courant.get("@graph"), list):
                pile.extend(courant["@graph"])
    return resultats


def _blocs_jsonld(html: str) -> list[dict]:
    blocs = []
    for brut in RE_JSONLD.findall(html):
        texte = brut.strip().rstrip(";")
        try:
            blocs.extend(_aplatir(json.loads(texte)))
        except (json.JSONDecodeError, ValueError):
            continue
    return blocs


def _premier(noeud: dict, *cles):
    for cle in cles:
        if noeud.get(cle) not in (None, "", []):
            return noeud[cle]
    return None


def _valeur_quantite(v):
    """QuantitativeValue {value:..} / nombre / chaîne → nombre."""
    if isinstance(v, dict):
        return _num(_premier(v, "value", "@value"))
    return _num(v)


def _offre(noeud: dict) -> dict:
    offre = noeud.get("offers") or noeud.get("offer") or {}
    if isinstance(offre, list):
        offre = offre[0] if offre else {}
    return offre if isinstance(offre, dict) else {}


def _proprietes(noeud: dict) -> list[dict]:
    props = noeud.get("additionalProperty") or []
    if isinstance(props, dict):
        props = [props]
    return [p for p in props if isinstance(p, dict)]


def _cherche_propriete(props: list[dict], *motifs: str):
    for p in props:
        nom = str(_premier(p, "name", "propertyID") or "").lower()
        if any(m in nom for m in motifs):
            return _premier(p, "value", "unitText")
    return None


def _adresse(noeud: dict) -> dict:
    adr = noeud.get("address")
    if isinstance(adr, list):
        adr = adr[0] if adr else {}
    return adr if isinstance(adr, dict) else {}


def _url_img(u) -> str | None:
    """Normalise une URL d'image en absolu https (gère le protocol-relative //)."""
    if not isinstance(u, str):
        return None
    u = u.strip()
    if u.startswith("//"):        # ex. //cdn.agence.fr/photo.jpg
        return "https:" + u
    if u.startswith("http://"):   # force https quand c'est possible
        return "https://" + u[len("http://"):]
    if u.startswith("https://"):
        return u
    return None


def _image(noeud: dict) -> str | None:
    """Première photo : schema.org `image` (URL, liste, ou ImageObject)."""
    img = noeud.get("image") or noeud.get("photo")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url") or img.get("contentUrl")
    return _url_img(img)


def _geo(noeud: dict):
    geo = noeud.get("geo")
    if isinstance(geo, list):
        geo = geo[0] if geo else {}
    if isinstance(geo, dict):
        return _num(_premier(geo, "latitude", "lat")), _num(_premier(geo, "longitude", "lon", "lng"))
    return None, None


def _type_bien(titre: str, types: set[str]) -> str:
    bas = (titre or "").lower()
    for mot, valeur in MOTS_TYPE:
        if mot in bas:
            return valeur
    for t in types:
        if t in TYPE_VERS_BIEN:
            return TYPE_VERS_BIEN[t]
    return "maison"


def _metas(html: str) -> dict:
    metas = {}
    for cle, val in RE_META.findall(html):
        metas.setdefault(cle.lower(), val)
    for val, cle in RE_META_INV.findall(html):
        metas.setdefault(cle.lower(), val)
    return metas


def _depuis_jsonld(noeud: dict) -> dict:
    offre = _offre(noeud)
    props = _proprietes(noeud)
    adresse = _adresse(noeud)
    lat, lon = _geo(noeud)

    titre = str(_premier(noeud, "name", "headline") or "").strip()
    surface = _valeur_quantite(_premier(noeud, "floorSize", "size"))
    terrain = _num(_cherche_propriete(props, "terrain", "land", "parcelle"))
    dpe_txt = _cherche_propriete(props, "dpe", "énergie", "energie", "energy", "classe")
    dpe = None
    if dpe_txt:
        m = RE_DPE.search(str(dpe_txt).upper())
        dpe = m.group(1) if m else None

    cp = _premier(adresse, "postalCode")
    # Disponibilité schema.org : SoldOut / OutOfStock = bien déjà vendu.
    dispo = str(_premier(offre, "availability") or "").lower()
    return {
        "titre": titre,
        "vendu": any(x in dispo for x in ("soldout", "outofstock", "discontinued")) or None,
        "description": str(_premier(noeud, "description") or "").strip(),
        "prix": _num(_premier(offre, "price", "lowPrice") or _premier(noeud, "price")),
        "surface_m2": surface,
        "terrain_m2": terrain,
        "pieces": _valeur_quantite(_premier(noeud, "numberOfRooms", "numberOfRoomsTotal")),
        "commune": _premier(adresse, "addressLocality"),
        "code_postal": cp,
        "departement": str(cp)[:2] if cp else None,
        "lat": lat,
        "lon": lon,
        "dpe": dpe,
        "photo": _image(noeud),
        "type_bien": _type_bien(titre, _types(noeud)),
    }


def _texte_visible(html: str) -> str:
    sans_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sans_script))


def extraire_annonce(html: str, url: str, source: str,
                     agence: str | None = None, agence_url: str | None = None) -> dict | None:
    """HTML d'une page d'agence → dict annonce brute, ou None si inexploitable.

    Le résultat est considéré valable s'il possède au moins un prix ou une
    surface (sinon la page n'est probablement pas une annonce).
    """
    annonce: dict = {}

    # 1. données structurées schema.org
    candidats = [n for n in _blocs_jsonld(html) if _types(n) & TYPES_IMMO]
    candidats.sort(key=lambda n: (n.get("offers") is None and n.get("price") is None))
    if candidats:
        annonce = {k: v for k, v in _depuis_jsonld(candidats[0]).items() if v not in (None, "")}

    # 2. compléments OpenGraph / meta
    metas = _metas(html)
    annonce.setdefault("titre", metas.get("og:title") or "")
    annonce.setdefault("description", metas.get("og:description") or "")
    if not annonce.get("photo") and metas.get("og:image"):
        annonce["photo"] = _url_img(metas["og:image"])
    if "prix" not in annonce:
        prix_meta = metas.get("product:price:amount") or metas.get("og:price:amount")
        if prix_meta:
            annonce["prix"] = _num(prix_meta)

    # 3. dernier recours : repères dans le texte visible
    texte = None
    if "prix" not in annonce or "surface_m2" not in annonce:
        texte = _texte_visible(html)
    if "prix" not in annonce and texte:
        for m in RE_PRIX.finditer(texte):          # 1er montant plausible
            val = _num(m.group(1))
            if val and 15_000 <= val <= 5_000_000:  # sous 15 000 € : réf., pas un prix
                annonce["prix"] = val
                break
    if "surface_m2" not in annonce and texte:
        for m in RE_SURFACE.finditer(f"{annonce.get('titre', '')} {texte}"):
            val = _num(m.group(1))
            if val and 8 <= val <= 800:            # surface habitable plausible
                annonce["surface_m2"] = val
                break
    if "terrain_m2" not in annonce and texte:
        m = RE_TERRAIN.search(texte)
        if m:
            annonce["terrain_m2"] = _num(m.group(1))
        else:
            m = RE_TERRAIN_HA.search(texte)
            if m:
                annonce["terrain_m2"] = int(float(m.group(1).replace(",", ".")) * 10_000)
    if "pieces" not in annonce and texte:
        m = RE_PIECES.search(f"{annonce.get('titre', '')} {texte}")
        if m:
            annonce["pieces"] = _num(m.group(1))

    # Nettoyage du titre (entités HTML, espaces multiples).
    if annonce.get("titre"):
        titre_propre = (annonce["titre"].replace("&nbsp;", " ")
                        .replace("&amp;", "&").replace("&#039;", "'"))
        annonce["titre"] = re.sub(r"\s+", " ", titre_propre).strip()

    # Bornes de bon sens : écarte les valeurs aberrantes issues d'un mauvais
    # repérage dans le texte (n° de référence pris pour un prix, terrain pris
    # pour la surface habitable…).
    prix = annonce.get("prix")
    if prix is not None and not (3_000 <= prix <= 5_000_000):
        annonce["prix"] = None
    surface = annonce.get("surface_m2")
    if surface is not None and not (8 <= surface <= 800):
        annonce["surface_m2"] = None
    terrain = annonce.get("terrain_m2")
    if terrain is not None and not (10 <= terrain <= 2_000_000):
        annonce["terrain_m2"] = None

    if not annonce.get("prix") and not annonce.get("surface_m2"):
        return None

    # Texte complet de la page pour la détection des critères de résilience
    # (les descriptions schema.org sont souvent trop courtes) et pour repérer
    # le code postal quand schema.org ne fournit pas l'adresse.
    texte_complet = texte or _texte_visible(html)
    annonce["texte"] = texte_complet[:3000]

    if not annonce.get("code_postal"):
        cp = _code_postal(annonce.get("titre", ""), texte_complet)
        if cp:
            annonce["code_postal"] = cp
    if annonce.get("code_postal") and not annonce.get("departement"):
        annonce["departement"] = str(annonce["code_postal"])[:2]

    annonce["source"] = source
    annonce["url"] = url
    annonce["agence"] = agence
    annonce["agence_url"] = agence_url
    annonce.setdefault("type_bien", "maison")
    if not annonce.get("titre"):
        annonce["titre"] = (agence or "Annonce") + " — bien à vendre"
    return annonce
