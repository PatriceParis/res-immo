"""La note doit pouvoir être jugée sans être livrée.

La note est ce que ce site apporte de propre : publier la formule et ses
coefficients reviendrait à la donner. Mais la loi n'exige pas la formule —
elle exige que ce qui est annoncé au public ne soit pas trompeur. Il faut donc
dire les sources, leur ÉCHELLE, le poids relatif des piliers, et surtout ce que
la note ne dit pas.

Le point décisif est l'échelle : nos risques valent pour la COMMUNE. Laisser
croire qu'ils valent pour la parcelle est exactement ce qui rendrait la note
trompeuse — et c'est aussi ce qui ferait renoncer à un bien parfaitement sain.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages, scoring, seo  # noqa: E402

PLAT = " ".join(pages.page_methode("https://exemple.fr").split())


def test_la_note_est_annoncee_comme_editoriale():
    assert "indicateur éditorial" in PLAT
    assert "ni un diagnostic, ni une expertise, ni une garantie" in PLAT


def test_l_echelle_communale_est_dite_sans_ambiguite():
    """LE test. Une note élevée ne dit rien de la parcelle."""
    assert "valent pour la commune, pas pour la parcelle" in PLAT.lower()
    assert "état des risques, obligatoire à la vente" in PLAT


def test_chaque_donnee_porte_sa_source_et_son_echelle():
    for source in ("Géorisques", "Insee", "Base Adresse Nationale"):
        assert source in PLAT, source
    assert "Échelle" in PLAT


def test_le_poids_des_piliers_est_publie_et_exact():
    """Publier des poids faux serait pire que de n'en publier aucun.

    Les libellés sont comparés ÉCHAPPÉS : « Abri & stockage » s'écrit
    « Abri &amp; stockage » en HTML, et un test qui l'ignore accuse la page
    d'un défaut qu'elle n'a pas."""
    import html as _html
    for cle, maxi in scoring.MAX_PILIERS.items():
        assert _html.escape(scoring.LIBELLES_PILIERS[cle], quote=True) in PLAT
        assert f"{maxi} points" in PLAT
    assert sum(scoring.MAX_PILIERS.values()) == 100


def test_le_bareme_lui_meme_n_est_pas_livre():
    """L'autre sens : la page doit rester le minimum. Si un jour elle publie
    les seuils, elle donne le seul travail propre du site."""
    assert "n'est pas publié" in PLAT
    for detail in ("has_cave", "MAX_PILIERS", "regex", "re.compile"):
        assert detail not in PLAT, detail


def test_les_limites_sont_enumerees_et_pas_seulement_evoquees():
    for limite in ("ne vérifions rien sur place", "Elle ne chiffre aucun travaux",
                   "Elle ignore l'état du bâti", "compare, elle ne certifie pas"):
        assert limite in PLAT, limite


def test_la_formule_employee_pour_l_inondation_est_explicitee():
    """« Commune sans inondation recensée » ressemble à une propriété du
    territoire. La page doit dire que c'est une absence dans une base."""
    assert "aucun événement d'inondation ne figure dans les données" in PLAT


def test_la_page_est_reliee_depuis_les_autres_pages_servies():
    from fastapi.testclient import TestClient
    from app.main import app
    page = TestClient(app).get("/petits-prix").text
    assert seo.URL_METHODE in page
