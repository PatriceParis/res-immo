"""Tri des annonces d'un réseau de mandataires, avant toute visite.

Le tri se fait sur l'ADRESSE : c'est ce qui rend la chose praticable — on ne
télécharge que ce qu'on garde — et c'est donc là que se jouent les erreurs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import mandataires  # noqa: E402

IAD = mandataires.RESEAUX["iad"]

COMMUNES = {
    "71": ["Saint-Bérain-sur-Dheune", "Givry", "Chalon-sur-Saône", "Bérain"],
    "89": ["Chablis", "Appoigny"],
    "61": ["Bellême"],
}
INDEX = mandataires.index_des_communes(COMMUNES)


def test_une_maison_de_nos_terroirs_est_retenue():
    """L'annonce qui a ouvert la piste."""
    url = ("https://www.iadfrance.fr/annonce/"
           "maison-vente-6-pieces-saint-berain-sur-dheune-245m2/r1949496")
    retenues = mandataires.annonces_a_visiter([url], IAD, INDEX)
    assert len(retenues) == 1
    assert retenues[0]["commune"] == "Saint-Bérain-sur-Dheune"
    assert retenues[0]["departement"] == "71"
    assert retenues[0]["agence"] == "IAD France (71)"


def test_le_nom_le_plus_long_gagne():
    """« Bérain » est aussi une commune : sans tri par longueur, l'annonce de
    Saint-Bérain-sur-Dheune serait rattachée à la mauvaise."""
    url = ("https://www.iadfrance.fr/annonce/"
           "maison-vente-6-pieces-saint-berain-sur-dheune-245m2/r1949496")
    commune, _dept = mandataires.commune_de_l_adresse(url, INDEX)
    assert commune == "Saint-Bérain-sur-Dheune"


def test_les_appartements_ne_sont_jamais_telecharges():
    urls = [
        "https://www.iadfrance.fr/annonce/appartement-vente-3-pieces-givry-70m2/r1",
        "https://www.iadfrance.fr/annonce/studio-vente-1-piece-chablis-25m2/r2",
        "https://www.iadfrance.fr/annonce/terrain-vente-givry-800m2/r3",
        "https://www.iadfrance.fr/annonce/parking-vente-chalon-sur-saone/r4",
    ]
    assert mandataires.annonces_a_visiter(urls, IAD, INDEX) == []


def test_les_communes_hors_terroir_sont_ecartees():
    url = "https://www.iadfrance.fr/annonce/maison-vente-3-pieces-antony-70m2/r2087669"
    assert mandataires.annonces_a_visiter([url], IAD, INDEX) == []


def test_les_pages_qui_ne_sont_pas_des_annonces_sont_ecartees():
    """robots.txt d'IAD interdit /liste/annonces* : on ne doit jamais y aller."""
    urls = ["https://www.iadfrance.fr/liste/annonces/maison-givry",
            "https://www.iadfrance.fr/conseiller-immobilier/jean-dupont"]
    assert mandataires.annonces_a_visiter(urls, IAD, INDEX) == []


def test_les_types_refuge_sont_tous_acceptes():
    urls = [f"https://www.iadfrance.fr/annonce/{t}-vente-5-pieces-belleme-200m2/r{n}"
            for n, t in enumerate(("maison", "longere", "ferme", "moulin",
                                   "chateau", "manoir", "propriete"))]
    assert len(mandataires.annonces_a_visiter(urls, IAD, INDEX)) == len(urls)


def test_une_meme_adresse_n_est_retenue_qu_une_fois():
    url = "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-chablis-90m2/r9"
    assert len(mandataires.annonces_a_visiter([url, url, url], IAD, INDEX)) == 1


def test_le_decoupage_par_departement_donne_une_agence_par_departement():
    """Sans ce découpage, `historique.fusionner` supprimerait à chaque passage
    tout ce que le passage n'a pas eu le temps de revoir."""
    urls = ["https://www.iadfrance.fr/annonce/maison-vente-4-pieces-givry-90m2/r1",
            "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-chablis-90m2/r2",
            "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-belleme-90m2/r3"]
    groupes = mandataires.par_departement(
        mandataires.annonces_a_visiter(urls, IAD, INDEX))
    assert set(groupes) == {"71", "89", "61"}
    agences = {a["agence"] for lot in groupes.values() for a in lot}
    assert agences == {"IAD France (71)", "IAD France (89)", "IAD France (61)"}


def test_les_departements_vus_il_y_a_le_plus_longtemps_passent_devant():
    """Le journal est indexé PAR RÉSEAU — « iad:71 », jamais « 71 ». Ce test
    passait un journal à clés nues, qui n'existe nulle part : il validait donc
    une fiction, et la rotation était morte en production sans qu'il bronche.
    Voir tests/test_rotation_departements.py."""
    groupes = {"71": [], "89": [], "61": []}
    vu = {"iad:71": "2026-08-07", "iad:89": "2026-08-01"}   # 61 jamais visité
    assert mandataires.ordre_des_departements(groupes, vu, "iad") == ["61", "89", "71"]


def test_une_commune_trop_courte_ne_cree_pas_de_faux_rapprochement():
    """« Ay », « Bu », « Oz » existent : trop courtes, elles se retrouveraient
    dans presque n'importe quelle adresse."""
    index = mandataires.index_des_communes({"51": ["Ay", "Bu"]})
    assert index == []


SAFTI = mandataires.RESEAUX["safti"]


def test_safti_retient_ses_maisons_et_ecarte_le_reste():
    """Ses adresses portent le type, la commune ET le code postal."""
    urls = [
        "https://www.safti.fr/annonces/achat/maison/givry-71640/1480990",
        "https://www.safti.fr/annonces/achat/appartement/chablis-89800/1480991",
        "https://www.safti.fr/annonces/achat/maison/antony-92160/1480992",
        "https://www.safti.fr/recherche?location=givry",
    ]
    retenues = mandataires.annonces_a_visiter(urls, SAFTI, INDEX)
    assert [a["commune"] for a in retenues] == ["Givry"]
    assert retenues[0]["agence"] == "Safti (71)"


def test_safti_ne_lit_que_les_sitemaps_de_maisons_disponibles():
    """Lire les 73 626 adresses pour n'en garder que les maisons à vendre
    serait inutilement lourd — pour eux comme pour nous."""
    voulus = SAFTI["sitemaps_voulus"]
    garde = "https://www.safti.fr/sitemaps/sitemap.annonce.maison.disponible.xml"
    assert voulus.search(garde)
    for ecarte in (
            "https://www.safti.fr/sitemaps/sitemap.annonce.maison.vendu.xml",
            "https://www.safti.fr/sitemaps/sitemap.annonce.appartement.disponible.xml",
            "https://www.safti.fr/sitemaps/sitemap.annonce.commerce.disponible.xml",
            "https://www.safti.fr/sitemaps/sitemap.mandataires.xml"):
        assert not voulus.search(ecarte), ecarte


def test_on_progresse_dans_un_departement_au_lieu_de_relire_les_memes():
    """Un passage ne visite que quelques dizaines d'annonces par département.
    En prenant toujours les premières du sitemap, les 1 308 autres annonces
    de Saône-et-Loire n'auraient jamais été atteintes."""
    annonces = [{"url": f"https://iad.fr/annonce/maison-givry-{n}"} for n in range(5)]
    deja = {
        "https://iad.fr/annonce/maison-givry-0": "2026-08-07",   # vue hier
        "https://iad.fr/annonce/maison-givry-1": "2026-08-01",   # vue avant
        # les 2, 3 et 4 sont inconnues
    }
    ordre = [a["url"].rsplit("-", 1)[1]
             for a in mandataires.ordre_dans_le_departement(annonces, deja)]
    assert ordre[:3] == ["2", "3", "4"], "les inconnues d'abord"
    assert ordre[3:] == ["1", "0"], "puis la plus anciennement revue"


def test_une_page_ouverte_et_refusee_compte_comme_vue():
    """Mesuré le 17 octobre 2026 en Côte-d'Or : 50 pages ouvertes, 2 gardées,
    48 refusées — vendues, ou d'autres régions qu'un nom de commune trompait.
    Le catalogue ne connaissant que les gardées, les 48 restaient « jamais
    vues » et repassaient en tête à chaque passage. La plus récente des deux
    dates — gardée au catalogue, refusée au journal — fait foi."""
    catalogue = {"https://iad.fr/annonce/a": "2026-09-01",
                 "https://iad.fr/annonce/b": "2026-10-10"}
    ecartees = {"https://iad.fr/annonce/a": {"jour": "2026-10-17", "motif": "vendu"},
                "https://iad.fr/annonce/b": {"jour": "2026-09-20", "motif": "vendu"},
                "https://iad.fr/annonce/c": {"jour": "2026-10-17", "motif": "hors_perimetre"}}
    dates = mandataires.dates_de_derniere_visite(catalogue, ecartees)
    assert dates == {"https://iad.fr/annonce/a": "2026-10-17",
                     "https://iad.fr/annonce/b": "2026-10-10",
                     "https://iad.fr/annonce/c": "2026-10-17"}
    assert mandataires.dates_de_derniere_visite(catalogue, {}) == catalogue


def test_safti_ouvre_d_abord_ce_que_le_code_postal_de_l_adresse_place_chez_nous():
    """Mesuré le 17 octobre 2026 au passage de 17 h 46 : 92 des 104 pages
    Safti ouvertes dans l'Aisne, les Ardennes et l'Aube étaient des biens
    d'ailleurs — Bagneux (92) pris pour Bagneux (02), Antezant-la-Chapelle
    (17) pour La Chapelle (08) —, et leur adresse le disait. Elles passent
    après les autres, sans être écartées : l'adresse peut se tromper aussi."""
    index = mandataires.index_des_communes({"02": ["Bagneux", "Vervins"], "71": ["Givry"]})
    urls = ["https://www.safti.fr/annonces/achat/maison/bagneux-92220/1627891",
            "https://www.safti.fr/annonces/achat/maison/vervins-02140/1700001",
            "https://www.safti.fr/annonces/achat/maison/bagneux-02290/1700002"]
    retenues = mandataires.annonces_a_visiter(urls, SAFTI, index)
    assert len(retenues) == 3, "aucune n'est écartée"
    assert [a["hors_cible_selon_l_adresse"] for a in retenues] == [True, False, False]
    deja = {"https://www.safti.fr/annonces/achat/maison/vervins-02140/1700001": "2026-10-01"}
    ordre = [a["url"].rsplit("/", 1)[1] for a in mandataires.ordre_dans_le_departement(retenues, deja)]
    assert ordre == ["1700002", "1627891", "1700001"], \
        "jamais vue chez nous, puis jamais vue d'ailleurs, puis la déjà vue"
    # IAD ne met pas de code dans ses adresses : rien ne change pour lui.
    iad = mandataires.annonces_a_visiter(
        ["https://www.iadfrance.fr/annonce/maison-vente-4-pieces-givry-90m2/r1"], IAD, index)
    assert iad[0]["hors_cible_selon_l_adresse"] is False
