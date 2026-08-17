"""Ce que les moteurs — et les IA — doivent pouvoir lire.

L'application est une page unique rendue en JavaScript. Google sait
l'exécuter, au prix d'un second passage ; les robots d'IA, non. GPTBot,
ClaudeBot, PerplexityBot et CCBot lisent le HTML tel qu'il arrive, et n'y
trouvaient rien : pas une annonce, pas un lien, pas une donnée structurée.

Ces tests fixent ce qui doit être servi SANS JavaScript. Ils ne mesurent pas
un classement — personne ne peut le promettre — mais ils garantissent la
condition sans laquelle il n'y a pas de classement du tout : que la page
existe, qu'elle se tienne seule, et qu'elle dise la vérité.
"""

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import pages, seo  # noqa: E402

BIEN = {
    "id": "immo-ray-com-a678b1226c04",
    "titre": "Belle longère rénovée",
    "type_bien": "longère", "prix": 250000, "surface_m2": 120.0,
    "terrain_m2": 3250.0, "pieces": 5, "commune": "Bellême",
    "code_postal": "61130", "departement": "61", "region": "Normandie",
    "lat": 48.376, "lon": 0.565, "altitude": 210.0, "dpe": "D",
    "score_total": 46.0, "temps_voiture_min": 110,
    "agence": "Agence du Perche", "agence_url": "https://perche.fr",
    "url": "https://perche.fr/annonce/longere-belleme",
    "photo": "https://perche.fr/photos/1.jpg",
    "badges": ["Chauffage au bois", "Puits"],
    "risques": {"nucleaire_km": 122.6, "nucleaire_nom": "Saint-Laurent",
                "vigilances": ["Retrait-gonflement des argiles"]},
    "revue_le": "2026-08-09",
    "texte": "MAGNIFIQUE longère de charme, coup de cœur assuré ! " * 60,
}


# --- Adresses --------------------------------------------------------------

def test_l_adresse_dit_ce_qu_elle_contient():
    """L'adresse est le premier texte que lit un moteur."""
    assert seo.url_annonce(BIEN) == (
        "/annonce/longere-120m2-belleme-61130/immo-ray-com-a678b1226c04")


def test_l_identifiant_survit_a_ses_propres_tirets():
    """Le piège de la première version : l'identifiant était collé au bout de
    l'adresse et relu après le DERNIER tiret. Or « immo-ray-com-a678b12 » en
    contient — on relisait « a678b12 », qui n'existe pas, et TOUTES les fiches
    répondaient 410. D'où deux segments."""
    adresse = seo.url_annonce(BIEN)
    assert adresse.rsplit("/", 1)[1] == BIEN["id"]


def test_deux_biens_de_la_meme_commune_ont_deux_adresses():
    autre = dict(BIEN, id="autre-id-999", surface_m2=90.0)
    assert seo.url_annonce(autre) != seo.url_annonce(BIEN)


def test_les_accents_ne_survivent_pas_a_l_adresse():
    assert seo.slug("Saint-Bérain-sur-Dheune") == "saint-berain-sur-dheune"
    assert seo.slug("L'Île-d'Elle") == "l-ile-d-elle"


# --- Ce qu'on publie, et ce qu'on ne publie pas ----------------------------

def test_la_prose_de_l_agence_n_est_jamais_republiee():
    """Recopier le texte de vente de l'agence serait du contenu dupliqué :
    mauvais pour le référencement, et discutable vis-à-vis de l'agence. La
    page ne porte que des FAITS et NOTRE analyse."""
    html = pages.page_annonce(BIEN, [])
    assert "coup de cœur assuré" not in html
    assert "MAGNIFIQUE" not in html


def test_la_fiche_porte_notre_analyse_et_pas_seulement_les_faits():
    """Sans apport propre, la page n'aurait aucune raison d'exister — ni pour
    un lecteur, ni pour un moteur."""
    html = pages.page_annonce(BIEN, [])
    for attendu in ("46 / 100", "210 m", "Géorisques", "Saint-Laurent",
                    "Chauffage au bois"):
        assert attendu in html, attendu


def test_la_fiche_renvoie_vers_l_annonce_d_origine():
    html = pages.page_annonce(BIEN, [])
    assert BIEN["url"] in html
    assert "Agence du Perche" in html


def test_le_risque_n_est_jamais_montre_sans_sa_mise_en_garde():
    """Afficher « retrait-gonflement des argiles » sans dire que le risque
    vaut pour la COMMUNE ferait fuir sur une information fausse."""
    plat = " ".join(pages.page_annonce(BIEN, []).split())
    # Le risque est désormais énoncé dans une phrase — donc en minuscules,
    # comme il se doit au milieu d'un texte, et non en étiquette isolée.
    assert "retrait-gonflement des argiles" in plat.lower()
    assert "commune entière et non pour cette parcelle" in plat
    assert "obligatoire à la vente" in plat


def test_la_page_ne_se_presente_pas_comme_une_agence():
    html = pages.page_annonce(BIEN, [])
    assert "n'est pas une agence" in html


# --- Balises de tête -------------------------------------------------------

def test_la_fiche_porte_titre_description_et_canonique():
    html = pages.page_annonce(BIEN, [], base="https://exemple.fr")
    assert "<title>" in html
    assert re.search(r'<meta name="description" content="[^"]{80,}"', html), \
        "description absente ou trop courte pour être utile"
    assert ('<link rel="canonical" href="https://exemple.fr/annonce/'
            'longere-120m2-belleme-61130/immo-ray-com-a678b1226c04">') in html


def test_le_titre_suit_l_ordre_dans_lequel_on_cherche():
    """Type, taille, lieu, prix — l'ordre des portails, qui est celui de la
    requête tapée."""
    assert seo.titre_annonce(BIEN) == (
        "Longère 5 pièces 120 m² à Bellême (61130) — 250\u00a0000\u00a0€")


def test_tout_ce_qui_vient_des_donnees_est_echappe():
    """Un titre d'agence contenant un guillemet casserait la page, et une
    balise y injecterait du script."""
    piege = dict(BIEN, commune='Bellême"><script>alert(1)</script>')
    html = pages.page_annonce(piege, [])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# --- Données structurées ---------------------------------------------------

def test_les_donnees_structurees_decrivent_une_offre_immobiliere():
    fiche = seo.jsonld_annonce(BIEN, "https://exemple.fr")
    assert fiche["@type"] == "RealEstateListing"
    assert fiche["offers"]["price"] == 250000
    assert fiche["offers"]["priceCurrency"] == "EUR"
    assert fiche["about"]["floorSize"]["value"] == 120.0
    assert fiche["about"]["address"]["postalCode"] == "61130"
    assert fiche["about"]["geo"]["latitude"] == 48.376


def test_les_donnees_structurees_disent_qui_vend():
    """Nous référençons, nous ne vendons pas. Le dire dans le balisage évite
    de nous faire passer pour le mandataire."""
    fiche = seo.jsonld_annonce(BIEN)
    assert fiche["provider"]["@type"] == "RealEstateAgent"
    assert fiche["provider"]["name"] == "Agence du Perche"


def test_les_donnees_structurees_de_la_page_sont_du_json_valide():
    html = pages.page_annonce(BIEN, [])
    blocs = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(blocs) >= 3, "offre, fil d'Ariane et organisation attendus"
    for bloc in blocs:
        json.loads(bloc)


def test_un_champ_absent_ne_laisse_pas_de_trou_dans_le_balisage():
    """Un `null` dans du JSON-LD invalide la fiche entière aux yeux du
    moteur : mieux vaut une clé absente qu'une clé vide."""
    maigre = {"id": "x-1", "type_bien": "maison", "commune": "Toul"}
    fiche = seo.jsonld_annonce(maigre)
    assert None not in fiche.values()
    assert "offers" not in fiche


# --- Pages de terroir ------------------------------------------------------

STATS = {"communes": 101, "prix_median": 294500, "surface_mediane": 130,
         "altitude_mediane": 58, "part_hors_inondation": 36,
         "communes_frequentes": [("Caen", 23), ("Le Havre", 38)]}


def test_le_paragraphe_de_tete_est_citable_tel_quel():
    """Un assistant ne recopie pas une page : il en extrait un passage
    autonome. Pour être cité, celui-ci doit répondre dès la première phrase,
    tenir seul, et porter des chiffres. Cent trente-quatre à cent
    soixante-sept mots est la fenêtre où cela fonctionne."""
    texte = seo.reponse_terroir("Normandie", 318, 101, 294500, 58, 36)
    mots = len(texte.split())
    assert 134 <= mots <= 175, f"{mots} mots"
    assert texte.startswith("En Normandie"), "la réponse doit ouvrir le passage"
    for chiffre in ("318", "101", "294\u00a0500", "58 m", "36 %"):
        assert chiffre in texte, chiffre


def test_la_page_terroir_pose_ses_titres_en_questions():
    """Une IA cherche des questions et leurs réponses ; un lecteur aussi."""
    html = pages.page_terroir("Normandie", [BIEN], STATS)
    titres = re.findall(r"<h2>(.*?)</h2>", html)
    assert sum(1 for t in titres if t.rstrip().endswith("?")) >= 2, titres


def test_la_page_terroir_mene_aux_fiches_et_aux_autres_terroirs():
    """Le maillage : sans lien sortant, une page reste une impasse."""
    html = pages.page_terroir("Normandie", [BIEN], STATS)
    assert seo.url_annonce(BIEN) in html
    for autre in ("centre-val-de-loire", "grand-est", "hauts-de-france"):
        assert f"/terroir/{autre}" in html


def test_la_page_terroir_annonce_les_limites_de_la_note():
    """Promettre une expertise qu'on ne fournit pas se paierait en confiance,
    et c'est le premier critère que pèse un moteur sur un sujet d'argent."""
    plat = " ".join(pages.page_terroir("Normandie", [BIEN], STATS).split())
    assert "n'est pas une expertise" in plat
    assert "état des risques" in plat


# --- Fichiers réclamés par les robots --------------------------------------

def test_robots_nomme_les_robots_d_ia_un_par_un():
    """Plusieurs n'explorent que si une règle les vise nommément."""
    texte = seo.robots_txt("https://exemple.fr")
    for robot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended",
                  "CCBot", "OAI-SearchBot"):
        assert f"User-agent: {robot}" in texte, robot
    assert "Sitemap: https://exemple.fr/sitemap.xml" in texte


def test_robots_ecarte_l_api_sans_bloquer_les_pages():
    texte = seo.robots_txt()
    assert "Disallow: /api/" in texte
    assert "Disallow: /\n" not in texte, "on ne doit jamais tout interdire"


def test_le_plan_du_site_couvre_accueil_terroirs_et_annonces():
    xml = seo.sitemap([BIEN], {"Normandie"}, "https://exemple.fr", jour="2026-08-09")
    assert xml.startswith("<?xml")
    assert "<loc>https://exemple.fr/</loc>" in xml
    assert "<loc>https://exemple.fr/terroir/normandie</loc>" in xml
    assert f"<loc>https://exemple.fr{seo.url_annonce(BIEN)}</loc>" in xml
    assert "<loc>https://exemple.fr/petits-prix</loc>" in xml
    assert "<loc>https://exemple.fr/sans-travaux</loc>" in xml
    # Le compte exact reste une garde : le plan ne doit porter QUE l'accueil,
    # les pages de sujet et les annonces. Une entrée en trop y passerait
    # inaperçue, et un plan qui gonfle dilue ce qu'il annonce. Passé de quatre
    # à cinq avec « sans travaux » — la garde a bien signalé l'ajout.
    assert xml.count("<url>") == 5


def test_llms_txt_dit_les_limites_autant_que_les_forces():
    """Son intérêt n'est pas d'être « lu par l'IA » comme un sésame : c'est de
    donner, en un seul endroit, la version que NOUS jugeons exacte — méthode,
    sources, limites — plutôt que de laisser un modèle la reconstituer de
    travers. Une fiche promotionnelle serait inutile, et fausse."""
    texte = seo.llms_txt(993, {"Normandie": 318}, "https://exemple.fr")
    assert texte.startswith("# Refuge Immo")
    for attendu in ("Géorisques", "prix DEMANDÉS", "pas une expertise",
                    "n'est pas une agence", "993"):
        assert attendu in texte, attendu
    assert "https://exemple.fr/terroir/normandie" in texte


# --- La commune vue du ciel -------------------------------------------------
#
# La photo d'agence n'est pas à nous, et la mesure du hotlink dira ce qu'il en
# restera. La vue aérienne, elle, nous appartient de plein droit : orthophotos
# IGN sous Licence Ouverte. C'est aussi la seule image qui ILLUSTRE ce que la
# page analyse. Une contrainte d'honnêteté la gouverne : notre géolocalisation
# est communale, pas parcellaire — la légende doit le dire.


def test_la_fiche_montre_la_commune_vue_du_ciel():
    html = pages.page_annonce(BIEN, [])
    assert "data.geopf.fr" in html, "l'orthophoto IGN doit illustrer la fiche"
    assert "orthophoto IGN" in html, "la source doit être créditée (licence)"


def test_la_vue_aerienne_avoue_sa_precision():
    """Elle cadre la COMMUNE : la présenter comme la parcelle serait inventer
    — l'adresse exacte ne figure presque jamais dans l'annonce."""
    plat = " ".join(pages.page_annonce(BIEN, []).split())
    assert "L’emplacement exact du bien n’est pas connu" in plat


def test_sans_coordonnees_pas_de_vue_aerienne():
    """Plutôt rien qu'une carte centrée sur n'importe quoi."""
    sans = {k: v for k, v in BIEN.items() if k not in ("lat", "lon")}
    assert "data.geopf.fr" not in pages.page_annonce(sans, [])
