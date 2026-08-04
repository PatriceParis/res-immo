"""Tests de la découverte d'agences (source OpenStreetMap).

Le réseau n'est pas sollicité : on vérifie le parsing d'une réponse Overpass,
le filtrage des portails, le score et la fusion dans la configuration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.decouverte import (  # noqa: E402
    ZONES, agences_depuis_overpass, domaine, est_portail_exclu, fusionner,
    requete_overpass, score_candidat, urls_de_biens,
)

# Réponse Overpass telle que l'API la renvoie (nœuds et chemins mélangés).
REPONSE = {
    "elements": [
        {"type": "node", "id": 1,
         "tags": {"office": "estate_agent", "name": "Agence de la Marne",
                  "website": "https://www.agence-marne.fr/"}},
        # Même agence via un autre nœud (doublon de domaine) : à ignorer.
        {"type": "node", "id": 2,
         "tags": {"office": "estate_agent", "name": "Agence de la Marne (bis)",
                  "website": "http://agence-marne.fr/contact"}},
        # Site renseigné dans contact:website plutôt que website.
        {"type": "way", "id": 3,
         "tags": {"shop": "estate_agent", "name": "Immo Vallée",
                  "contact:website": "https://immo-vallee.fr"}},
        # Portail national : ce n'est pas une agence locale.
        {"type": "node", "id": 4,
         "tags": {"office": "estate_agent", "name": "Vitrine SeLoger",
                  "website": "https://www.seloger.com/agence/123"}},
        # Page Facebook : inexploitable.
        {"type": "node", "id": 5,
         "tags": {"office": "estate_agent", "name": "Agence Facebook",
                  "website": "https://facebook.com/agence"}},
        # Sans site web : rien à collecter.
        {"type": "node", "id": 6,
         "tags": {"office": "estate_agent", "name": "Agence sans site"}},
    ]
}


def test_requete_overpass_cible_les_agences_autour_de_la_ville():
    r = requete_overpass({"nom": "X", "lat": 49.045, "lon": 3.4028, "rayon_km": 30})
    assert '"office"="estate_agent"' in r
    assert "around:30000,49.045,3.4028" in r
    assert "[out:json]" in r


def test_parsing_overpass_et_dedoublonnage():
    agences = agences_depuis_overpass(REPONSE, "Château-Thierry")
    noms = [a["nom"] for a in agences]
    assert noms == ["Agence de la Marne", "Immo Vallée"]      # doublon + portails écartés
    assert agences[0]["site"] == "https://agence-marne.fr"    # normalisé (sans www)
    assert agences[0]["zone"] == "Château-Thierry"


def test_portails_et_reseaux_sociaux_ecartes():
    assert est_portail_exclu("https://www.seloger.com/x")
    assert est_portail_exclu("https://facebook.com/agence")
    assert est_portail_exclu("")
    assert not est_portail_exclu("https://www.perch-immo.fr")


def test_domaine():
    assert domaine("https://www.Agence-Marne.FR/nos-biens") == "agence-marne.fr"
    assert domaine("agence.fr") == "agence.fr"
    assert domaine("") == ""


def test_urls_de_biens_filtre_par_domaine_et_motif():
    urls = [
        "https://a.fr/vente/12-maison-belleme",     # bien
        "https://a.fr/nos-biens/8-longere",         # bien
        "https://a.fr/contact",                     # pas un bien
        "https://autre.fr/vente/9-maison",          # autre domaine
        "https://a.fr/vente/12-maison-belleme",     # doublon
    ]
    gardees = urls_de_biens(urls, "https://a.fr")
    assert gardees == ["https://a.fr/vente/12-maison-belleme",
                       "https://a.fr/nos-biens/8-longere"]


def test_score_privilegie_les_sites_exploitables():
    riche = score_candidat({"joignable": True, "nb_biens": 40,
                            "sitemap": True, "schema_org": True})
    pauvre = score_candidat({"joignable": True, "nb_biens": 2,
                             "sitemap": False, "schema_org": False})
    injoignable = score_candidat({"joignable": False, "nb_biens": 99})
    assert riche > pauvre > injoignable == 0


def test_fusion_ignore_les_agences_deja_suivies_et_les_faibles():
    existantes = [{"nom": "Perch'Immo", "site": "https://www.perch-immo.fr"}]
    candidates = [
        {"nom": "Bonne agence", "site": "https://bonne.fr", "note": 70, "zone": "Noyon"},
        {"nom": "Perch'Immo (doublon)", "site": "https://perch-immo.fr", "note": 90},
        {"nom": "Site pauvre", "site": "https://pauvre.fr", "note": 5},
    ]
    toutes, ajoutees = fusionner(existantes, candidates, note_mini=25)
    assert [a["nom"] for a in ajoutees] == ["Bonne agence"]
    assert len(toutes) == 2
    assert ajoutees[0]["max"] and ajoutees[0]["pages"]      # réglages de collecte


def test_zones_couvrent_les_villes_demandees():
    noms = {z["nom"] for z in ZONES}
    assert {"Château-Thierry", "Noyon", "Vendôme", "Beauvais"} <= noms
    for z in ZONES:
        assert -5 < z["lon"] < 10 and 41 < z["lat"] < 52     # bien en France


def test_tete_de_reseau_exclue_mais_agence_locale_gardee():
    """OpenStreetMap donne souvent l'adresse NATIONALE d'une franchise locale.

    Collecter sur orpi.com ramènerait des dizaines de milliers de biens de
    toute la France. Mais quentimmo.fr ou compiegne.arthurimmo.com sont, eux,
    de vraies agences de terrain : il ne faut pas les perdre.
    """
    assert est_portail_exclu("https://orpi.com")
    assert est_portail_exclu("https://www.laforet.com/agence/compiegne")
    assert est_portail_exclu("https://eraimmobilier.com")
    assert est_portail_exclu("https://arthurimmo.com")
    # Déclinaisons locales : conservées.
    assert not est_portail_exclu("https://compiegne.arthurimmo.com")
    assert not est_portail_exclu("https://century21-vandome-crepy.com")
    assert not est_portail_exclu("https://quentimmo.fr")


def test_catalogue_demesure_trahit_un_portail():
    """Garde-fou indépendant de la liste de réseaux, qui ne peut être exhaustive :
    une agence de terroir n'a pas des milliers de biens en vitrine."""
    portail = {"joignable": True, "nb_biens": 69519, "sitemap": True,
               "schema_org": True, "site": "https://inconnu-national.fr"}
    locale = {"joignable": True, "nb_biens": 77, "sitemap": True,
              "schema_org": True, "site": "https://agence-locale.fr"}
    assert score_candidat(portail) == 0
    assert score_candidat(locale) > 50


def test_les_passes_se_cumulent_au_lieu_de_s_ecraser():
    """Overpass ne répond pas pour les mêmes zones d'une passe à l'autre.

    Cas réel : Compiègne a répondu à la 1re passe, Vendôme à la 2e. Écraser le
    rapport ferait perdre la moitié du travail à chaque fois.
    """
    from app.decouverte import fusionner_rapports

    passe1 = [{"site": "https://compiegne.fr", "note": 80, "zone": "Compiègne"},
              {"site": "https://beauvais.fr", "note": 40, "zone": "Beauvais"}]
    passe2 = [{"site": "https://vendome.fr", "note": 76, "zone": "Vendôme"},
              # Même site que la passe 1, mieux sondé cette fois : on garde le meilleur.
              {"site": "https://beauvais.fr", "note": 89, "zone": "Beauvais"}]

    cumul = fusionner_rapports(passe1, passe2)
    par_site = {s["site"]: s["note"] for s in cumul}
    assert set(par_site) == {"https://compiegne.fr", "https://beauvais.fr",
                             "https://vendome.fr"}
    assert par_site["https://beauvais.fr"] == 89        # le meilleur sondage l'emporte
    assert [s["note"] for s in cumul] == sorted((s["note"] for s in cumul), reverse=True)


def test_constructeurs_de_maisons_neuves_ecartes():
    """Une maison neuve de lotissement n'a ni cave, ni dépendance, ni terrain
    nourricier : c'est l'inverse d'un refuge."""
    from app.decouverte import est_constructeur

    assert est_constructeur("Maisons France Confort")
    assert est_constructeur("Maisons Pierre")
    assert est_constructeur("Trecobat constructeur")
    assert not est_constructeur("Perch'Immo")
    assert not est_constructeur("Maison du Perche")     # agence, pas constructeur

    _, ajoutees = fusionner(
        [], [{"nom": "Maisons France Confort", "site": "https://mfc.fr", "note": 80},
             {"nom": "Agence du Bourg", "site": "https://bourg.fr", "note": 60}], 25)
    assert [a["nom"] for a in ajoutees] == ["Agence du Bourg"]
