"""Un titre d'une lettre n'est pas un titre : l'extracteur cherche encore.

Sondé le 16 octobre 2026 chez L'Agence Smith, 45 pages sur 45 écartées pour
« titre indigent » à chaque visite : la page écrit son og:title entre
apostrophes — content='L'agence Smith - NOUVEAUTÉ SMITH : …' — et le nom de
l'agence en contient une. Le navigateur comme nous n'y lisons que « L ». Le
prix et la surface, eux, se lisaient parfaitement (119 000 €, 66,4 m²), et la
balise <title> disait tout : « L'agence Smith - NOUVEAUTÉ SMITH : APPARTEMENT
4 PIÈCES / 3 CHAMBRES ». L'extracteur ne se repliait sur <title> qu'en
l'absence de titre ; il s'y replie désormais aussi devant un titre indigent,
par la définition même du filtre qualité (`qualite.titre_indigent`) — une
seule règle pour refuser et pour chercher encore.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import qualite  # noqa: E402
from app.extraction import extraire_annonce  # noqa: E402

URL = "https://www.agence-smith.com/bien-immobilier/nouveaute-smith-appartement-4-pieces-3-chambres-2/"
PAGE = """<!doctype html><html lang="fr"><head>
<title>L&#039;agence Smith - NOUVEAUT&Eacute; SMITH : APPARTEMENT 4 PI&Egrave;CES / 3 CHAMBRES</title>
<meta property="og:title" content='L'agence Smith - NOUVEAUTÉ SMITH : APPARTEMENT 4 PIÈCES / 3 CHAMBRES' />
<meta property="og:description" content="Bel appartement de 66,4 m² au calme." />
</head><body>
<h1>NOUVEAUTÉ SMITH : APPARTEMENT 4 PIÈCES / 3 CHAMBRES</h1>
<p>Prix : 119 000 €</p><p>Surface habitable : 66,4 m²</p><p>4 pièces, 3 chambres, à Lille 59000.</p>
</body></html>"""


def test_devant_un_titre_d_une_lettre_l_extracteur_lit_la_balise_title():
    annonce = extraire_annonce(PAGE, URL, source="test")
    assert annonce, "prix et surface se lisent : la page est une annonce"
    assert annonce["titre"].startswith("L'agence Smith - NOUVEAUTÉ SMITH : APPARTEMENT"), annonce["titre"]
    assert annonce["prix"] == 119000 and annonce["surface_m2"] == 66.4
    # Et le filtre qualité peut alors faire son travail : c'est un appartement,
    # ce qui est un refus stable — plus un titre indigent relu à chaque visite.
    assert qualite.motif_de_rejet({**annonce, "agence": "L'Agence Smith"}) == "titre_hors_cible:appartement"


def test_la_definition_du_titre_indigent_est_celle_du_filtre():
    assert qualite.titre_indigent("L") and qualite.titre_indigent("389") and qualite.titre_indigent("")
    assert not qualite.titre_indigent("Maison de bourg")
    assert qualite.motif_de_rejet({"titre": "L", "prix": 119000, "surface_m2": 66.4}) == "titre_indigent"


def test_sans_balise_title_le_titre_indigent_reste_et_la_page_est_refusee():
    """Pas de <title> pour se rattraper : rien n'est inventé, la règle d'avant."""
    sans_title = PAGE.replace(
        "<title>L&#039;agence Smith - NOUVEAUT&Eacute; SMITH : APPARTEMENT 4 PI&Egrave;CES / 3 CHAMBRES</title>", "")
    annonce = extraire_annonce(sans_title, URL, source="test")
    assert annonce and annonce["titre"] == "L"
    assert qualite.motif_de_rejet(annonce) == "titre_indigent"
