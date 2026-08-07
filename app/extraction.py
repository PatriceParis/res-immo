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

import html as html_
import json
import re
from collections import Counter
from urllib.parse import urljoin

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

# Ces mots doivent être des MOTS, pas des morceaux de mots : « Châteauroux »
# annonçait un château, et « Moulins » un moulin. On écarte aussi le mot suivi
# d'un trait d'union, qui trahit presque toujours un nom de commune
# (Château-Renault, Ferme-Neuve) plutôt que le type du bien.
RE_MOTS_TYPE = [
    (re.compile(rf"\b{re.escape(mot)}\b(?!-)"), valeur) for mot, valeur in MOTS_TYPE
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
# Les surfaces sont très souvent décimales dans les annonces (« 132,96 m² »,
# « 238.0 m2 »). Sans la partie décimale, « 132,96 m² » était lu **96 m²** et
# « 238.0 m2 » n'était pas reconnu du tout : de quoi fausser tous les prix
# au m², donc la comparaison au marché.
RE_SURFACE = re.compile(
    # Le nombre ne doit pas être la FIN d'un nombre plus grand : dans
    # « Terrain de 2 500 m² », « 500 m² » se lisait comme une surface
    # habitable, et supplantait les vrais 130 m² de la maison.
    r"(?<!\d)(?<!\d[\s\u00a0\u202f])(\d{2,4}(?:[.,]\d{1,2})?)\s*m[²2]\b",
    re.IGNORECASE)
RE_TERRAIN = re.compile(
    r"(?:terrain|parcelle|jardin)\D{0,30}?(\d[\d\s  ]{2,})\s*m[²2]", re.IGNORECASE)
RE_TERRAIN_HA = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:ha|hectares?)\b", re.IGNORECASE)
RE_PIECES = re.compile(r"(\d{1,2})\s*pi[eè]ces?", re.IGNORECASE)
RE_TITRE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
RE_DPE = re.compile(r"\b([A-G])\b")

# --- Diagnostic de performance énergétique (DPE) ------------------------------
# Le DPE est obligatoire dans toute annonce, mais sa lettre A–G est presque
# toujours portée par une IMAGE ou une étiquette stylée, pas par le texte : le
# lire dans le texte seul le manquait systématiquement (0 bien sur 72).
# On le cherche donc là où les sites le rangent réellement.
RE_DPE_CLASSE = re.compile(          # class="dpe-d", "energy-class-D", "etiquette-energie_C"
    r'class="[^"]*?(?:dpe|classe[-_ ]?energie|energy[-_ ]?class|etiquette[-_ ]?energ\w*)'
    r'[-_ ]?([a-g])(?![a-z0-9])', re.IGNORECASE)
RE_DPE_DATA = re.compile(            # data-dpe="D", data-classe-energie="C"
    r'data-(?:dpe|classe[-_]?energie|energie|energy)="\s*([a-g])\s*"', re.IGNORECASE)
RE_DPE_ALT = re.compile(             # alt="DPE D", title="Classe énergie : C"
    r'(?:alt|title)="[^"]{0,60}?(?:dpe|classe [ée]nerg\w*|[ée]tiquette [ée]nerg\w*)'
    r'[^"a-g]{0,12}?([a-g])(?![a-z0-9])"?', re.IGNORECASE)
# En texte, la lettre est TOUJOURS en majuscule sur une étiquette. L'exiger
# évite de lire « DPE a été réalisé » comme un DPE de classe A.
RE_DPE_TEXTE = re.compile(
    r'(?:DPE|[Cc]lasse [ée]nerg\w*|[ÉEée]tiquette [ée]nerg\w*|[Bb]ilan [ée]nerg\w*)'
    r'\s*(?:[:\-–]|\bde\b)?\s*([A-G])(?![A-Za-z0-9])')


def _dpe(html: str, texte: str) -> str | None:
    """Classe énergétique A–G du bien, cherchée dans l'ordre de fiabilité."""
    for motif in (RE_DPE_CLASSE, RE_DPE_DATA, RE_DPE_ALT):
        m = motif.search(html or "")
        if m:
            return m.group(1).upper()
    m = RE_DPE_TEXTE.search(texte or "")
    return m.group(1).upper() if m else None
# Code postal de France métropolitaine (01000–95999, Corse comprise).
RE_CP = re.compile(r"\b((?:0[1-9]|[1-8]\d|9[0-5])\d{3})\b")
# Numéros de référence d'annonce : « Ref. 23624 », « réf : 1077b », « n° 1580 ».
# Ils ressemblent à s'y méprendre à un code postal — « Hôtel particulier à
# Alençon - Ref. 23624 » se retrouvait géolocalisé dans la Creuse.
RE_REFERENCE = re.compile(r"(?:r[ée]f\.?(?:[ée]rence)?|n[°o]|lot)\s*:?\s*\d+", re.IGNORECASE)


# Bornes de prix au m² pour les terroirs ruraux visés. Au-delà, ce n'est pas
# le bien qui est hors norme : c'est une des deux valeurs qui est fausse.
PRIX_M2_MIN, PRIX_M2_MAX = 300, 8000


# Ce qui, juste avant un nombre en m², désigne du TERRAIN et non de
# l'habitable. Cas réels : « Surface 83,58 m² terrain 285 m² » et « Surface
# habitable (m²) 94 m² surface terrain 558 m² » — dans les deux, c'est le
# terrain qui ressortait comme surface habitable du bien.
RE_AVANT_TERRAIN = re.compile(
    r"(?:terrain|parcelle|jardin|cour|verger|prairie|p[âa]ture|potager)"
    r"[^.;]{0,18}$", re.IGNORECASE)


def _surfaces(texte: str) -> list[float]:
    """Toutes les surfaces habitables plausibles citées, dans l'ordre.

    Les surfaces annoncées comme du terrain sont écartées : elles passaient
    pour de l'habitable et, étant généralement plus grandes, l'emportaient au
    moment de choisir — `_surface_coherente` retient la plus grande des
    surfaces crédibles, et un terrain l'est souvent aussi.
    """
    texte = texte or ""
    vues, fin_precedente = [], 0
    for m in RE_SURFACE.finditer(texte):
        # On ne regarde en arrière que jusqu'à la surface précédente : sinon
        # « Terrain 500 m², maison 120 m² » verrait le mot « terrain » devant
        # les 120 m² de la maison et les écarterait à tort.
        debut = max(fin_precedente, m.start() - 40)
        qualifie_du_terrain = RE_AVANT_TERRAIN.search(texte[debut:m.start()])
        fin_precedente = m.end()
        val = _num(m.group(1))
        if not val or not (8 <= val <= 800) or val in vues:
            continue
        if qualifie_du_terrain:
            continue
        vues.append(val)
    return vues


def _surface_coherente(candidates: list[float], prix) -> float | None:
    """La surface qui donne un prix au m² crédible, à défaut la première.

    Sans ce garde-fou, on retenait la première surface rencontrée — souvent
    une pièce, une piscine ou une dépendance. Mieux vaut ne rien afficher
    qu'une surface qui rend le prix au m² absurde.
    """
    if not candidates:
        return None
    if not prix:
        return candidates[0]
    coherentes = [v for v in candidates if PRIX_M2_MIN <= prix / v <= PRIX_M2_MAX]
    # La plus grande des surfaces crédibles : l'habitable dépasse les annexes.
    return max(coherentes) if coherentes else None


def _code_postal(titre: str, texte: str) -> str | None:
    """Repère le code postal du bien : priorité au titre (souvent « Ville
    (61130) »), sinon le CP le plus fréquent du texte — c'est celui du bien,
    pas une adresse d'agence en pied de page."""
    titre = RE_REFERENCE.sub(" ", titre or "")
    texte = RE_REFERENCE.sub(" ", texte or "")
    m = RE_CP.search(titre)
    if m:
        return m.group(1)
    trouves = RE_CP.findall(texte)
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


def _url_img(u, base: str | None = None) -> str | None:
    """Normalise une URL d'image en absolu https.

    Les chemins RELATIFS (« /media/biens/2017-1.jpg ») étaient purement et
    simplement rejetés : une agence qui les publie ainsi n'avait aucune photo,
    alors que l'URL était là, à un `urljoin` près.
    """
    if not isinstance(u, str):
        return None
    # Une adresse lue dans du HTML arrive échappée : immo-ray sert
    # « image-get.inc.php?f=1024x550&amp;n=11665 ». Gardé tel quel, le
    # paramètre s'appellerait « amp;n » et le serveur renverrait autre chose
    # que la photo demandée.
    u = html_.unescape(u.strip())
    if not u or u.startswith("data:"):
        return None
    if u.startswith("//"):        # ex. //cdn.agence.fr/photo.jpg
        return "https:" + u
    if u.startswith("http://"):   # force https quand c'est possible
        return "https://" + u[len("http://"):]
    if u.startswith("https://"):
        return u
    if base:
        absolue = urljoin(base, u)
        return absolue if absolue.startswith("https://") else (
            "https://" + absolue[len("http://"):] if absolue.startswith("http://") else None)
    return None


def _image(noeud: dict, base: str | None = None) -> str | None:
    """Première photo : schema.org `image` (URL, liste, ou ImageObject)."""
    img = noeud.get("image") or noeud.get("photo")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url") or img.get("contentUrl")
    return _url_img(img, base)


# --- Photo de repli : les images de la page ---------------------------------
#
# Un quart des biens n'avait aucune photo, non parce que la page n'en montre
# pas, mais parce qu'on ne cherchait QUE dans schema.org et OpenGraph. Les
# sites qui ne publient ni l'un ni l'autre affichaient pourtant leurs clichés
# dans de simples <img>. On va donc les y chercher.

RE_BALISE_IMG = re.compile(r"<(?:img|source)\b[^>]*>", re.IGNORECASE)
RE_ATTRIBUT = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
RE_FOND_CSS = re.compile(r"background-image\s*:\s*url\(\s*['\"]?([^'\")]+)", re.IGNORECASE)

# Attributs où dort l'URL réelle. `src` vient en dernier : sur les sites à
# chargement différé, il ne contient qu'un pixel gris ou un flou de
# remplacement, la vraie photo étant dans un `data-*`.
ATTRS_IMAGE = ("data-src", "data-original", "data-lazy-src", "data-lazy",
               "data-echo", "data-image", "data-large", "data-full", "src")

# Habillage du site, jamais le bien : logos, pictogrammes, drapeaux de langue,
# pixels de mesure d'audience, images d'attente.
RE_IMG_HABILLAGE = re.compile(
    r"logo|sprite|favicon|picto|icone?s?/|/icons?/|flag|drapeau|avatar|placeholder"
    r"|blank|spacer|transparent|loader|loading|chargement|pixel|tracking|banniere"
    r"|banner|signature|cachet|qr[-_]?code|\.svg(?:$|\?)", re.IGNORECASE)

# Le sélecteur de langue. Son image s'appelle « FR.png », « en_GB.gif »,
# « fr-fr.svg » : un code de langue ou de pays, jamais un nom de photo. Elle
# échappait à RE_IMG_HABILLAGE (ni « flag » ni « drapeau » dans l'adresse) et,
# pire, vivait dans /assets/images/ — donc RE_IMG_BIEN la classait parmi les
# PHOTOS PRÉFÉRÉES. Six annonces d'une même agence affichaient un drapeau
# français en guise de maison.
#
# On énumère les codes plutôt que d'écrire « deux lettres » : cette version-là
# rejetait « og.jpg », le nom courant d'une vignette OpenGraph parfaitement
# légitime (un test existant l'a montré aussitôt).
CODES_DE_LANGUE = (
    "fr en es de it nl pt ru zh ar pl ja sv da fi tr el ko "
    "gb us be ch lu ca br cn jp"
).split()
RE_IMG_LANGUE = re.compile(
    r"/(?:%s)(?:[-_](?:%s))?\.(?:png|gif|jpe?g|webp|svg)(?:$|[?#])"
    % ("|".join(CODES_DE_LANGUE), "|".join(CODES_DE_LANGUE)),
    re.IGNORECASE)

# Ce qui, au contraire, sent la photo de bien.
RE_IMG_BIEN = re.compile(
    r"/(?:photos?|images?|medias?|uploads?|biens?|annonces?|propert|listing|vente"
    r"|galerie|gallery|thumb|vignette)", re.IGNORECASE)


def _urls_srcset(valeur: str) -> list[str]:
    """URLs d'un srcset, de la plus large à la plus étroite."""
    entrees = []
    for morceau in (valeur or "").split(","):
        bouts = morceau.strip().split()
        if not bouts:
            continue
        largeur = 0
        if len(bouts) > 1 and bouts[1].endswith(("w", "x")):
            try:
                largeur = float(bouts[1][:-1])
            except ValueError:
                largeur = 0
        entrees.append((largeur, bouts[0]))
    return [u for _, u in sorted(entrees, key=lambda e: -e[0])]


# Largeur annoncée par l'adresse elle-même : « …?f=1024x550&n=11665 »,
# « /1600xauto/images/… », « /290x218/11665.jpg », « ?w=800 ». Les sites
# d'agences dimensionnent presque toujours leurs images dans l'URL, et c'est
# le seul indice de taille disponible sans télécharger le fichier.
RE_LARGEUR_URL = re.compile(
    r"(?:^|[/?&_=-])(\d{3,4})\s*[x×]\s*(?:\d{2,4}|auto)"
    r"|[?&](?:w|width|size)=(\d{3,4})", re.IGNORECASE)


def largeur_annoncee(url: str) -> int:
    """La plus grande largeur que l'adresse revendique, 0 si elle n'en dit rien."""
    largeurs = []
    for a, b in RE_LARGEUR_URL.findall(url or ""):
        for valeur in (a, b):
            if valeur:
                largeurs.append(int(valeur))
    return max(largeurs) if largeurs else 0


def _image_de_la_page(html: str, base: str | None) -> str | None:
    """Photo la plus plausible parmi les images de la page.

    On écarte l'habillage du site (logos, pictogrammes, pixels de mesure) et
    les vignettes minuscules, puis on préfère une URL qui ressemble à un média
    de bien.

    Parmi celles-là, on prend LA PLUS GRANDE, et non la première rencontrée.
    C'était le défaut de fond : l'habillage d'un site est en haut de la page,
    la galerie plus bas — donc le premier venu était systématiquement une
    icône. Chez Cabinet Ray, `img/bell.png` (une cloche, sans dimension
    annoncée) l'emportait sur `image-get.inc.php?f=1024x550`, la vraie photo,
    présente dans la même page. Trois correctifs successifs sur des noms de
    fichiers n'avaient traité que les symptômes de ce choix-là.
    """
    candidates, secours = [], []
    for balise in RE_BALISE_IMG.finditer(html or ""):
        attrs = {}
        for m in RE_ATTRIBUT.finditer(balise.group(0)):
            attrs[m.group(1).lower()] = m.group(2) if m.group(2) is not None else m.group(3)

        # Une vignette déclarée minuscule n'est pas la photo du bien.
        petite = False
        for cle in ("width", "height"):
            try:
                if 0 < int(re.sub(r"\D", "", attrs.get(cle, "") or "0") or 0) <= 100:
                    petite = True
            except ValueError:
                pass
        if petite:
            continue

        brutes = []
        for cle in ("srcset", "data-srcset"):
            if attrs.get(cle):
                brutes += _urls_srcset(attrs[cle])
        brutes += [attrs[c] for c in ATTRS_IMAGE if attrs.get(c)]

        for brute in brutes:
            url = _url_img(brute, base)
            if not url or RE_IMG_HABILLAGE.search(url) or RE_IMG_LANGUE.search(url):
                continue
            (candidates if RE_IMG_BIEN.search(url) else secours).append(url)
            break

    if not candidates and not secours:
        # Dernier recours : les diaporamas posent souvent la photo en fond CSS.
        for m in RE_FOND_CSS.finditer(html or ""):
            url = _url_img(m.group(1), base)
            if url and not (RE_IMG_HABILLAGE.search(url) or RE_IMG_LANGUE.search(url)):
                return url

    # La plus grande l'emporte ; à taille égale ou inconnue, la première
    # rencontrée — l'ordre du document reste un départage honnête.
    retenues = candidates or secours
    if not retenues:
        return None
    return max(retenues, key=lambda u: (largeur_annoncee(u), -retenues.index(u)))


def _geo(noeud: dict):
    geo = noeud.get("geo")
    if isinstance(geo, list):
        geo = geo[0] if geo else {}
    if isinstance(geo, dict):
        return _num(_premier(geo, "latitude", "lat")), _num(_premier(geo, "longitude", "lon", "lng"))
    return None, None


def _type_bien(titre: str, types: set[str]) -> str:
    bas = (titre or "").lower()
    for motif, valeur in RE_MOTS_TYPE:
        if motif.search(bas):
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


def _depuis_jsonld(noeud: dict, base: str | None = None) -> dict:
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
        "photo": _image(noeud, base),
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
        annonce = {k: v for k, v in _depuis_jsonld(candidats[0], url).items() if v not in (None, "")}

    # 2. compléments OpenGraph / meta
    metas = _metas(html)
    annonce.setdefault("titre", metas.get("og:title") or "")
    annonce.setdefault("description", metas.get("og:description") or "")
    if not annonce.get("photo"):
        # L'OpenGraph d'un site mal gabarité sert le logo de l'agence à toutes
        # ses pages (`logo_og.png`). On lui applique le même tamis qu'aux <img>
        # : refusée, la vignette laisse la place aux vraies photos de la page.
        for cle in ("og:image", "og:image:secure_url", "twitter:image",
                    "twitter:image:src"):
            if metas.get(cle):
                candidate = _url_img(metas[cle], url)
                if candidate and not (RE_IMG_HABILLAGE.search(candidate)
                                      or RE_IMG_LANGUE.search(candidate)):
                    annonce["photo"] = candidate
                    break
    if not annonce.get("photo"):
        # Ni schema.org, ni OpenGraph : la photo est pourtant bien là, dans les
        # <img> de la page. Un quart des biens s'affichait sans image faute de
        # l'y chercher.
        annonce["photo"] = _image_de_la_page(html, url)
    if "prix" not in annonce:
        prix_meta = metas.get("product:price:amount") or metas.get("og:price:amount")
        if prix_meta:
            annonce["prix"] = _num(prix_meta)

    # 3. dernier recours : repères dans le texte visible
    #
    # Le texte n'était extrait que si le prix OU la surface manquaient — donc
    # jamais quand la fiche technique du site les fournit tous les deux. Deux
    # conséquences : le TERRAIN n'était alors pas lu du tout, et l'on ne
    # pouvait pas recouper une surface douteuse avec ce que la page annonce
    # noir sur blanc. Il est de toute façon relu plus bas pour la détection
    # des atouts : l'extraire ici ne coûte rien.
    texte = _texte_visible(html)
    if "prix" not in annonce and texte:
        for m in RE_PRIX.finditer(texte):          # 1er montant plausible
            val = _num(m.group(1))
            if val and 15_000 <= val <= 5_000_000:  # sous 15 000 € : réf., pas un prix
                annonce["prix"] = val
                break
    if "surface_m2" not in annonce and texte:
        # Le titre d'abord : c'est la surface la plus fiable de la page.
        titre_courant = annonce.get("titre", "")
        du_titre = _surfaces(titre_courant)
        if du_titre:
            annonce["surface_m2"] = du_titre[0]
            annonce["_surface_du_titre"] = True
        else:
            # Sinon, parmi toutes les surfaces du texte, celle qui donne un
            # prix au m² crédible : prendre la première conduisait à retenir
            # une piscine ou une chambre (« 50 m² » pour une propriété à
            # 950 000 €, soit 19 000 €/m²).
            choisie = _surface_coherente(_surfaces(texte), annonce.get("prix"))
            if choisie:
                annonce["surface_m2"] = choisie
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

    # Habitable = terrain : le site a publié la même valeur dans les deux
    # champs. Cas réel : la fiche technique de l'agence donne floorSize = 360
    # alors que sa propre page annonce « Surface habitable 300 m² — Terrain
    # 360 m² ». Écarter les surfaces du texte annoncées comme du terrain ne
    # suffit pas ici : la valeur ne vient PAS du texte, elle vient des données
    # structurées du site. On va donc rechercher dans le texte une surface
    # distincte du terrain — et si aucune n'est crédible, on n'affiche pas de
    # surface plutôt qu'un terrain déguisé en habitable.
    surface, terrain = annonce.get("surface_m2"), annonce.get("terrain_m2")
    if surface and terrain and surface == terrain:
        autres = [v for v in _surfaces(texte or "") if v != terrain]
        annonce["surface_m2"] = _surface_coherente(autres, annonce.get("prix"))
        annonce.pop("_surface_du_titre", None)

    # Contrôle croisé : un prix au m² absurde signale que l'une des deux
    # valeurs est fausse. Le titre étant la source la plus sûre, on garde ce
    # qu'il affirme et on efface l'autre — plutôt que d'afficher un hôtel
    # particulier de 220 m² à 182 €/m², ou une propriété à 19 000 €/m².
    du_titre = annonce.pop("_surface_du_titre", False)
    prix, surface = annonce.get("prix"), annonce.get("surface_m2")
    if prix and surface and not (PRIX_M2_MIN <= prix / surface <= PRIX_M2_MAX):
        if du_titre:
            annonce["prix"] = None          # la surface du titre fait foi
        else:
            annonce["surface_m2"] = None

    if not annonce.get("prix") and not annonce.get("surface_m2"):
        return None

    # Texte complet de la page pour la détection des critères de résilience
    # (les descriptions schema.org sont souvent trop courtes) et pour repérer
    # le code postal quand schema.org ne fournit pas l'adresse.
    texte_complet = texte or _texte_visible(html)
    annonce["texte"] = texte_complet[:3000]

    # DPE : schema.org ne le donne presque jamais ; on le cherche dans la page.
    if not annonce.get("dpe"):
        dpe = _dpe(html, texte_complet)
        if dpe:
            annonce["dpe"] = dpe

    if not annonce.get("code_postal"):
        cp = _code_postal(annonce.get("titre", ""), texte_complet)
        if cp:
            annonce["code_postal"] = cp
    if annonce.get("code_postal") and not annonce.get("departement"):
        annonce["departement"] = str(annonce["code_postal"])[:2]

    # Dernier recours pour le titre : la balise <title> de la page.
    if not annonce.get("titre"):
        balise = RE_TITRE.search(html)
        if balise:
            annonce["titre"] = re.sub(r"\s+", " ", balise.group(1)).strip()

    # Sans titre exploitable, l'extraction a échoué de bout en bout. Inventer
    # un titre (« Agence X — bien à vendre ») masquait cet échec : les pages
    # concernées ressortaient toutes avec le MÊME prix et la MÊME surface,
    # récupérés dans un bandeau commun à tout le site. Mieux vaut ne rien
    # remonter qu'une dizaine de biens fantômes identiques.
    if not annonce.get("titre"):
        return None

    annonce["source"] = source
    annonce["url"] = url
    annonce["agence"] = agence
    annonce["agence_url"] = agence_url
    annonce.setdefault("type_bien", "maison")
    return annonce
