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
    groupes = {"71": [], "89": [], "61": []}
    vu = {"71": "2026-08-07", "89": "2026-08-01"}      # 61 jamais visité
    assert mandataires.ordre_des_departements(groupes, vu) == ["61", "89", "71"]


def test_une_commune_trop_courte_ne_cree_pas_de_faux_rapprochement():
    """« Ay », « Bu », « Oz » existent : trop courtes, elles se retrouveraient
    dans presque n'importe quelle adresse."""
    index = mandataires.index_des_communes({"51": ["Ay", "Bu"]})
    assert index == []
