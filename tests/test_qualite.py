"""Tests du filtre de qualité (ne garder que de vrais biens « refuge »)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.qualite import (est_bien_valide, est_vendu, motif_de_rejet,  # noqa: E402
                         motif_url_hors_cible)


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


def test_rejette_les_offres_de_construction():
    """Cas réel : « Bourgogne Bâtir », classée agence par OpenStreetMap, a
    livré 7 offres de construction — « Maison + Terrain à Oslon », 55 000 € —
    toutes géolocalisées au siège du constructeur. Le site annonçait donc
    7 biens à Chalon-sur-Saône où il n'y en avait aucun.

    Ce prix est celui d'un chantier, et le bien n'existe pas encore : c'est
    l'exact contraire d'un refuge prêt à habiter."""
    for titre in ("Maison 3 chambres + Terrain à Saint Etienne en Bresse !",
                  "Maison + Terrain à OSLON ! - Bourgogne Bâtir",
                  "Votre Maison Connectée avec DELTA DORE",
                  "Terrain à bâtir viabilisé"):
        assert not est_bien_valide(
            {"titre": titre, "type_bien": "maison", "surface_m2": 90,
             "prix": 55000}), titre

    # Une maison existante vendue AVEC son terrain reste un bien valide :
    # c'est la formule « maison + terrain » du constructeur qu'on écarte,
    # pas le fait d'avoir du terrain.
    assert est_bien_valide(
        {"titre": "Longère rénovée avec 5000 m² de terrain arboré",
         "type_bien": "longère", "surface_m2": 150, "prix": 245000})


def test_le_constructeur_est_ecarte_des_la_decouverte():
    """Mieux vaut ne jamais le brancher que filtrer ses annonces ensuite."""
    from app.decouverte import est_constructeur

    assert est_constructeur("Bourgogne Bâtir")
    assert est_constructeur("Bourgogne Batir")          # sans accent
    assert est_constructeur("Constructions Dupont")
    # Une agence ordinaire n'est pas écartée.
    assert not est_constructeur("Terres du Perche")
    assert not est_constructeur("Century 21 Agence Massot")


def test_abreviations_appartement_ecartees():
    """Cas réel : « A VENDRE APPT T2 » passait à travers « appartements? »."""
    assert not est_bien_valide({"titre": "A VENDRE APPT T2 A LA FERTÉ SOUS JOUARRE",
                                "surface_m2": 45, "prix": 95000})
    assert not est_bien_valide({"titre": "Vente appart 3 pièces centre-ville",
                                "surface_m2": 65, "prix": 120000})
    # « T6 » seul ne disqualifie pas : une maison peut être un T6.
    assert est_bien_valide({"titre": "A VENDRE MAISON T6 DANS HAMEAU",
                            "type_bien": "maison", "surface_m2": 140, "prix": 235000})


def test_locations_ecartees_du_catalogue():
    """Cas réel : dix annonces de LOCATION dans un catalogue de vente.

    Sans prix de vente, elles n'ont ni prix au m² ni écart au marché — et
    l'une d'elles affichait 199 800 €, un montant récupéré ailleurs sur la
    page, qui la faisait passer pour une vraie vente.
    """
    # Repérée par le titre
    assert not est_bien_valide({"titre": "Maison à louer Savonnières",
                                "type_bien": "maison", "surface_m2": 120})
    assert not est_bien_valide({"titre": "F3 A louer a Fécamp",
                                "type_bien": "maison", "surface_m2": 55})
    assert not est_bien_valide({"titre": "Location Maison 4 pièces 82 m² Déols",
                                "type_bien": "maison", "surface_m2": 82})
    # Repérée par l'URL, alors que le titre ne dit rien
    assert not est_bien_valide(
        {"titre": "MAISON T4", "type_bien": "maison", "surface_m2": 96,
         "url": "https://agence.fr/location/maison-4-pieces-monts-37260"})
    assert not est_bien_valide(
        {"titre": "Maison 4 pièces 85 m² Veigné", "type_bien": "maison",
         "surface_m2": 85,
         "url": "https://agence.fr/fr/louer/maison/veigne-37250"})
    assert not est_bien_valide(
        {"titre": "MAISON F3 PLAIN PIED SALENCY", "type_bien": "maison",
         "surface_m2": 66,
         "url": "https://cabinet-reca.fr/a-louer/maison-f3-salency-l50002559/"})
    # Faux positif à éviter : un domaine de portail qui contient « alouer ».
    assert est_bien_valide(
        {"titre": "Longère 4 chambres à Bellême", "type_bien": "longère",
         "surface_m2": 140, "prix": 245000,
         "url": "https://www.avendrealouer.fr/vente/belleme/longere-12345.html"})


def test_une_vraie_maison_contemporaine_reste_au_catalogue():
    """« maison contemporaine » désignait un modèle de constructeur — la règle
    écartait aussi cette annonce réelle de Larçay."""
    assert est_bien_valide(
        {"titre": "Magnifique maison Contemporaine", "type_bien": "maison",
         "surface_m2": 165, "prix": 425000,
         "url": "https://www.pantherimmo.com/vente/137-larcay/maison/t5/82-magnifique-maison-contemporaine/"})
    # Les pages de constructeur restent écartées, par d'autres signaux.
    assert not est_bien_valide(
        {"titre": "Votre Maison Connectée avec DELTA DORE - Bourgogne Bâtir",
         "type_bien": "maison", "surface_m2": 110, "prix": 180000})


def test_pages_catalogue_ecartees():
    """Cas réels : l'extraction y prend le prix et la surface de la première
    vignette, ce qui les faisait passer pour un bien à part entière."""
    for titre in ("177 Maisons à vendre",
                  "22 Villas et maisons à vendre",
                  "Vente de maisons et villas | Agence du Centre",
                  "Biens immobiliers à vendre | Berry Immobilier",
                  "Maisons à vendre à Pont-l'Évêque"):
        assert not est_bien_valide(
            {"titre": titre, "type_bien": "maison", "surface_m2": 370,
             "prix": 212000}), titre
    # Page de glossaire repérée par son URL.
    assert not est_bien_valide(
        {"titre": "Biens immobiliers - Office b", "type_bien": "maison",
         "surface_m2": 721, "prix": 240000,
         "url": "https://www.office-b.fr/lexique/biens-immobiliers/"})


def test_une_annonce_singuliere_reste_valide():
    """« Maison à vendre à Barentin » est une vraie annonce : singulier, pas
    de décompte. La règle contre les catalogues ne doit pas l'emporter."""
    assert est_bien_valide(
        {"titre": "Maison à vendre à Barentin : 5 pièces avec jardin",
         "type_bien": "maison", "surface_m2": 120, "prix": 245000,
         "url": "https://biasimmobilier.fr/maison-barentin-5p/"})


def test_colocation_et_meuble_sans_prix_sont_des_locations():
    """Cas réels du 10 octobre 2026 : onze chambres en colocation, F2 et T1
    meublés servis comme des maisons à vendre, chez cinq agences — tous sans
    prix, le loyer n'ayant pas été lu comme un prix de vente."""
    for titre in ("Chambre en colocation &#8211; Avenue de Strasbourg &#8211; NANCY",
                  "Co-living/Colocation &#8211; NANCY Fac de lettre / Fac de droit",
                  "Colocation meublée - 3 chambres disponibles à deux pas de la plage",
                  "T1 meublé", "T1 VIEILLE VILLE non meublé",
                  "F2 MEUBLE (N°6) CHARLEVILLE MEZIERES", "MAISON MEUBLE CHARNY"):
        assert motif_de_rejet({"titre": titre, "type_bien": "maison",
                               "surface_m2": 45, "pieces": 3}) == "location", titre
    # Avec un prix, « colocation » et « meublé » décrivent un immeuble
    # d'investisseur, à vendre : on ne les touche pas.
    for titre, prix in (("Roubaix, immeuble de colocation 4 chambres", 165800),
                        ("Lille Esquermes - Maison 2 Chambres/Idéal colocation", 134000),
                        ("Immeuble quartier Gare loué en meublé", 540000)):
        assert est_bien_valide({"titre": titre, "type_bien": "maison",
                                "surface_m2": 120, "prix": prix}), titre
    # « Cuisine meublée » décrit une cuisine, pas un bail — même sans prix.
    assert est_bien_valide({"titre": "F3 en duplex avec cuisine meublée et équipée",
                            "type_bien": "maison", "surface_m2": 70})


def test_un_commerce_se_reconnait_a_sa_rubrique():
    """Mesuré le 10 octobre 2026 : quarante-cinq commerces servis comme des
    maisons — restaurants, bars, salon de coiffure, garage, murs commerciaux —
    chez une vingtaine d'agences. Leur titre ne dit rien d'un local ; leur
    adresse, si : /vente-pro/, /fonds-de-commerce/, /local-commercial/,
    /murs-commerciaux/, /local-professionnel/, et chez IAD
    « local-commercial-vente-Commune »."""
    commerces = [
        ("Restaurant à vendre à Champenoux",
         "https://www.immobi.com/vente-pro/60-champenoux/fonds-de-commerce/3044-restaurant-a-vendre-a-champenoux"),
        ("Axe Passant,", "https://www.cric.fr/vente/fonds-de-commerce"),
        ("salon coiffure",
         "https://www.aude-immo-18.com/vente-pro/1-nerondes/fonds-de-commerce/12-salon-coiffure"),
        ("- BATIMENT COMMERCIAL -", "https://www.bapimmo.fr/vente/local-professionnel"),
        ("Bar-brasserie de 185 m² à CHÂTEAU-RENARD (45220)",
         "https://www.iadfrance.fr/annonce/local-commercial-vente-chateau-renard-185m2/r1956894"),
        ("Immeuble - 340 m² - EPINAL",
         "https://www.immobi.com/vente-pro/1-epinal/murs-commerciaux/3155-immeuble-340-m-epinal"),
        ("Roubaix Immeuble à usage professionnel de 167 m²",
         "https://www.vipimmobilier.fr/vente/local-commercial"),
    ]
    for titre, url in commerces:
        assert motif_url_hors_cible(url) == "url_type_exclu", url
        assert motif_de_rejet({"titre": titre, "url": url, "type_bien": "maison",
                               "surface_m2": 120, "prix": 150000}) == "url_type_exclu", url
    # Le mot au MILIEU du libellé d'une maison ne la condamne pas : sa rubrique
    # à elle est /maison/, et son libellé commence par autre chose.
    url = "https://www.agence.fr/vente/2-auxerre/maison/3555-centre-ville-local-professionnel-ou-habitation"
    assert motif_url_hors_cible(url) is None, url
    assert est_bien_valide({"titre": "Maison 8 pièces 160 m² Auxerre", "url": url,
                            "type_bien": "maison", "surface_m2": 160, "prix": 249000}), url
    # Mais un libellé qui COMMENCE par « immeuble », même sous /maison/, dit le
    # type que l'agence lui a donné : depuis le 13 octobre 2026, il l'emporte.
    assert motif_url_hors_cible(
        "https://www.agence.fr/vente/10-brienne/maison/9280-immeuble-mixte-avec-grand-appartement-et-local-commercial"
    ) == "url_type_exclu"


def test_le_nom_de_l_agence_n_est_pas_le_type_du_bien():
    """Mesuré le 15 octobre 2026 au déroulé de collecte : Loft & House —
    Vimont, dans l'Orne, en plein dans la cible —, 14 pages ouvertes, 0
    gardée, 12 refusées « loft ». Chaque titre de ce site se termine par le
    nom de l'agence : « Maison de 6 pièces de 168,21 m² à VIMONT - Loft &
    House ». Six autres agences portent un mot de règle dans leur nom
    (Bon'Appart, Logimmo Conseil, Ifc Conseils…), et aucune des sept n'a
    jamais versé une ligne au catalogue. On lit le type dans le titre
    débarrassé du nom de l'agence ; le reste du titre garde toute sa force."""
    maison = {"titre": "Maison de 6 pièces de 168,21 m² à VIMONT - Loft & House",
              "agence": "Loft & House", "type_bien": "maison",
              "url": "https://www.lofthouseimmo.fr/bien-immobilier/maison-6-pieces-168-m2-vimont-61603110/",
              "surface_m2": 168.21, "prix": 262000, "pieces": 6}
    assert motif_de_rejet(maison) is None
    assert est_bien_valide(maison)
    # Le mot hors du nom de l'agence condamne toujours.
    assert motif_de_rejet({**maison, "titre": "Loft atypique à Caen - Loft & House"}) == "titre_hors_cible:loft"
    assert motif_de_rejet({**maison, "agence": "Bon'Appart",
                           "titre": "Appartement T2 à Lille - Bon'Appart"}) == "titre_hors_cible:appartement"
    assert motif_de_rejet({**maison, "agence": "Logimmo Conseil",
                           "titre": "Nos conseils pour bien vendre - Logimmo Conseil"}) == "titre_hors_cible:conseils"
    # Sans agence connue, rien ne peut être retiré : la règle d'avant, intacte.
    assert motif_de_rejet({k: v for k, v in maison.items() if k != "agence"}) == "titre_hors_cible:loft"
