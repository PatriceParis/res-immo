"""Recensement des agences : réseaux de franchise et registre officiel.

Les appels réseau vivent dans scripts/recenser_agences.py ; ici on éprouve
la logique qui les exploite, sur des réponses réelles reconstituées.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import decouverte, reseaux, sirene  # noqa: E402


# --- Réseaux de franchise ---------------------------------------------------

COMMUNES = {"60": ["Noyon", "Compiègne", "Beauvais", "Le Meux"],
            "61": ["Bellême", "Mortagne-au-Perche", "Alençon"],
            "41": ["Vendôme", "Montoire-sur-le-Loir"]}
INDEX = reseaux.index_des_communes(COMMUNES)


# Les trois faux positifs du premier recensement réel, et rien d'autre.
COMMUNES_FR = [{"nom": n} for n in (
    "Brétigny", "Brétigny-sur-Orge", "Ville", "Aube", "Bellême", "Noyon",
    "Compiègne", "Beauvais", "Vendôme", "Montluçon")]
NATIONALES = reseaux.occurrences_nationales(COMMUNES_FR)
EXTENSIONS = reseaux.extensions_nationales(COMMUNES_FR)


def test_les_trois_faux_positifs_du_premier_recensement():
    """Le premier recensement réel a ramené 3 agences de réseau, et les trois
    étaient fausses :

      /agence-immobiliere/bretigny        → Brétigny-sur-Orge (91), rattachée
                                            à Brétigny dans l'Oise ;
      /immobilier-montlucon-centre-ville- → la commune « Ville » (60) lue dans
       les-forges/                          une adresse de Montluçon (03) ;
      /square-habitat-champagne-bourgogne/ → la commune « Aube » (61) lue dans
       nos-agences-immo                     « Champagne » … non, dans « Aube ».

    Trois résultats, trois faux : pire que rien, puisqu'ils auraient pollué
    le catalogue.
    """
    index = reseaux.index_des_communes(
        {"60": ["Brétigny", "Ville"], "61": ["Aube", "Bellême"]}, NATIONALES)
    # « Ville » et « Aube » sont trop courants pour servir de repère.
    assert "ville" not in index and "aube" not in index

    def cherche(nom, site, url):
        return reseaux.agences_du_reseau({"nom": nom, "site": site}, [url],
                                         index, EXTENSIONS)

    assert cherche("Laforêt", "https://www.laforet.com",
                   "https://www.laforet.com/agence-immobiliere/bretigny-sur-orge") == []
    assert cherche("Orpi", "https://www.orpi.com",
                   "https://www.orpi.com/immobilier-montlucon-centre-ville-les-forges/") == []
    assert cherche("Square Habitat", "https://www.squarehabitat.fr",
                   "https://www.squarehabitat.fr/square-habitat-champagne-bourgogne/nos-agences-immo") == []

    # Et la vraie agence de Brétigny (Oise) reste trouvée.
    vrai = cherche("Laforêt", "https://www.laforet.com",
                   "https://www.laforet.com/agence-immobiliere/bretigny")
    assert vrai and vrai[0]["departement"] == "60"


def test_une_agence_de_reseau_est_rattachee_a_sa_commune():
    laforet = {"nom": "Laforêt", "site": "https://www.laforet.com"}
    urls = [
        "https://www.laforet.com/agence-immobiliere/noyon",
        "https://www.laforet.com/agence-immobiliere/compiegne",
        "https://www.laforet.com/agence-immobiliere/marseille-8e",   # hors cible
        "https://www.laforet.com/annonces/vente-maison-noyon-123",   # une annonce
        "https://www.laforet.com/recherche/agences",                 # page générique
    ]
    trouvees = reseaux.agences_du_reseau(laforet, urls, INDEX)
    assert [a["site"] for a in trouvees] == [
        "https://www.laforet.com/agence-immobiliere/noyon",
        "https://www.laforet.com/agence-immobiliere/compiegne",
    ]
    assert trouvees[0]["nom"] == "Laforêt Noyon"
    assert trouvees[0]["departement"] == "60"


def test_la_commune_la_plus_longue_l_emporte():
    """« Le Meux » ne doit pas être capté par une URL de Meaux, et un nom
    court ne doit pas primer sur un nom composé qui le contient."""
    index = reseaux.index_des_communes(
        {"45": ["Saint-Jean-de-Braye", "Saint-Jean-le-Blanc"]})
    reseau = {"nom": "Orpi", "site": "https://www.orpi.com"}
    trouvees = reseaux.agences_du_reseau(
        reseau, ["https://www.orpi.com/agence-saint-jean-de-braye"], index)
    assert trouvees[0]["nom"] == "Orpi Saint-Jean-de-Braye"


def test_les_homonymes_entre_departements_sont_ecartes():
    """« Sainte-Marie » existe dans plusieurs départements : la rattacher à
    l'un d'eux au hasard placerait l'agence dans le mauvais terroir."""
    index = reseaux.index_des_communes(
        {"60": ["Sainte-Marie", "Noyon"], "61": ["Sainte-Marie"]})
    assert "sainte-marie" not in index
    assert index["noyon"] == ("60", "Noyon")


def test_un_reseau_de_mandataires_ne_donne_aucune_agence():
    """IAD, Safti, Capifrance… n'ont pas d'agence locale : leurs mandats
    vivent sur un site national unique, qui est un portail."""
    iad = {"nom": "IAD France", "site": "https://www.iadfrance.fr",
           "mandataires": True}
    assert reseaux.agences_du_reseau(
        iad, ["https://www.iadfrance.fr/agence-immobiliere/noyon"], INDEX) == []


def test_une_url_d_un_autre_domaine_est_ignoree():
    laforet = {"nom": "Laforêt", "site": "https://www.laforet.com"}
    assert reseaux.agences_du_reseau(
        laforet, ["https://autre-site.fr/agence-immobiliere/noyon"], INDEX) == []


# --- Registre officiel ------------------------------------------------------


def test_lecture_du_registre():
    reponse = {"results": [
        {"nom_complet": "AGENCE DU PERCHE",
         "matching_etablissements": [
             {"siret": "12345678900011", "code_postal": "61130",
              "libelle_commune": "BELLEME", "adresse": "3 rue Ville Close"}]},
        # Établissement d'un autre département : c'est l'adresse de l'agence
        # qui compte, pas le siège social.
        {"nom_complet": "IMMO AILLEURS",
         "matching_etablissements": [
             {"siret": "22", "code_postal": "75008", "libelle_commune": "PARIS"}]},
        # Activité hors cible.
        {"nom_complet": "SYNDIC DE COPROPRIETE DU PERCHE",
         "matching_etablissements": [
             {"siret": "33", "code_postal": "61000", "libelle_commune": "ALENCON"}]},
    ]}
    agences = sirene.agences_depuis_reponse(reponse, "61")
    assert [a["nom"] for a in agences] == ["AGENCE DU PERCHE"]
    assert agences[0]["commune"] == "Belleme"
    assert agences[0]["departement"] == "61"


def test_la_couverture_dit_ce_qui_manque():
    registre = [
        {"nom": "AGENCE DU PERCHE", "departement": "61"},
        {"nom": "TERRES DU PERCHE", "departement": "61"},
        {"nom": "IMMO BELLEME", "departement": "61"},
    ]
    connues = [{"nom": "Agence du Perche"}, {"nom": "Terres du Perche"}]
    couv = sirene.couverture(registre, connues)
    assert couv["61"]["recensees"] == 3
    assert couv["61"]["reconnues"] == 2
    assert [m["nom"] for m in couv["61"]["manquantes"]] == ["IMMO BELLEME"]


# --- OpenStreetMap ----------------------------------------------------------


def test_requete_par_departement_vise_la_limite_administrative():
    q = decouverte.requete_overpass_departement("61")
    assert '"admin_level"="6"' in q and '"ref:INSEE"="61"' in q
    assert '"office"="estate_agent"' in q


def test_les_agences_sans_site_ne_sont_plus_jetees():
    """C'est la majorité des points OSM : une agence de village a rarement
    renseigné son site, ce qui ne veut pas dire qu'elle n'en a pas."""
    reponse = {"elements": [
        {"tags": {"name": "Agence du Bourg", "addr:city": "Bellême",
                  "addr:postcode": "61130", "phone": "02 33 00 00 00"}},
        {"tags": {"name": "Terres du Perche", "website": "https://terres-perche.fr"}},
        {"tags": {"addr:city": "Mortagne"}},          # sans nom : inexploitable
    ]}
    sans = decouverte.agences_sans_site(reponse, "dept 61")
    assert [a["nom"] for a in sans] == ["Agence du Bourg"]
    assert sans[0]["commune"] == "Bellême" and sans[0]["telephone"]
    # Celle qui a un site reste du ressort de l'autre fonction.
    avec = decouverte.agences_depuis_overpass(reponse, "dept 61")
    assert [a["nom"] for a in avec] == ["Terres du Perche"]
