"""La page qui s'adresse aux agences, et la limite du listing d'accueil.

Deux exigences gouvernent cette page, et elles se tiennent :

**Ce qui se vend ne touche pas au classement.** Un site qui promet une
sélection objective sur la résilience et vend de la mise en avant ment sur les
deux à la fois. Les prestations proposées portent donc sur ce que l'agence
fait de NOS données chez elle — jamais sur sa place dans nos listes — et la
page l'écrit noir sur blanc plutôt que de le sous-entendre.

**On ne recueille rien qu'on ne puisse recevoir.** Le formulaire suit la règle
posée pour les alertes : tant qu'aucune boîte n'existe, il n'y a pas de
formulaire, il y a le canal qui fonctionne. Recueillir une coordonnée
professionnelle pour la perdre serait pire que ne pas la recueillir — c'est
la leçon de la mise en relation retirée le 17 août, dont le journal vivait
dans un fichier temporaire effacé à chaque redémarrage.

Quant à l'accueil : le catalogue a dépassé seize mille biens servis, et les
demander tous d'un coup alourdit le premier affichage à mesure que la collecte
progresse. Depuis novembre 2026 la liste se pagine ; le compteur doit
continuer de dire les deux nombres — combien répondent aux filtres, et
lesquels sont montrés.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages, seo  # noqa: E402

APP_JS = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")
INDEX = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")
STYLE = (RACINE / "app" / "static" / "style.css").read_text(encoding="utf-8")


def sans_balises(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# --- L'accueil ------------------------------------------------------------

def test_l_accueil_ne_demande_qu_une_page_de_biens():
    """LE test de la limite. Écrit en clair, pas déduit d'un commentaire.

    Elle valait 250 jusqu'en novembre 2026, et c'était un compromis bancal :
    assez pour alourdir la page (109 189 pixels de haut sur téléphone) et
    trop peu pour tout montrer, les biens suivants n'étant atteignables que
    par les filtres. La pagination lève le compromis — la limite descend donc
    à 24, et la contrainte d'origine (une seule limite, déclarée en clair et
    réellement envoyée) tient toujours.
    """
    limite = re.search(r"BIENS_PAR_PAGE\s*=\s*(\d+)", APP_JS)
    assert limite, "la limite du listing d'accueil n'est pas déclarée en clair"
    assert int(limite.group(1)) <= 50, (
        "une page de plus de cinquante biens retombe dans le défilement sans fin")
    assert '"limit", "500"' not in APP_JS, (
        "l'ancienne demande de 500 biens subsiste")
    assert 'p.set("limit", String(BIENS_PAR_PAGE))' in APP_JS, (
        "la requête n'utilise pas la limite déclarée")
    assert 'p.set("offset", String(etat.page * BIENS_PAR_PAGE))' in APP_JS, (
        "sans décalage, la pagination afficherait toujours la même page")


def test_le_compteur_dit_toujours_combien_sont_montres():
    """Limiter sans le dire ferait annoncer « 3 177 biens trouvés » sous une
    liste de 24 — le travers que ce compteur avait déjà corrigé une fois.

    Il disait « les 250 premiers affichés » ; avec des pages il doit dire
    LESQUELS, car « les 24 premiers » serait faux dès la page 2.
    """
    assert "n > montres" in APP_JS, (
        "le compteur ne distingue plus les biens trouvés de ceux affichés")
    assert "nombre(debut + 1)} à ${nombre(debut + montres)" in APP_JS, (
        "le compteur ne dit pas quels biens de la liste sont affichés")
    assert "premiers affichés" not in APP_JS, (
        "« les N premiers » est faux dès la deuxième page")


# --- Le lien du pied de page ---------------------------------------------

def test_le_pied_de_l_accueil_porte_le_lien_professionnel():
    assert 'href="/professionnels"' in INDEX
    assert "Professionnel de l" in INDEX


def test_le_bloc_professionnel_est_sur_fond_blanc():
    """La demande était explicite, et elle a une raison : ce bloc ne s'adresse
    pas au même visiteur que le reste du pied."""
    regle = STYLE[STYLE.index(".pied .pied-pro {"):]
    regle = regle[:regle.index("}")]
    assert "background: #fff" in regle, (
        "le bloc professionnel n'est pas sur fond blanc")


def test_les_pages_serveur_portent_aussi_le_lien():
    """Une fiche d'annonce est souvent la première page qu'une agence voit du
    site — c'est même par là qu'elle découvre y figurer."""
    html = pages.page_methode()
    assert seo.URL_PROFESSIONNELS in html, (
        "le pied des pages serveur ignore la page professionnels")


# --- La page elle-même ----------------------------------------------------

def test_la_page_dit_que_rien_de_vendu_ne_change_le_classement():
    """L'engagement qui rend la page acceptable. Sans lui, vendre quoi que ce
    soit à une agence rendrait la note suspecte pour tout le monde."""
    texte = sans_balises(pages.page_professionnels(3177)).lower()
    assert "ne modifie une note ni un classement" in texte, (
        "la page ne pose pas l'engagement d'indépendance du classement")
    assert "mise en avant" in texte, (
        "la page ne nomme pas ce qu'elle refuse de vendre")


def test_la_page_annonce_un_catalogue_mesure():
    """Une page qui s'adresse à des professionnels ne peut pas annoncer un
    catalogue qu'elle ne mesure pas."""
    texte = sans_balises(pages.page_professionnels(3177))
    assert "3 177" in texte, "le nombre de biens n'est pas celui qu'on lui passe"
    # Sans chiffre, on ne bluffe pas : on reste vague plutôt que faux.
    assert "3 177" not in sans_balises(pages.page_professionnels(0))


def test_la_correction_et_le_retrait_restent_gratuits():
    """Faire payer le retrait d'une annonce mal lue serait indéfendable."""
    texte = sans_balises(pages.page_professionnels(10)).lower()
    assert "gratuit" in texte and "retirer" in texte


def test_sans_adresse_ouverte_aucun_formulaire_ne_recueille_rien(monkeypatch):
    """LE test de la promesse sans destination. Tant qu'aucune boîte ne
    reçoit, la page renvoie au canal qui fonctionne — elle n'affiche pas un
    formulaire qui jetterait les coordonnées."""
    monkeypatch.setattr(seo, "COURRIEL_PRO", "")
    html = pages.page_professionnels(100)
    assert "<form" not in html, (
        "un formulaire est affiché alors qu'aucune adresse ne le reçoit")
    assert seo.CONTACT_PROVISOIRE in html, (
        "le canal provisoire n'est pas proposé à la place")


def test_avec_une_adresse_le_formulaire_ecrit_au_visiteur(monkeypatch):
    """Le jour où l'adresse existe, le formulaire compose un courriel que le
    visiteur envoie lui-même : rien ne transite par le serveur."""
    monkeypatch.setattr(seo, "COURRIEL_PRO", "pro@exemple.fr")
    html = pages.page_professionnels(100)
    assert "<form" in html and "mailto:pro@exemple.fr" in html
    assert "/api/" not in html, (
        "le formulaire poste vers le serveur : rien n'est prévu pour recevoir")


def test_la_page_ne_promet_aucune_mise_en_relation():
    """La loi Hoguet réserve l'entremise aux titulaires d'une carte
    professionnelle. Cette page vend des prestations de données, pas de la
    mise en relation — et ne doit pas laisser croire le contraire."""
    texte = sans_balises(pages.page_professionnels(100)).lower()
    assert "aucun mandat" in texte and "aucune commission" in texte
    for interdit in ("mise en relation", "acheteurs qualifiés", "prospects"):
        assert interdit not in texte, f"la page promet « {interdit} »"
