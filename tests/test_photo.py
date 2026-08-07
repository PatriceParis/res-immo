"""Récupération de la photo du bien.

Un quart des biens (65 sur 252) s'affichait sans photo — non parce que la
page n'en montre pas, mais parce qu'on ne la cherchait QUE dans les données
structurées schema.org et les balises OpenGraph. Les sites qui ne publient
ni l'une ni l'autre affichaient pourtant leurs clichés dans de simples
<img>, souvent en chargement différé et en URL relative.

Cas signalé : le manoir de immo-ray.com (Cabinet Ray), sans image sur le
site alors que la page en comporte — comme les 8 autres biens de cette
agence, et 10 de l'Agence du Terroir, 8 d'AJC, 8 d'Echinard…
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extraction import _image_de_la_page, _url_img, extraire_annonce  # noqa: E402

BASE = "https://www.immo-ray.com/fr/a/vente/maisons/chalonnais/2017/manoir"


def test_url_relative_resolue():
    """« /media/biens/2017-1.jpg » était purement rejeté : l'URL était là,
    à un urljoin près."""
    assert _url_img("/media/biens/2017-1.jpg", BASE) == \
        "https://www.immo-ray.com/media/biens/2017-1.jpg"
    assert _url_img("../photos/a.jpg", BASE) == \
        "https://www.immo-ray.com/fr/a/vente/maisons/chalonnais/photos/a.jpg"
    # Sans page de référence, on ne peut rien en faire.
    assert _url_img("/media/x.jpg") is None
    # Le protocol-relative et le http restent gérés.
    assert _url_img("//cdn.agence.fr/p.jpg") == "https://cdn.agence.fr/p.jpg"
    assert _url_img("http://agence.fr/p.jpg") == "https://agence.fr/p.jpg"
    # Une image encodée dans la page n'est pas une photo d'agence exploitable.
    assert _url_img("data:image/gif;base64,R0lGOD", BASE) is None


def test_photo_trouvee_dans_les_img_de_la_page():
    html = """<html><body>
      <img src="/assets/logo-agence.png" alt="Cabinet Ray">
      <img src="/img/drapeau-fr.png" width="24" height="16">
      <img src="/media/biens/2017/manoir-1.jpg" alt="Manoir">
      <img src="/media/biens/2017/manoir-2.jpg">
    </body></html>"""
    assert _image_de_la_page(html, BASE) == \
        "https://www.immo-ray.com/media/biens/2017/manoir-1.jpg"


def test_chargement_differe_la_vraie_photo_est_dans_data_src():
    """Sur les sites à chargement différé, `src` ne porte qu'un pixel
    d'attente : la photo est dans un attribut `data-*`."""
    html = """<html><body>
      <img src="/img/placeholder.png" data-src="/media/biens/2017/manoir-1.jpg">
    </body></html>"""
    assert _image_de_la_page(html, BASE) == \
        "https://www.immo-ray.com/media/biens/2017/manoir-1.jpg"


def test_srcset_on_prend_la_plus_large():
    html = """<html><body><picture>
      <source srcset="/media/biens/p-400.jpg 400w, /media/biens/p-1200.jpg 1200w">
      <img src="/media/biens/p-400.jpg">
    </picture></body></html>"""
    assert _image_de_la_page(html, BASE) == \
        "https://www.immo-ray.com/media/biens/p-1200.jpg"


def test_l_habillage_du_site_n_est_jamais_pris_pour_le_bien():
    html = """<html><body>
      <img src="/assets/logo.svg">
      <img src="/assets/sprite-icons.png">
      <img src="/static/pixel-tracking.gif">
      <img src="/img/loader.gif">
    </body></html>"""
    assert _image_de_la_page(html, BASE) is None


def test_diaporama_en_fond_css():
    html = """<html><body>
      <div class="slide" style="background-image:url('/media/biens/2017/vue.jpg')"></div>
    </body></html>"""
    assert _image_de_la_page(html, BASE) == \
        "https://www.immo-ray.com/media/biens/2017/vue.jpg"


def test_l_ordre_des_sources_est_respecte():
    """schema.org fait foi, puis OpenGraph, puis les images de la page."""
    page = """<html><head>
    <meta property="og:title" content="Manoir origine 17ème">
    {og}
    {ld}
    </head><body>
      <img src="/media/biens/2017/depuis-la-page.jpg">
      <p>Prix : 660 000 €. Surface 400 m². Chalon-sur-Saône 71100.</p>
    </body></html>"""
    ld = """<script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Manoir",
     "image":"https://cdn.immo-ray.com/schema.jpg",
     "offers":{"@type":"Offer","price":"660000","priceCurrency":"EUR"}}
    </script>"""
    og = '<meta property="og:image" content="/media/og.jpg">'

    a = extraire_annonce(page.format(og=og, ld=ld), BASE, source="x")
    assert a["photo"] == "https://cdn.immo-ray.com/schema.jpg"

    b = extraire_annonce(page.format(og=og, ld=""), BASE, source="x")
    assert b["photo"] == "https://www.immo-ray.com/media/og.jpg"

    c = extraire_annonce(page.format(og="", ld=""), BASE, source="x")
    assert c["photo"] == "https://www.immo-ray.com/media/biens/2017/depuis-la-page.jpg"


def test_une_page_sans_aucune_image_n_en_invente_pas():
    html = """<html><head><meta property="og:title" content="Maison de bourg">
    </head><body><p>Prix : 189 000 €. Surface 120 m². Bellême 61130.</p>
    </body></html>"""
    a = extraire_annonce(html, "https://agence.fr/vente/1-maison", source="x")
    assert not a.get("photo")


def test_le_drapeau_du_selecteur_de_langue_n_est_pas_une_photo():
    """Cas réel signalé : six annonces d'Agence Armance affichaient le drapeau
    français. L'image s'appelle FR.png et vit dans /assets/images/ — donc
    RE_IMG_BIEN la classait parmi les photos PRÉFÉRÉES."""
    from app.extraction import _image_de_la_page

    html = """<html><body>
      <a href="/fr"><img src="/assets/images/FR.png" alt="Français"></a>
      <a href="/en"><img src="/assets/images/EN.png" alt="English"></a>
      <img src="/assets/images/photos/maison-sormery-01.jpg" alt="La maison">
    </body></html>"""
    photo = _image_de_la_page(html, "https://agencearmance.com/fr/annonce/562")
    assert photo == "https://agencearmance.com/assets/images/photos/maison-sormery-01.jpg"


def test_un_drapeau_seul_ne_donne_aucune_photo():
    """Mieux vaut pas d'image du tout qu'un drapeau présenté comme la maison."""
    from app.extraction import _image_de_la_page

    html = '<html><body><img src="/assets/images/FR.png"></body></html>'
    assert _image_de_la_page(html, "https://agencearmance.com/fr/annonce/562") is None


def test_le_logo_opengraph_ne_devient_pas_la_photo():
    """« 177 Maisons à vendre » a été catalogué avec logo_og.png pour photo :
    l'OpenGraph n'était filtré par rien."""
    from app.extraction import extraire_annonce

    html = """<html><head>
      <meta property="og:image" content="/images/logo_og.png">
      <meta property="og:title" content="Pavillon à Appoigny">
    </head><body>
      <img src="/medias/photos/pavillon-appoigny.jpg" alt="">
      <p>Prix : 159 900 €. Surface 102 m². Appoigny 89380.</p>
    </body></html>"""
    a = extraire_annonce(html, "https://www.groupe123immo.com/vente/1-appoigny/maison/3515-x", source="x")
    assert a.get("photo") == "https://www.groupe123immo.com/medias/photos/pavillon-appoigny.jpg"


def test_une_vraie_photo_opengraph_est_conservee():
    from app.extraction import extraire_annonce

    html = ('<html><head><meta property="og:image" '
            'content="https://cdn.agence.fr/photos/maison-42.jpg">'
            '<meta property="og:title" content="Longère"></head><body>'
            '<p>Prix : 245 000 €. Surface 140 m². Bellême 61130.</p>'
            '</body></html>')
    a = extraire_annonce(html, "https://agence.fr/bien/42", source="x")
    assert a.get("photo") == "https://cdn.agence.fr/photos/maison-42.jpg"


def test_le_relais_annonce_la_page_de_l_annonce_comme_referer():
    """Cas réel signalé : les photos de Groupe 123 Immo (hébergées sur
    staticlbi.com) ne s'affichaient pas. Le relais se réclamait du CDN
    lui-même — ce qu'aucun navigateur n'envoie jamais."""
    from urllib.parse import urlparse

    from app.main import referer_de_la_page

    cdn = urlparse("https://grcentvingttrois.staticlbi.com/600xauto/images/5/photo.jpg")
    page = "https://www.groupe123immo.com/vente/1-appoigny/maison/3515-pavillon"
    assert referer_de_la_page(page, cdn) == "https://www.groupe123immo.com/"


def test_sans_page_connue_le_relais_garde_l_ancien_comportement():
    """Les agences qui hébergent leurs images chez elles continuent de marcher."""
    from urllib.parse import urlparse

    from app.main import referer_de_la_page

    img = urlparse("https://agencearmance.com/assets/photos/maison.jpg")
    assert referer_de_la_page(None, img) == "https://agencearmance.com/"
    assert referer_de_la_page("", img) == "https://agencearmance.com/"
    # Une page inexploitable (relative, autre protocole) ne doit pas casser.
    assert referer_de_la_page("/annonce/562", img) == "https://agencearmance.com/"
    assert referer_de_la_page("javascript:alert(1)", img) == "https://agencearmance.com/"
