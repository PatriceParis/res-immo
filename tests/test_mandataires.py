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


# Un extrait de la France : nos départements, et quelques communes d'ailleurs
# dont le nom prolonge ou contient celui d'une des nôtres.
FRANCE = {
    "72": ["Champagné"], "21": ["Saint-Laurent", "Beaulieu", "Sainte-Marie"],
    "89": ["Valravillon"],
    "77": ["Champagne-sur-Seine"], "30": ["Saint-Laurent-le-Minier"],
    "64": ["Oloron-Sainte-Marie"], "49": ["Beaulieu"],
}
CIBLES = {"72", "21", "89"}


def test_un_nom_plus_long_ailleurs_en_france_n_est_pas_ouvert():
    """Mesuré le 19 octobre 2026 : 151 des 262 pages IAD ouvertes au passage
    de 20 h 24 étaient « hors périmètre ». Les noms tronqués en étaient la
    première cause : sans connaître les communes d'ailleurs, on ne pouvait pas
    savoir que « saint-laurent-le-minier » n'est pas Saint-Laurent."""
    index = mandataires.index_des_communes(FRANCE, CIBLES)
    ailleurs = [
        "https://www.iadfrance.fr/annonce/maison-vente-10-pieces-champagne-sur-seine-208m2/r1",
        "https://www.iadfrance.fr/annonce/maison-vente-10-pieces-saint-laurent-le-minier-82m2/r2",
        "https://www.iadfrance.fr/annonce/maison-vente-10-pieces-oloron-sainte-marie-260m2/r3",
    ]
    assert mandataires.annonces_a_visiter(ailleurs, IAD, index, CIBLES) == []
    chez_nous = [
        "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-champagne-90m2/r4",
        "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-saint-laurent-90m2/r5",
        "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-sainte-marie-90m2/r6",
    ]
    retenues = mandataires.annonces_a_visiter(chez_nous, IAD, index, CIBLES)
    assert [(a["commune"], a["departement"]) for a in retenues] == [
        ("Champagné", "72"), ("Saint-Laurent", "21"), ("Sainte-Marie", "21")]


def test_a_nom_egal_nos_terroirs_passent_devant():
    """Un vrai homonyme reste chez nous, comme quand l'index ne connaissait
    que nos communes : le Beaulieu du Maine-et-Loire ne doit pas faire perdre
    celui de Côte-d'Or — quel que soit l'ordre où l'API rend les départements."""
    for france in (FRANCE, dict(reversed(list(FRANCE.items())))):
        index = mandataires.index_des_communes(france, CIBLES)
        url = "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-beaulieu-90m2/r7"
        retenues = mandataires.annonces_a_visiter([url], IAD, index, CIBLES)
        assert [(a["commune"], a["departement"]) for a in retenues] == [("Beaulieu", "21")]


def test_une_commune_nouvelle_ecrite_avec_l_ancienne_reste_chez_nous():
    """IAD écrit « laduz-valravillon » : Laduz n'existe plus, fondue dans
    Valravillon. Exiger que la commune couvre tout le nom de l'adresse aurait
    perdu ce bien ; le nom le plus long connu, lui, est bien chez nous."""
    index = mandataires.index_des_communes(FRANCE, CIBLES)
    url = "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-laduz-valravillon-75m2/r8"
    retenues = mandataires.annonces_a_visiter([url], IAD, index, CIBLES)
    assert [(a["commune"], a["departement"]) for a in retenues] == [("Valravillon", "89")]


def test_un_homonyme_bien_plus_peuple_ailleurs_fait_passer_la_page_apres():
    """Mesuré le 26 octobre 2026 : 16 des 44 pages IAD ouvertes pour la
    Haute-Saône étaient des maisons de La Rochelle — la ville de
    Charente-Maritime, pas le hameau d'une quarantaine d'habitants. Ces pages
    passent après les autres et quelques-unes seulement sont ouvertes par
    passage ; deux Beaulieu de taille voisine, eux, ne changent rien."""
    france = {"70": ["La Rochelle", "Vesoul"], "17": ["La Rochelle"],
              "21": ["Beaulieu"], "49": ["Beaulieu"]}
    cibles = {"70", "21"}
    populations = {("70", "La Rochelle"): 41, ("17", "La Rochelle"): 77205,
                   ("70", "Vesoul"): 14678,
                   ("21", "Beaulieu"): 312, ("49", "Beaulieu"): 640}
    ecrases = mandataires.homonymes_ecrases(populations, cibles)
    assert ecrases == {"la-rochelle"}
    index = mandataires.index_des_communes(france, cibles)
    urls = ["https://www.iadfrance.fr/annonce/maison-vente-4-pieces-la-rochelle-90m2/r1",
            "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-beaulieu-90m2/r2",
            "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-vesoul-90m2/r3"]
    retenues = mandataires.annonces_a_visiter(urls, IAD, index, cibles, ecrases)
    assert [(a["commune"], a["hors_cible_selon_l_adresse"]) for a in retenues] == [
        ("La Rochelle", True), ("Beaulieu", False), ("Vesoul", False)], \
        "retenue, jamais écartée : la maison du hameau finit par être lue"
    # Sans populations — la liste nationale n'a pas répondu —, rien ne change.
    assert mandataires.homonymes_ecrases({}, cibles) == set()


def test_une_ancienne_commune_d_ailleurs_n_est_plus_lue_comme_une_des_notres():
    """Pierrefitte-sur-Seine est fondue dans Saint-Denis depuis le 1er janvier
    2025 : elle a quitté la liste des communes, pas les annonces. Mesuré le
    27 octobre 2026 : sur les 282 pages refusées « hors périmètre » depuis le
    20, 15 l'avaient été à cause d'une ancienne commune — dont six maisons de
    Pierrefitte-sur-Seine, ouvertes pour les Vosges qui ont leur Pierrefitte."""
    france = {"88": ["Pierrefitte"], "93": ["Saint-Denis"]}
    index = mandataires.index_des_communes(france, {"88"}, {"93": ["Pierrefitte-sur-Seine"]})
    urls = ["https://www.iadfrance.fr/annonce/"
            "maison-vente-7-pieces-pierrefitte-sur-seine-118m2/r2052828",
            "https://www.iadfrance.fr/annonce/maison-vente-6-pieces-pierrefitte-142m2/r2135191"]
    retenues = mandataires.annonces_a_visiter(urls, IAD, index, {"88"})
    assert [(a["commune"], a["departement"]) for a in retenues] == [("Pierrefitte", "88")]


def test_une_ancienne_commune_de_chez_nous_est_lue_chez_nous():
    """Saint-Denis-sur-Ouanne est fondue dans Charny Orée de Puisaye, dans
    l'Yonne. Sans elle, l'adresse se lisait « Saint-Denis », hors de nos
    terroirs : la maison, au catalogue, n'avait plus été revue depuis le
    11 octobre 2026."""
    france = {"89": ["Charny Orée de Puisaye"], "11": ["Saint-Denis"], "93": ["Saint-Denis"]}
    index = mandataires.index_des_communes(france, {"89"}, {"89": ["Saint-Denis-sur-Ouanne"]})
    url = "https://www.safti.fr/annonces/achat/maison/saint-denis-sur-ouanne-89120/1589546"
    retenues = mandataires.annonces_a_visiter([url], mandataires.RESEAUX["safti"], index, {"89"})
    assert [(a["commune"], a["departement"], a["hors_cible_selon_l_adresse"])
            for a in retenues] == [("Saint-Denis-sur-Ouanne", "89", False)]


def test_a_nom_egal_une_commune_d_aujourd_hui_passe_devant_une_ancienne():
    """Une ancienne commune ne l'emporte que par la longueur du nom. La Colombe
    de la Manche existe toujours, celle du Loir-et-Cher est fondue dans Beauce
    la Romaine : toutes deux chez nous, la maison de la Manche serait partie
    dans le budget du Loir-et-Cher. Presles du Calvados est fondue dans
    Valdallière, celle du Val-d'Oise est bien vivante : une adresse « presles »
    reste hors de nos terroirs, comme avant. Quel que soit l'ordre des
    départements."""
    cibles = {"50", "41", "14"}
    france = {"50": ["La Colombe"], "41": ["Beauce la Romaine"],
              "14": ["Valdallière"], "95": ["Presles"]}
    anciennes = {"41": ["La Colombe"], "14": ["Presles"]}
    urls = ["https://www.iadfrance.fr/annonce/maison-vente-4-pieces-la-colombe-88m2/r1",
            "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-presles-90m2/r2"]
    for ordre in (lambda d: d, lambda d: dict(reversed(list(d.items())))):
        index = mandataires.index_des_communes(ordre(france), cibles, ordre(anciennes))
        retenues = mandataires.annonces_a_visiter(urls, IAD, index, cibles)
        assert [(a["commune"], a["departement"]) for a in retenues] == [("La Colombe", "50")]


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


def test_un_passage_n_ouvre_que_quelques_pages_que_l_adresse_place_ailleurs():
    """Mesuré le 18 octobre 2026 : chez Safti en Haute-Marne, 42 des 50 pages
    ouvertes étaient des Aigremont du Gard, et leur adresse le disait. Passer
    en dernier ne suffisait pas : le département comptait moins de pages chez
    nous que le lot n'en prend, et le reste allait aux homonymes."""
    index = mandataires.index_des_communes({"52": ["Aigremont", "Langres"]})
    chez_nous = [f"https://www.safti.fr/annonces/achat/maison/langres-52200/17000{n:02d}"
                 for n in range(3)]
    ailleurs = [f"https://www.safti.fr/annonces/achat/maison/aigremont-30350/16000{n:02d}"
                for n in range(20)]
    retenues = mandataires.annonces_a_visiter(chez_nous + ailleurs, SAFTI, index)
    deja = {u: "2026-10-01" for u in chez_nous[1:]}       # deux déjà vues, à revoir
    candidats = mandataires.ordre_dans_le_departement(retenues, deja)
    lot = mandataires.lot_du_passage(candidats, 50)
    assert sum(a["hors_cible_selon_l_adresse"] for a in lot) == mandataires.HORS_CIBLE_PAR_PASSAGE
    assert {a["url"] for a in lot} >= set(chez_nous), "toutes celles de chez nous, même déjà vues"
    assert len(lot) < len(candidats), "des pages restent : le département n'est pas vu en entier"
    # Sans homonyme, rien ne change : le lot est le début de la liste.
    sans = mandataires.ordre_dans_le_departement(
        mandataires.annonces_a_visiter(chez_nous, SAFTI, index), deja)
    assert mandataires.lot_du_passage(sans, 2) == sans[:2]
