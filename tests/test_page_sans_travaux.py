"""La page « sans travaux » doit dire ce qu'elle ignore.

Sa liste n'a rien d'original : tous les portails en proposent une. Ce qui la
distingue est qu'elle avoue son angle mort — la plupart des annonces ne disent
rien de l'état du bien, et une annonce muette n'est pas une bonne nouvelle.
Ces tests tiennent cet aveu, parce que c'est lui qui peut disparaître sans
qu'on s'en aperçoive : une page plus fournie serait plus vendeuse et moins
vraie.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages, seo  # noqa: E402

BIENS = [
    {"id": "a", "titre": "Longère rénovée", "commune": "Bellême", "prix": 149_000,
     "surface_m2": 120, "score_total": 61, "region": "Perche",
     "url": "https://agence.fr/a", "sans_travaux": 1, "etat_declare": "sans_travaux"},
    {"id": "b", "titre": "Maison de bourg", "commune": "Mortagne", "prix": 96_000,
     "surface_m2": 90, "score_total": 44, "region": "Perche",
     "url": "https://agence.fr/b", "sans_travaux": 1, "etat_declare": "sans_travaux"},
]
STATS = {"communes": 2, "prix_median": 122_500, "surface_mediane": 105,
         "bien_notes": 2, "dans_la_tranche": 287, "muettes": 162,
         "avec_travaux": 72}


def page() -> str:
    return pages.page_sans_travaux(BIENS, STATS, "https://exemple.fr")


def test_la_page_annonce_les_deux_bornes_de_la_tranche():
    html = page()
    assert seo._euros(seo.PLANCHER_SANS_TRAVAUX) in html
    assert seo._euros(seo.PLAFOND_SANS_TRAVAUX) in html


def test_la_page_avoue_les_annonces_muettes():
    """LE test. Sans ce nombre, la page laisse croire que les 53 retenus sont
    les seuls biens prêts de la tranche — alors que 162 n'ont rien dit."""
    html = page()
    assert "162" in html, "le nombre d'annonces muettes doit être écrit"
    assert "muette" in html.lower()


def test_la_page_dit_que_le_silence_n_est_pas_une_bonne_nouvelle():
    texte = seo.reponse_sans_travaux(53, 287, 162, 40, 122_500, 30)
    assert "ne sont pas écartées parce qu'elles auraient des travaux" in texte
    assert "n'est pas une bonne nouvelle" in texte


def test_la_page_attribue_la_formule_a_l_agence():
    """« Sans travaux » est la parole de l'agence, pas notre constat. Le
    catalogue ne visite rien et ne doit pas laisser croire l'inverse."""
    html = page()
    assert "parole de l'agence" in html
    assert "diagnostics obligatoires" in html


def test_le_classement_est_par_note_et_non_par_prix():
    """Comme la page des petits prix : le moins cher n'ouvre pas la liste.
    Ici « b » est moins cher mais moins bien noté — il doit rester second.
    On s'ancre sur la commune : le titre AFFICHÉ est rédigé depuis nos données
    (« Bien 120 m² à Bellême »), pas recopié de l'agence."""
    html = page()
    assert html.index("Bellême") < html.index("Mortagne")


def test_le_lien_vers_la_carte_ne_promet_que_ce_que_la_carte_montre():
    """Le filtre de l'accueil n'a pas de plancher : lui passer la borne basse
    donnerait une carte qui ne correspond pas au bouton."""
    html = page()
    assert f"prix_max={seo.PLAFOND_SANS_TRAVAUX}" in html
    assert f"prix_min={seo.PLANCHER_SANS_TRAVAUX}" not in html


def test_la_page_est_dans_le_plan_du_site_et_le_llms_txt():
    """Une page que rien n'annonce n'est jamais lue."""
    plan = seo.sitemap(BIENS, {"Perche"}, "https://exemple.fr")
    assert f"https://exemple.fr{seo.URL_SANS_TRAVAUX}" in plan
    resume = seo.llms_txt(287, {"Perche": 12}, "https://exemple.fr")
    assert seo.URL_SANS_TRAVAUX in resume


def test_le_titre_et_la_description_portent_le_nombre_reel():
    assert "2 biens" in seo.titre_sans_travaux(len(BIENS))
    description = seo.description_sans_travaux(53, 30, 122_500)
    assert "53 maisons" in description and "350 km" in description
