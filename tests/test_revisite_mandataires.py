"""La revisite existait, elle n'arrivait jamais à son tour.

`ordre_dans_le_departement` promet depuis octobre : « les jamais vues
d'abord, puis ce qu'on a revu il y a le plus longtemps ». L'intention est
juste ; la seconde moitié de la phrase ne s'exécutait pas.

Le sitemap d'IAD compte 112 570 adresses pour 6 487 annonces à notre
catalogue, et chaque passage en découvre d'autres. La file des jamais-vues
ne se vide donc pas : elle s'allonge. Un ordre strict la sert indéfiniment,
et les déjà-vues attendent derrière un mur qui monte.

Mesuré le 15 novembre 2026 : 93 % des annonces IAD et 80 % des Safti
n'avaient jamais été revues depuis leur découverte, certaines datant de
quatre-vingt-seize jours. C'est la même famine que le tri alphabétique du
vérificateur de liens, qui donnait 0 % de couverture à Safti — un ordre
strict là où il fallait une part garantie.

Le quota porte sur les annonces AU CATALOGUE, et pas sur toute page déjà
ouverte : rouvrir une page écartée — vendue, ou d'une commune homonyme —
ne la ramènerait pas, et ce sont justement ces pages-là qui bloquaient la
Côte-d'Or en octobre. Les deux correctifs doivent tenir ensemble.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import mandataires  # noqa: E402


def annonces(n, prefixe="https://www.iadfrance.fr/annonce/a"):
    return [{"url": f"{prefixe}{i}"} for i in range(n)]


def test_une_annonce_du_catalogue_repasse_meme_s_il_reste_des_neuves():
    """LE test. Cinquante places, mille neuves en attente : sans quota, pas
    une seule revisite — c'est l'état mesuré le 15 novembre."""
    catalogue = {a["url"]: "2026-08-01" for a in annonces(200, "https://x.fr/vue")}
    candidats = (annonces(200, "https://x.fr/vue") + annonces(1000))
    lot = mandataires.lot_du_passage(candidats, 50, catalogue)
    revisites = sum(1 for a in lot if a["url"] in catalogue)
    assert revisites == 25, f"{revisites} revisites sur 50 places"


def test_seules_les_annonces_servies_ont_des_places_reservees():
    """La leçon d'octobre doit tenir avec celle-ci.

    48 pages refusées — vendues, ou d'un Beaulieu du Maine-et-Loire pris pour
    celui de Côte-d'Or — monopolisaient le département.
    `dates_de_derniere_visite` les compte depuis comme vues POUR L'ORDRE, et
    c'est juste : sans cela elles repassent en tête. Mais leur RÉSERVER des
    places les ferait revenir occuper le lot sans rien rapporter — une page
    écartée ne reviendra pas au catalogue.

    Ici les écartées ouvrent la liste : sans quota, elles prendraient tout.
    """
    ecartees = annonces(40, "https://x.fr/refusee")     # ouvertes, jamais gardées
    servies = annonces(40, "https://x.fr/vue")
    catalogue = {a["url"]: "2026-08-01" for a in servies}
    lot = mandataires.lot_du_passage(ecartees + servies, 20, catalogue)
    assert sum(1 for a in lot if a["url"] in catalogue) == 10, (
        "la moitié du lot revient aux annonces SERVIES")
    assert sum(1 for a in lot if a["url"].startswith("https://x.fr/refusee")) == 10, (
        "l'autre moitié suit l'ordre reçu, sans privilège")


def test_un_departement_sans_revisite_a_faire_rend_ses_places():
    """Réserver sans servir reviendrait à raccourcir le passage."""
    lot = mandataires.lot_du_passage(annonces(30), 20, au_catalogue={})
    assert len(lot) == 20
    deux = annonces(2, "https://x.fr/vue")
    catalogue = {a["url"]: "2026-08-01" for a in deux}
    lot = mandataires.lot_du_passage(deux + annonces(30), 20, catalogue)
    assert len(lot) == 20, "les 18 places non utilisées doivent revenir aux neuves"
    assert sum(1 for a in lot if a["url"] in catalogue) == 2


def test_un_departement_sans_neuve_donne_tout_a_la_revisite():
    """L'inverse : un département entièrement connu doit se relire, pas
    rendre la main."""
    vues = annonces(30, "https://x.fr/vue")
    catalogue = {a["url"]: "2026-08-01" for a in vues}
    lot = mandataires.lot_du_passage(vues, 20, catalogue)
    assert len(lot) == 20


def test_sans_catalogue_rien_ne_change():
    """L'argument est facultatif : les appels qui l'ignorent — les tests
    d'origine, l'audit — gardent exactement l'ordre d'avant."""
    candidats = annonces(30)
    assert (mandataires.lot_du_passage(candidats, 10)
            == mandataires.lot_du_passage(candidats, 10, {})
            == candidats[:10])


def test_le_quota_des_homonymes_tient_toujours():
    """Deux quotas cohabitent : celui des pages hors cible et celui de la
    revisite. Le premier ne doit pas sauter parce que le second existe."""
    hors_cible = [{"url": f"https://x.fr/ailleurs{i}",
                   "hors_cible_selon_l_adresse": True} for i in range(30)]
    vues = annonces(10, "https://x.fr/vue")
    catalogue = {a["url"]: "2026-08-01" for a in vues}
    lot = mandataires.lot_du_passage(hors_cible + vues + annonces(10), 20, catalogue)
    retenus = sum(1 for a in lot if a.get("hors_cible_selon_l_adresse"))
    assert retenus == mandataires.HORS_CIBLE_PAR_PASSAGE


def test_la_part_reste_une_moitie_au_plus():
    """La découverte ne doit pas s'arrêter : un réseau neuf se remplit encore,
    et lui donner moins de la moitié du lot le ferait stagner."""
    assert 0 < mandataires.PART_DE_REVISITE <= 0.5
