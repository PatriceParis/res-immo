"""L'éditeur doit être identifiable, et ce qui manque doit se voir.

Le site n'affichait ni qui l'exploite, ni où le joindre, ni qui répond d'une
publication. Une agence dont l'annonce est reprise, ou une personne voulant
exercer un droit sur ses données, n'avait aucune porte à laquelle frapper.
« Refuge Immo n'est pas une agence » n'est pas une identité.

Ces tests tiennent deux choses en tension : que l'identité connue soit
publiée, et que ce qui manque encore soit AVOUÉ plutôt que comblé. Une mention
légale approximative est pire qu'une mention légale incomplète — elle a l'air
complète, et personne ne la corrige.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages, seo  # noqa: E402

BASE = "https://exemple.fr"


def test_l_editeur_connu_est_publie():
    html = pages.page_mentions_legales(BASE)
    assert seo.EDITEUR["nom"] in html
    assert "819 273 178" in html, "le SIREN doit être lisible, groupé par trois"
    assert "Directeur de la publication" in html
    assert seo.HEBERGEUR["nom"] in html


def test_le_siren_est_groupe_comme_sur_un_kbis():
    assert seo.siren_lisible("819273178") == "819 273 178"
    assert seo.siren_lisible("") == ""


def test_ce_qui_manque_est_avoue_et_non_invente():
    """LE test. Inventer une adresse dans une mention légale serait pire que
    de ne rien écrire : la page aurait l'air en règle."""
    html = pages.page_mentions_legales(BASE)
    if not seo.EDITEUR["adresse"]:
        assert "à compléter" in html
        assert "manque" in html, "la ligne manquante doit se distinguer à l'œil"


def test_la_page_decrit_le_service_et_pas_seulement_une_clause():
    """La qualification juridique dépend de ce qu'on fait, jamais de ce qu'on
    déclare. La page doit donc énumérer les actes, pas se contenter d'un
    « nous ne sommes pas une agence »."""
    html = pages.page_mentions_legales(BASE)
    for acte in ("Détient un mandat", "Perçoit une commission",
                 "Transmet vos coordonnées à une agence", "carte professionnelle"):
        assert acte in html, acte


def test_une_agence_sait_comment_demander_le_retrait():
    """Sans porte de sortie visible, le premier recours d'une agence est la
    mise en demeure. C'est le point le plus concret de toute la page."""
    # Espaces normalisés : la phrase est coupée par un retour à la ligne, et
    # un test ancré sur le texte brut casse au premier reformatage sans que
    # rien n'ait changé pour le lecteur.
    plat = " ".join(pages.page_mentions_legales(BASE).split())
    assert "retrait" in plat.lower()
    assert "sans discussion et sans délai" in plat
    assert "Aucune justification n'est demandée" in plat


def test_la_note_est_presentee_comme_editoriale_et_non_comme_un_diagnostic():
    # Espaces normalisés : les phrases de la page sont coupées par des
    # retours à la ligne, et un test ancré sur le texte brut casse au premier
    # reformatage sans que rien n'ait changé pour le lecteur.
    plat = " ".join(pages.page_mentions_legales(BASE).split())
    assert "indicateur éditorial" in plat
    assert "ni un diagnostic immobilier" in plat
    assert "obligatoire à la vente" in plat


def test_la_confidentialite_ne_decrit_que_des_traitements_reels():
    """Une politique bavarde décrivant des traitements qui n'existent pas
    serait aussi trompeuse qu'une politique absente."""
    html = pages.page_confidentialite(BASE)
    assert "aucun cookie de mesure d'audience" in html
    assert "il n'y a rien à consentir" in html
    if not seo.COURRIEL_ALERTES:
        assert "les alertes ne sont pas encore ouvertes" in html


def test_la_confidentialite_nomme_les_tiers_qui_voient_l_adresse_ip():
    """Les photos viennent de chez l'agence et les fonds de carte de l'IGN :
    ces tiers voient l'adresse IP du visiteur. Le taire serait mentir par
    omission."""
    html = pages.page_confidentialite(BASE)
    assert "IGN" in html and "hébergées chez l'agence" in html


def test_les_droits_et_la_cnil_sont_indiques():
    html = pages.page_confidentialite(BASE)
    for mention in ("effacement", "opposition", "portabilité", "CNIL"):
        assert mention in html, mention


def test_chaque_page_servie_mene_aux_mentions_legales():
    """Une mention légale que rien ne relie n'existe pas : la loi demande
    qu'elle soit accessible depuis le service, pas qu'elle existe quelque
    part."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    for chemin in ("/petits-prix", "/sans-travaux", "/alertes"):
        page = client.get(chemin).text
        assert seo.URL_MENTIONS in page, chemin
        assert seo.URL_CONFIDENTIALITE in page, chemin


def test_une_promesse_de_retrait_a_toujours_une_destination():
    """Les mentions promettent aux agences un retrait « sans discussion et sans
    délai ». Tant que le courriel n'existe pas, cette promesse ne pointe nulle
    part — et c'est justement celle dont dépend la tranquillité du projet.

    Le canal provisoire n'est pas une élégance : c'est le seul qui fonctionne
    aujourd'hui sans exposer d'adresse personnelle. Il doit exister tant que le
    courriel n'existe pas, et disparaître le jour où il existe."""
    html = pages.page_mentions_legales(BASE)
    if not seo.EDITEUR["courriel"]:
        assert seo.CONTACT_PROVISOIRE in html
        assert "sans destinataire" in html
    else:
        assert seo.CONTACT_PROVISOIRE not in html, (
            "le canal provisoire doit s'effacer dès que le courriel existe")


def test_le_canal_provisoire_previent_qu_il_est_public():
    """On y invite des demandes RGPD : dire qu'elles seront lisibles de tous
    n'est pas un détail."""
    html = pages.page_confidentialite(BASE)
    if not seo.EDITEUR["courriel"]:
        assert "aucune donnée sensible" in html
        assert "la page est publique" in html


def test_l_application_elle_meme_mene_aux_pages_legales():
    """Elles n'étaient reliées que depuis les pages servies par le serveur —
    donc invisibles depuis l'application, qui est pourtant la porte d'entrée
    de tout le monde. Une mention légale que rien ne relie n'existe pas."""
    index = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")
    for page in (seo.URL_METHODE, seo.URL_MENTIONS, seo.URL_CONFIDENTIALITE,
                 seo.URL_ALERTES):
        assert f'href="{page}"' in index, page


def test_le_menu_du_haut_tient_en_deux_entrees():
    """Deux, et deux seulement : la méthode, parce qu'une note sur 100 qui ne
    dit pas comment elle est faite n'est pas crédible ; les informations
    légales, parce qu'une agence qui veut le retrait de ses annonces doit
    trouver l'éditeur sans chercher. En ajouter d'autres diluerait les deux."""
    import re
    index = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")
    menu = re.search(r'<nav class="menu-haut".*?</nav>', index, re.S)
    assert menu, "le menu du haut doit exister"
    liens = re.findall(r'href="([^"]+)"', menu.group(0))
    assert liens == [seo.URL_METHODE, seo.URL_MENTIONS], liens
