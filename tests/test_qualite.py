"""Tests du filtre de qualité (ne garder que de vrais biens « refuge »)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.qualite import est_bien_valide, est_vendu  # noqa: E402


def test_detecte_les_biens_vendus():
    """La pastille « Vendu » de la fiche (cas réel signalé par l'utilisateur)."""
    assert est_vendu({"texte": "Retour aux résultats Partager ce bien Vendu "
                               "Afficher toutes les photos 1 / 11"})
    assert est_vendu({"texte": "maison retour Vendu Ref : 1280 villa 170 m"})
    assert est_vendu({"texte": "Cette maison est sous compromis."})
    # Disponibilité schema.org (signal le plus fiable).
    assert est_vendu({"vendu": True, "texte": ""})


def test_le_menu_biens_vendus_ne_compte_pas():
    """Piège : le menu de navigation dit « Biens vendus » sur CHAQUE page.

    Au pluriel — il ne doit jamais faire passer un bien disponible pour vendu.
    """
    menu = ("Espace propriétaire 0 fr Menu Nos biens Biens vendus Notre équipe "
            "Estimation Alerte e-mail Contact Accueil")
    assert not est_vendu({"texte": menu})
    assert est_bien_valide({"titre": "Longère avec cave à Bellême", "texte": menu,
                            "type_bien": "longère", "surface_m2": 140})


def test_vendu_descriptif_ne_compte_pas():
    """« vendu avec/séparément/meublé » décrit le bien, il n'est pas vendu."""
    assert not est_vendu({"texte": "Le terrain attenant est vendu séparément."})
    assert not est_vendu({"texte": "Bien vendu meublé, disponible immédiatement."})


def test_bien_vendu_ecarte_de_la_base():
    assert not est_bien_valide(
        {"titre": "PROCHE BELLÊME ET FORÊT DOMANIALE MAISON 3 CHAMBRES",
         "type_bien": "maison", "surface_m2": 96, "prix": 97000,
         "texte": "Partager ce bien Vendu Afficher toutes les photos"})


def test_rejette_pages_non_annonce():
    # Article de blog (cas réel vu sur le site)
    assert not est_bien_valide(
        {"titre": "Vendre sa maison, quel mandat choisir? Demeures du Perche",
         "prix": 795000})
    # Page catalogue « nos biens à vendre »
    assert not est_bien_valide(
        {"titre": "Nos biens à vendre | Demeures du Perche et de Normandie",
         "surface_m2": 120})
    # Page d'agence
    assert not est_bien_valide({"titre": "Estimation gratuite | Notre agence",
                                "surface_m2": 90})


def test_rejette_biens_non_refuge():
    assert not est_bien_valide({"titre": "Appartement T3 lumineux à Beauvais",
                                "type_bien": "appartement", "surface_m2": 65})
    assert not est_bien_valide({"titre": "Studio meublé centre-ville", "surface_m2": 22})
    assert not est_bien_valide({"titre": "Parking sécurisé à vendre", "prix": 15000})
    assert not est_bien_valide({"titre": "Terrain à bâtir viabilisé", "prix": 80000})
    assert not est_bien_valide({"titre": "Local commercial 120 m²", "surface_m2": 120})


def test_rejette_pages_et_titres_indigents():
    # Page de résultats de recherche (vue réellement sur un site d'agence).
    assert not est_bien_valide({"titre": "Search - Perche et Demeures", "surface_m2": 400})
    # Titre-gabarit « A vendre | Agence » : aucune info de bien.
    assert not est_bien_valide({"titre": "A vendre | BAUDART IMMO", "surface_m2": 100})
    # Titres réduits à un numéro de référence.
    assert not est_bien_valide({"titre": "389", "surface_m2": 176, "prix": 11500})
    assert not est_bien_valide({"titre": "9", "surface_m2": 720})
    # Local professionnel : hors cible refuge.
    assert not est_bien_valide({"titre": "LOCAL PROFESSIONNEL BELLÊME 405 M²",
                                "surface_m2": 405, "prix": 286200})


def test_le_type_dans_l_url_prime_sur_le_titre():
    """Cas réels : le titre dit « maison », l'URL dit terrain / autre.

    Les titres d'agences sont souvent tronqués ou purement commerciaux ; le
    chemin de l'URL, lui, porte le vrai type du bien.
    """
    assert not est_bien_valide(
        {"titre": "A PROXIMITE DE BELLEME ET SES COMMERCES", "surface_m2": 440,
         "prix": 56000,
         "url": "https://www.perch-immo.fr/vente/2525-belforet-en-perche/terrain/1841-a-proximite"})
    assert not est_bien_valide(
        {"titre": "BATIMENT D", "surface_m2": 375, "prix": 213900,
         "url": "https://www.perch-immo.fr/vente/1-belleme/autre/1479-batiment-d-activite-belleme"})
    assert not est_bien_valide(
        {"titre": "Vente de terrains | Indicateur Vendomois", "surface_m2": 400,
         "url": "https://www.indicateurvendomois.com/vente/terrains/1"})
    # Une vraie maison garde son URL /maison/ : elle passe.
    assert est_bien_valide(
        {"titre": "Corps de ferme à rénover au bout d'un chemin",
         "type_bien": "corps de ferme", "surface_m2": 180, "prix": 345000,
         "url": "https://www.perch-immo.fr/vente/1-belleme/maison/1795-corps-de-ferme"})


def test_rejette_prix_aberrant_sans_surface():
    # « Prix » de 3 480 € (référence prise pour un prix) sans surface : écarté.
    assert not est_bien_valide({"titre": "Propriété de caractère restaurée",
                                "type_bien": "propriété", "prix": 3480, "pieces": 8})
    # Le même bien AVEC une surface reste valide (le prix sera corrigé au chargement).
    assert est_bien_valide({"titre": "Propriété de caractère restaurée",
                            "type_bien": "propriété", "prix": 3480, "surface_m2": 220})


def test_accepte_vrais_biens_refuge():
    assert est_bien_valide(
        {"titre": "Longère avec cave et puits — Bellême", "type_bien": "longère",
         "surface_m2": 140, "prix": 285000, "pieces": 5})
    assert est_bien_valide(
        {"titre": "Maison de campagne à Toucy", "type_bien": "maison", "surface_m2": 130})
    # Maison « à vendre » (singulier) : à ne PAS confondre avec la page catalogue
    assert est_bien_valide(
        {"titre": "Maison à vendre à Mortagne-au-Perche", "type_bien": "maison",
         "prix": 190000, "pieces": 6})


def test_rejette_vitrines_de_constructeur_et_pages_d_agence():
    """Cas réels remontés d'une collecte : une page « modèles et prix » d'un
    constructeur et la page d'accueil d'une agence s'affichaient comme biens."""
    assert not est_bien_valide(
        {"titre": "Maison France Confort : 7 Modèles et Prix Exclusifs",
         "surface_m2": 120, "prix": 250000})
    assert not est_bien_valide(
        {"titre": "Olléa Immobilier Beauvais - Achat & Vente Immobilier",
         "surface_m2": 90, "prix": 180000})
    assert not est_bien_valide(
        {"titre": "Faire construire sa maison neuve dans l'Oise", "surface_m2": 100})
    # Une vraie annonce contenant le mot « vente » reste valide.
    assert est_bien_valide(
        {"titre": "Vente Maison Ribemont 5 pièce(s) 100 m2", "type_bien": "maison",
         "surface_m2": 100, "prix": 128000, "pieces": 5})


def test_abreviations_appartement_ecartees():
    """Cas réel : « A VENDRE APPT T2 » passait à travers « appartements? »."""
    assert not est_bien_valide({"titre": "A VENDRE APPT T2 A LA FERTÉ SOUS JOUARRE",
                                "surface_m2": 45, "prix": 95000})
    assert not est_bien_valide({"titre": "Vente appart 3 pièces centre-ville",
                                "surface_m2": 65, "prix": 120000})
    # « T6 » seul ne disqualifie pas : une maison peut être un T6.
    assert est_bien_valide({"titre": "A VENDRE MAISON T6 DANS HAMEAU",
                            "type_bien": "maison", "surface_m2": 140, "prix": 235000})
