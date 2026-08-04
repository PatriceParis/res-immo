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
<meta property="og:image" content="//agence-yonne.fr/img/toucy.jpg">
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
    # URL protocol-relative (//…) normalisée en https absolu.
    assert a["photo"] == "https://agence-yonne.fr/img/toucy.jpg"


def test_code_postal_depuis_titre():
    # Titre « Ville (CP) » sans adresse schema.org : le CP doit être repéré.
    html = """<html><head>
    <meta property="og:title" content="Maison 5 pièces 130 m² Breteuil (60120)">
    </head><body><p>Belle maison. Prix : 245 000 €. Surface 130 m².</p></body></html>"""
    a = extraire_annonce(html, "https://x.fr/vente/42-maison", source="x")
    assert a["code_postal"] == "60120"
    assert a["departement"] == "60"


def test_code_postal_depuis_texte():
    # CP absent du titre mais présent (et dominant) dans le texte de la page.
    html = """<html><head>
    <meta property="og:title" content="Corps de ferme à rénover">
    </head><body><p>Prix : 189 000 €. Surface 160 m². Secteur Bellême 61130,
    proche forêt. Réf. 61130-A. Contact agence 61130.</p></body></html>"""
    a = extraire_annonce(html, "https://x.fr/vente/7-ferme", source="x")
    assert a["code_postal"] == "61130"
    assert a["departement"] == "61"


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


def test_numero_de_reference_nest_pas_un_code_postal():
    """Cas réel : « Hôtel particulier à Alençon - Ref. 23624 » se retrouvait
    géolocalisé dans la Creuse (23), le numéro de référence ayant été pris
    pour un code postal."""
    html = """<html><head>
    <meta property="og:title" content="Hôtel particulier de charme - Alençon - Ref. 23624">
    </head><body><p>Alençon 61000, Orne. Prix : 395 000 €. Surface 210 m².</p>
    </body></html>"""
    a = extraire_annonce(html, "https://x.fr/demeures/hotel-alencon", source="x")
    assert a["code_postal"] == "61000"
    assert a["departement"] == "61"


def test_surfaces_decimales():
    """« 132,96 m² » était lu 96 m², « 238.0 m2 » pas lu du tout — de quoi
    fausser le prix au m² et donc la comparaison au marché."""
    html = """<html><head>
    <meta property="og:title" content="Maison 6 pièces 132,96 m² Bellême">
    </head><body><p>Prix : 189 000 €. Terrain 1 200 m².</p></body></html>"""
    a = extraire_annonce(html, "https://x.fr/vente/1-maison", source="x")
    assert a["surface_m2"] == 132.96

    html2 = """<html><head>
    <meta property="og:title" content="maison 7 pièces - 238.0 m2 - BETHISY">
    </head><body><p>Prix : 280 000 €.</p></body></html>"""
    b = extraire_annonce(html2, "https://x.fr/vente/2-maison", source="x")
    assert b["surface_m2"] == 238


def test_la_surface_du_terrain_n_est_pas_prise_pour_l_habitable():
    """Dans « Terrain de 2 500 m² », « 500 m² » se lisait comme une surface
    habitable et supplantait les vrais 130 m² de la maison."""
    from app.extraction import _surfaces
    assert _surfaces("Surface habitable 130 m². Terrain de 2 500 m².") == [130]
    assert _surfaces("terrain 4425 m²") == []          # hors bornes habitables


def test_la_surface_annoncee_comme_terrain_est_ecartee():
    """Cas réels relevés par l'audit : « Surface 83,58 m² terrain 285 m² » et
    « Surface habitable (m²) 94 m² surface terrain 558 m² » ressortaient tous
    deux avec le TERRAIN comme surface habitable — la plus grande des surfaces
    crédibles l'emportait, et un terrain l'est souvent aussi."""
    from app.extraction import _surface_coherente, _surfaces

    # Le terrain ne doit pas figurer parmi les candidats. Les autres surfaces
    # de la page (une pièce, une dépendance) peuvent y rester : c'est le rôle
    # de _surface_coherente de trancher entre elles.
    candidats = _surfaces("Surface 83,58 m² terrain 285 m² séjour 25 m²")
    assert 285 not in candidats
    assert _surface_coherente(candidats, 150000) == 83.58

    candidats = _surfaces("Surface habitable (m²) 94 m² surface terrain 558 m²")
    assert 558 not in candidats
    assert _surface_coherente(candidats, 260000) == 94

    # …sans écarter pour autant l'habitable qui SUIT une mention de terrain :
    # on ne regarde en arrière que jusqu'à la surface précédente.
    assert _surface_coherente(_surfaces("Terrain 500 m², maison 120 m²"), 240000) == 120
    assert _surface_coherente(
        _surfaces("Jardin clos de 300 m², habitation de 145 m²"), 290000) == 145


def test_surface_choisie_par_coherence_du_prix_au_m2():
    """Cas réel : une propriété à 950 000 € ressortait à 50 m² — la première
    surface du texte était celle de la piscine, soit 19 000 €/m²."""
    html = """<html><head>
    <meta property="og:title" content="propriété avec piscine, tennis et gîtes">
    </head><body><p>Prix : 950 000 €. Piscine de 50 m², maison de 350 m².</p>
    </body></html>"""
    a = extraire_annonce(html, "https://x.fr/vente/9-propriete", source="x")
    assert a["surface_m2"] == 350                       # pas la piscine


def test_prix_absurde_efface_quand_le_titre_donne_la_surface():
    """« Hôtel particulier 8 pièces 220 m2 » à 40 000 € : 182 €/m². La surface
    vient du titre, donc c'est le prix qui est faux — on n'en affiche aucun
    plutôt qu'un chiffre trompeur."""
    html = """<html><head>
    <meta property="og:title" content="Hôtel particulier 8 pièces 220 m2 Beaumont">
    </head><body><p>Honoraires 40 000 €.</p></body></html>"""
    a = extraire_annonce(html, "https://x.fr/vente/3-hotel", source="x")
    assert a["surface_m2"] == 220
    assert a.get("prix") is None
    assert "_surface_du_titre" not in a                  # clé interne nettoyée
