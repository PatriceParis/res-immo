"""Le collecteur lit robots.txt et le respecte — pour de bon, pas sur une page.

La page /robot promettait depuis le 1er octobre : « il lit d'abord votre
fichier robots.txt et le respecte », avec les deux lignes qui l'arrêtent. Le
collecteur de production ne lisait rien du tout ; seul le spider Scrapy, qui
ne tourne pas, honorait ROBOTSTXT_OBEY. Ces tests tiennent la promesse au mot
près : les deux lignes de la page doivent suffire à nous arrêter.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import robot, robots  # noqa: E402

BASE = "https://agence-exemple.fr"


def test_les_deux_lignes_de_la_page_robot_nous_arretent():
    """Mot pour mot ce que /robot donne à copier."""
    texte = f"User-agent: {robot.NOM}\nDisallow: /\n"
    p = robots.interpreter(texte, 200, BASE)
    assert p.tout_interdit(BASE)
    assert not p.autorise(f"{BASE}/sitemap.xml")
    assert not p.autorise(f"{BASE}/vente/maison-12")


def test_un_site_qui_interdit_tous_les_robots_nous_interdit_aussi():
    p = robots.interpreter("User-agent: *\nDisallow: /\n", 200, BASE)
    assert p.tout_interdit(BASE)


def test_notre_groupe_l_emporte_sur_l_etoile():
    """La convention : un groupe à notre nom prime sur « * », dans les deux
    sens — pour nous ouvrir ce qui est fermé aux autres, ou l'inverse."""
    ouvert = robots.interpreter(
        f"User-agent: *\nDisallow: /\n\nUser-agent: {robot.NOM}\nAllow: /\n", 200, BASE)
    assert not ouvert.tout_interdit(BASE) and ouvert.autorise(f"{BASE}/vente/x")
    ferme = robots.interpreter(
        f"User-agent: *\nAllow: /\n\nUser-agent: {robot.NOM}\nDisallow: /\n", 200, BASE)
    assert ferme.tout_interdit(BASE)


def test_une_interdiction_partielle_ne_ferme_que_ce_qu_elle_nomme():
    p = robots.interpreter("User-agent: *\nDisallow: /recherche\nDisallow: /admin/\n", 200, BASE)
    assert not p.tout_interdit(BASE)
    assert not p.autorise(f"{BASE}/recherche?q=maison")
    assert p.autorise(f"{BASE}/vente/maison-12")
    assert p.autorise(f"{BASE}/sitemap.xml")


def test_absent_tout_est_permis_refuse_rien_ne_l_est():
    assert not robots.interpreter(None, 404, BASE).tout_interdit(BASE)
    assert not robots.interpreter("", 200, BASE).tout_interdit(BASE), "fichier vide : rien d'interdit"
    assert robots.interpreter(None, 403, BASE).tout_interdit(BASE), (
        "un site qui refuse de nous montrer ses règles ne nous laisse rien lire")
    assert robots.interpreter(None, 401, BASE).tout_interdit(BASE)
    assert not robots.interpreter(None, 503, BASE).tout_interdit(BASE), (
        "une panne du site n'est pas une interdiction")


def test_notre_panne_n_est_pas_leur_interdiction():
    p = robots.lire(BASE, lambda url: (0, None))
    assert not p.tout_interdit(BASE)
    assert p.statut == 0


def test_lire_vise_la_racine_de_l_hote_et_rapporte_les_sitemaps():
    vus = []

    def chercher(url):
        vus.append(url)
        return 200, "User-agent: *\nAllow: /\nSitemap: /sitemap-biens.xml\nCrawl-delay: 3\n"

    p = robots.lire(f"{BASE}/agence/accueil", chercher)
    assert vus == [f"{BASE}/robots.txt"], "robots.txt vit à la racine de l'hôte"
    assert p.sitemaps == [f"{BASE}/sitemap-biens.xml"]
    assert p.delai() == 3.0
