"""Une page qui énumère plusieurs biens n'est pas un bien.

Un utilisateur a signalé qu'une annonce vue chez son agence — 108 000 € à
Doudeville — n'apparaissait pas sur le site. Elle y était pourtant, mais
noyée : la page catalogue « /vente/maison » de l'Agence Saint-Joseph avait
été publiée comme UNE maison, portant le titre et le prix de sa première
carte et une surface qui n'appartenait à aucune. Les cinq biens réels de la
page n'existaient nulle part ailleurs.

Les pages catalogue se reconnaissaient à leur titre (« 177 Maisons à
vendre »). Celle-ci empruntait le sien à son premier bien. Il fallait donc
un signe qui vienne du CONTENU, pas de l'étiquette.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.qualite import (_REFERENCE, REFERENCES_MAXI,  # noqa: E402
                         enumere_plusieurs_biens, est_bien_valide)

# Le texte réellement collecté, raccourci — c'est lui qui a produit le fantôme.
CATALOGUE = (
    "Maisons en vente Accueil Acheter Louer Vendre Estimer Nos biens vendus "
    "BIENS EN VENTE Trier par Créer une alerte "
    "93 000 € Maison de Ville 5 pièces 105 m² Doudeville 76560 Référence 7252 "
    "108 000 € Maison ancienne à vendre 4 pièces 120 m² Doudeville 76560 Référence 7196 "
    "117 000 € Maison de campagne 3 pièces 78 m² Yvetot 76190 Référence 7128 "
    "125 000 € Longère 4 pièces 96 m² Yerville 76760 Référence 6710 "
    "133 000 € Maison ancienne 5 pièces 110 m² Le Trait 76580 Référence 6141"
)

BIEN_REEL = (
    "Référence 7196. Maison ancienne à vendre, 4 pièces, 120 m² à Doudeville "
    "(76560). Maison de ville avec terrasse, grand garage et bâtiment, "
    "comprenant au rez-de-chaussée une entrée, un salon, une cuisine."
)


def _fiche(texte, **extra):
    # L'adresse d'une vraie fiche de cette agence : un libellé et une
    # référence. Depuis le 12 octobre 2026, « /vente/maison » tout court est
    # reconnu comme une page de rubrique dès l'adresse ; ces tests mesurent
    # l'énumération des références, pas l'adresse.
    base = {"titre": "Maison de Ville", "texte": texte, "prix": 93000,
            "surface_m2": 140.0, "pieces": 5, "type_bien": "maison",
            "url": "https://www.immobiliersaintjoseph.com/vente/"
                   "maison-de-ville-tourville-sur-sienne-50200,VM865"}
    return {**base, **extra}


def test_la_page_catalogue_n_est_plus_publiee_comme_un_bien():
    """LE cas signalé : titre d'annonce, contenu de catalogue."""
    assert enumere_plusieurs_biens(_fiche(CATALOGUE))
    assert not est_bien_valide(_fiche(CATALOGUE))
    # Et sous son adresse réelle de rubrique, elle tombe aussi.
    assert not est_bien_valide(_fiche(CATALOGUE, url="https://www.immobiliersaintjoseph.com/vente/maison"))


def test_une_vraie_fiche_garde_sa_place():
    """Le bien à 108 000 € que l'utilisateur cherchait, sur sa propre page :
    une seule référence, il doit passer."""
    fiche = _fiche(BIEN_REEL, titre="Maison ancienne à vendre, 4 pièces - Doudeville",
                   prix=108000, surface_m2=120.0, pieces=4,
                   url="https://www.immobiliersaintjoseph.com/vente/"
                       "maison-ancienne-4-pieces-doudeville-76560,VM2599")
    assert not enumere_plusieurs_biens(fiche)
    assert est_bien_valide(fiche)


def test_deux_references_ne_suffisent_pas_a_condamner():
    """Le seuil est à trois parce que deux se rencontrent honnêtement : chez
    Antony Vesque, chaque fiche porte la référence de l'AGENCE en plus de
    celle du bien. Trois vraies annonces auraient disparu."""
    fiche = _fiche("Vente maison 2 chambres Tourville-sur-Sienne. "
                   "Référence 865. Agence réf. 1022.",
                   titre="Vente maison 2 chambres Tourville-sur-Sienne")
    assert not enumere_plusieurs_biens(fiche)
    assert est_bien_valide(fiche)
    assert REFERENCES_MAXI == 2, "le seuil documenté par ce test"


def test_une_page_sans_reference_n_est_pas_condamnee():
    """Beaucoup d'agences n'affichent aucune référence : la règle doit rester
    muette plutôt que de deviner."""
    assert not enumere_plusieurs_biens(_fiche("Belle longère au cœur du Perche."))
    assert not enumere_plusieurs_biens(_fiche(""))
    assert not enumere_plusieurs_biens({})


def test_la_meme_reference_repetee_ne_compte_qu_une_fois():
    """Une fiche rappelle souvent sa référence en haut et en bas de page."""
    fiche = _fiche("Référence 7196. … Réf. 7196 … référence 7196",
                   titre="Maison ancienne à Doudeville")
    assert not enumere_plusieurs_biens(fiche)


# Le texte d'une fiche Demonchy, raccourci : un bien, et ses voisins en marge.
FICHE_AVEC_VOISINES = (
    "La Solution Immo Maison à Clairy Saulchoix 415.000 € Partager sur les réseaux: "
    "Consommation énergétiques : 260 kwh/m² an Emission de gaz à effet de serre : "
    "53 kg C02/m² an Réf. 2026-02-258P Biens similaires Maison à Poix-de-Picardie "
    "Réf. 974 Maison à Aumale Réf. 975 Maison à Hornoy-le-Bourg Réf. 20226"
)


def test_la_fiche_d_un_bien_qui_cite_ses_voisines_n_est_pas_un_catalogue():
    """Sondé le 17 octobre 2026 chez Demonchy, à Amiens : vingt maisons par
    visite refusées comme catalogues, chacune sous une adresse qui porte sa
    surface, sa commune, son code postal et sa référence — « vente-maison-
    111m-hornoy-le-bourg-80640-2024-10-350p ». La page est celle d'un seul
    bien : son prix, son DPE, son bouton « Partager ». Elle cite en marge les
    références de biens voisins, et la règle les comptait comme les cartes
    d'un catalogue."""
    assert len(set(_REFERENCE.findall(FICHE_AVEC_VOISINES))) > REFERENCES_MAXI, \
        "le texte cite bien plus de références que le seuil"
    fiche = _fiche(FICHE_AVEC_VOISINES, titre="Vente-Maison-Amiens-258P | DEMONCHY IMMOBILIER",
                   prix=415000, surface_m2=207.0,
                   url="https://www.agence-demonchy.fr/annonce-immobilier/vente-maison-207m-amiens-80000/")
    assert not enumere_plusieurs_biens(fiche)
    assert est_bien_valide(fiche)
    for url in ("https://www.agence-demonchy.fr/annonce-immobilier/"
                "vente-maison-111m-hornoy-le-bourg-80640-2024-10-350p/",
                "https://www.agence.fr/vente/80640-hornoy/maison-111m2-jardin-80640"):
        assert not enumere_plusieurs_biens(_fiche(FICHE_AVEC_VOISINES, url=url)), url


def test_sans_surface_ni_code_dans_l_adresse_la_regle_d_avant_tient():
    """L'exception ne vaut que pour une adresse qui désigne un bien. Le même
    texte sous une adresse de liste, ou le catalogue de Saint-Joseph sous une
    adresse de fiche sans surface, restent des catalogues : une annonce
    fantôme coûte plus cher qu'une maison manquée."""
    for url in ("https://www.agence-demonchy.fr/nos-biens/",
                "https://www.agence-demonchy.fr/annonce-immobilier/vente-maison-amiens-80000/",
                "https://lemaistre-immo.fr/fr/vente-maison-villa.htm"):
        assert enumere_plusieurs_biens(_fiche(FICHE_AVEC_VOISINES, url=url)), url
    assert enumere_plusieurs_biens(_fiche(CATALOGUE))
    # Le constat de l'export, sans texte, tient aussi hors de l'exception.
    assert enumere_plusieurs_biens({"plusieurs_biens": True,
                                    "url": "https://lemaistre-immo.fr/fr/vente-maison-villa.htm"})
