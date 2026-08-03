"""Tests de l'extracteur d'annonces (schema.org JSON-LD + OpenGraph + texte).

Ces pages d'exemple reproduisent la structure réelle des sites d'agences
(données schema.org publiées pour le référencement Google), sans dépendre
d'un accès internet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extraction import extraire_annonce  # noqa: E402

# --- Page type « logiciel d'agence » : RealEstateListing + Offer complet -----
PAGE_JSONLD = """
<!doctype html><html><head>
<meta property="og:title" content="Longère à vendre — Bellême">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "RealEstateListing",
  "name": "Longère rénovée avec cave et puits",
  "description": "Belle longère avec cave voûtée, puits et grange. Poêle à bois.",
  "url": "https://agence-du-perche.fr/annonce/12345",
  "image": ["https://agence-du-perche.fr/photos/12345-1.jpg",
            "https://agence-du-perche.fr/photos/12345-2.jpg"],
  "numberOfRooms": 6,
  "floorSize": {"@type": "QuantitativeValue", "value": "165", "unitCode": "MTK"},
  "address": {"@type": "PostalAddress", "addressLocality": "Bellême", "postalCode": "61130"},
  "geo": {"@type": "GeoCoordinates", "latitude": 48.376, "longitude": 0.561},
  "additionalProperty": [
    {"@type": "PropertyValue", "name": "Surface terrain", "value": "7 500 m²"},
    {"@type": "PropertyValue", "name": "Classe énergie (DPE)", "value": "C"}
  ],
  "offers": {"@type": "Offer", "price": "289000", "priceCurrency": "EUR"}
}
</script></head><body><h1>Longère</h1></body></html>
"""

# --- Page type « Product + @graph », pièces en QuantitativeValue -------------
PAGE_GRAPH = """
<html><head>
<meta property="og:description" content="Corps de ferme avec dépendances et grand terrain.">
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Organization","name":"Immo Morvan"},
  {"@type":"Product","name":"Corps de ferme — Lormes (58)",
   "offers":[{"@type":"Offer","price":198000,"priceCurrency":"EUR"}],
   "numberOfRooms":{"@type":"QuantitativeValue","value":7},
   "floorSize":{"value":210},
   "address":{"postalCode":"58140","addressLocality":"Lormes"}}
]}
</script></head><body></body></html>
"""

# --- Page sans JSON-LD : uniquement OpenGraph + texte visible ----------------
PAGE_OG = """
<html><head>
<meta property="og:title" content="Maison de campagne à Toucy">
<meta property="og:description" content="Maison avec cave et verger.">
<meta property="og:image" content="https://agence-yonne.fr/img/toucy.jpg">
</head><body>
<h1>Maison de campagne</h1>
<p>Prix : 176 000 €. Surface habitable 130 m². Terrain de 2 500 m². 5 pièces.</p>
</body></html>
"""


def test_jsonld_complet():
    a = extraire_annonce(PAGE_JSONLD, "https://agence-du-perche.fr/annonce/12345",
                         source="agence-du-perche", agence="Agence du Perche",
                         agence_url="https://agence-du-perche.fr")
    assert a["prix"] == 289000
    assert a["surface_m2"] == 165
    assert a["terrain_m2"] == 7500
    assert a["pieces"] == 6
    assert a["commune"] == "Bellême"
    assert a["code_postal"] == "61130"
    assert a["departement"] == "61"
    assert a["lat"] == 48.376 and a["lon"] == 0.561
    assert a["dpe"] == "C"
    assert a["type_bien"] == "longère"
    assert a["agence"] == "Agence du Perche"
    assert a["photo"] == "https://agence-du-perche.fr/photos/12345-1.jpg"


def test_jsonld_graph_et_offre_liste():
    a = extraire_annonce(PAGE_GRAPH, "https://immo-morvan.fr/bien/9", source="immo-morvan")
    assert a["prix"] == 198000
    assert a["surface_m2"] == 210
    assert a["pieces"] == 7
    assert a["commune"] == "Lormes"
    assert a["type_bien"] == "corps de ferme"


def test_repli_opengraph_et_texte():
    a = extraire_annonce(PAGE_OG, "https://agence-yonne.fr/annonce/toucy", source="agence-yonne")
    assert a["titre"] == "Maison de campagne à Toucy"
    assert a["prix"] == 176000
    assert a["surface_m2"] == 130
    assert a["terrain_m2"] == 2500
    assert a["pieces"] == 5
    assert a["photo"] == "https://agence-yonne.fr/img/toucy.jpg"


def test_page_non_annonce_ignoree():
    html = "<html><head><title>Contact</title></head><body>Nos agences</body></html>"
    assert extraire_annonce(html, "https://x.fr/contact", source="x") is None


def test_valeurs_aberrantes_ecartees():
    # Prix aberrant (n° de référence) et « surface » qui est en fait le terrain.
    html = """<html><head>
    <meta property="og:title" content="&nbsp;Maison de caractère">
    </head><body><p>Réf 387487600 € — habitable, terrain 6000 m². Prix : 250 000 €.</p>
    </body></html>"""
    a = extraire_annonce(html, "https://x.fr/vente/12-maison", source="x")
    assert a is not None
    assert a["titre"] == "Maison de caractère"          # &nbsp; nettoyé
    assert a["prix"] == 250000                            # le vrai prix, pas 387 M
    assert a.get("surface_m2") in (None, )                # 6000 m² écarté (aberrant)
