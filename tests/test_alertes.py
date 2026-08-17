"""La mise en relation est retirée, et ne doit pas revenir par la bande.

Le bloc « recevez les photos, soyez recontacté » recueillait l'e-mail du
visiteur pour le transmettre à l'agence, et l'annonçait lui-même : « la
plateforme est gratuite pour vous ; elle est rémunérée à la mise en relation
qualifiée avec l'agence ». Prêter son concours, même à titre accessoire et
contre rémunération, à la recherche d'un immeuble pour autrui est l'activité
que la loi Hoguet réserve aux titulaires d'une carte professionnelle. La
phrase « Refuge Immo n'est pas une agence immobilière » ne décrivait pas ce
que le site faisait, et une clause ne défait pas une qualification.

Deux choses devaient partir, pas une : le bouton ET la route. Retirer le
premier en laissant la seconde ouverte n'aurait rien changé au fond.

Ce qui remplace ne met personne en relation. Ces tests tiennent la frontière,
parce qu'elle est facile à repasser sans y penser — il suffirait d'un
formulaire « on s'occupe de tout » pour y retomber.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages, seo  # noqa: E402

import re  # noqa: E402

_BRUT_JS = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")
MAIN = (RACINE / "app" / "main.py").read_text(encoding="utf-8")

# Le code SEUL, commentaires retirés. Les commentaires citent la phrase
# supprimée — « rémunéré à la mise en relation qualifiée » — pour expliquer
# pourquoi elle l'a été. C'est précisément ce qu'on veut garder, et un test qui
# les lirait accuserait la documentation à la place du code.
APP_JS = re.sub(r"/\*.*?\*/|<!--.*?-->|^\s*//.*$", "", _BRUT_JS, flags=re.S | re.M)


def test_le_retrait_reste_explique_dans_le_code():
    """L'inverse du test suivant : la raison doit rester écrite quelque part,
    sinon quelqu'un remettra le bloc de bonne foi dans six mois."""
    assert "Hoguet" in _BRUT_JS and "Hoguet" in MAIN


def test_la_route_de_mise_en_relation_n_existe_plus():
    """LE test. Le bouton retiré sans la route aurait laissé le recueil
    d'adresses ouvert à qui connaît l'adresse de l'API."""
    from app.main import app
    chemins = [getattr(r, "path", "") for r in app.routes]
    assert "/api/contact" not in chemins
    assert "DemandeContact" not in MAIN


def test_l_interface_ne_propose_plus_d_etre_recontacte():
    for trace in ("btn-mer", "mise-en-relation", "Être recontacté",
                  "mise en relation qualifiée", "/api/contact"):
        assert trace not in APP_JS, f"« {trace} » traîne encore dans l'interface"


def test_les_vignettes_verrouillees_ont_disparu():
    """Elles laissaient croire que d'autres photos attendaient derrière un
    e-mail. Le catalogue ne détient rien de plus que ce qu'il montre."""
    assert "verrou" not in APP_JS


def test_la_page_d_alertes_dit_ce_qu_elle_ne_fait_pas():
    """C'est la partie qui compte juridiquement : la page doit décrire le
    service réellement rendu, pas se contenter d'une clause d'exclusion."""
    html = pages.page_alertes({}, base="https://exemple.fr")
    for engagement in ("non, jamais", "aucune commission",
                       "carte professionnelle", "annonce d'origine"):
        assert engagement in html, engagement


def test_aucune_adresse_n_est_recueillie_tant_qu_aucune_boite_ne_la_recoit():
    """Le dispositif précédent écrivait les adresses dans un fichier voisin de
    la base — donc dans /tmp sur l'hébergement, effacé à chaque redémarrage.
    Recueillir une donnée personnelle pour la perdre est pire que ne pas la
    recueillir : sans boîte configurée, la page le dit au lieu d'afficher un
    formulaire qui ment."""
    html = pages.page_alertes({}, base="https://exemple.fr")
    if not seo.COURRIEL_ALERTES:
        assert "ne sont pas encore ouvertes" in html
        assert 'type="email"' not in html, "pas de champ qui recueille pour rien"


def test_la_page_annonce_son_droit_a_l_effacement():
    html = pages.page_alertes({}, base="https://exemple.fr")
    assert "effacement" in html and "sans condition" in html


def test_les_criteres_venus_de_la_fiche_ne_sont_qu_une_suggestion():
    """Pré-remplir n'est pas choisir à la place : le visiteur doit pouvoir
    tout changer, sinon c'est nous qui sélectionnons pour lui."""
    html = pages.page_alertes({}, prix_choisi=150_000,
                              region_choisie="Normandie", base="https://exemple.fr")
    assert "n'en fixons aucun à votre place" in html


def test_une_region_inconnue_ne_passe_pas_dans_la_page():
    """Le paramètre vient de l'adresse : il est donc entre les mains du
    visiteur, et ne doit jamais atterrir tel quel dans le HTML."""
    from fastapi.testclient import TestClient
    from app.main import app
    reponse = TestClient(app).get("/alertes?region=<script>alert(1)</script>")
    assert reponse.status_code == 200
    assert "<script>alert(1)</script>" not in reponse.text


def test_l_alerte_est_annoncee_au_plan_du_site_et_au_llms_txt():
    plan = seo.sitemap([], {"Normandie"}, "https://exemple.fr")
    assert f"https://exemple.fr{seo.URL_ALERTES}" in plan
    assert seo.URL_ALERTES in seo.llms_txt(10, {"Normandie": 4}, "https://exemple.fr")
