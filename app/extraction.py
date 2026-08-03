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


def _image(noeud: dict) -> str | None:
    """Première photo : schema.org `image` (URL, liste, ou ImageObject)."""
    img = noeud.get("image") or noeud.get("photo")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url") or img.get("contentUrl")
    return img if isinstance(img, str) and img.startswith("http") else None


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
    return {
        "titre": titre,
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
        annonce["photo"] = metas["og:image"]
    if "prix" not in annonce:
        prix_meta = metas.get("product:price:amount") or metas.get("og:price:amount")
        if prix_meta:
            annonce["prix"] = _num(prix_meta)

    # 3. dernier recours : repères dans le texte visible
    texte = None
    if "prix" not in annonce or "surface_m2" not in annonce:
        texte = _texte_visible(html)
    if "prix" not in annonce and texte:
        m = RE_PRIX.search(texte)
        if m:
            annonce["prix"] = _num(m.group(1))
    if "surface_m2" not in annonce and texte:
        m = RE_SURFACE.search(f"{annonce.get('titre', '')} {texte}")
        if m:
            annonce["surface_m2"] = _num(m.group(1))
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

    if not annonce.get("prix") and not annonce.get("surface_m2"):
        return None

    annonce["source"] = source
    annonce["url"] = url
    annonce["agence"] = agence
    annonce["agence_url"] = agence_url
    annonce.setdefault("type_bien", "maison")
    if not annonce.get("titre"):
        annonce["titre"] = (agence or "Annonce") + " — bien à vendre"
    return annonce
