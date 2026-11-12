"""Une annonce que le réseau ne publie plus sort du catalogue.

Signalé le 12 novembre 2026 : une maison IAD de Charny, servie chez nous,
renvoyait vers la liste de toutes les annonces IAD — vendue ou retirée.
La collecte ne l'avait pas revue depuis le 17 octobre (son département est
tronqué à chaque passage), le vérificateur de liens jamais (9 408 liens
servis jamais regardés, ~170 par jour). Pourtant le collecteur lit à chaque
passage le sitemap complet du réseau, la liste de ses annonces en ligne :
il savait, et ne s'en servait pas.

Ces tests fixent la parade et ses garde-fous : deux absences à deux jours
distincts avant le retrait, comme pour un lien mort ; rien n'est noté sur un
sitemap lu en partie ou qui perdrait d'un coup une part invraisemblable du
catalogue ; une annonce revenue au sitemap est innocentée.
"""

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import liens  # noqa: E402
from scripts import collecter_mandataires as collecteur  # noqa: E402

SITE = "https://www.iadfrance.fr"
MOTIF = re.compile(r"/annonce/", re.IGNORECASE)
CHARNY = "https://www.iadfrance.fr/annonce/maison-vente-5-pieces-charny-90m2/r2124994"
AUTRES = [f"https://www.iadfrance.fr/annonce/maison-vente-4-pieces-joigny-80m2/r{n}"
          for n in range(2100000, 2100010)]


def test_l_annonce_disparue_du_sitemap_est_reperee():
    connues = [CHARNY, *AUTRES,
               "https://www.safti.fr/annonces/achat/maison-autun/12",   # autre réseau
               "https://www.iadfrance.fr/conseiller/jean"]               # pas une annonce
    # Le sitemap écrit ses adresses à sa façon : barre finale, http.
    sitemap = [u.replace("https://", "http://") + "/" for u in AUTRES]
    assert liens.absentes_du_sitemap(connues, sitemap, SITE, MOTIF) == [CHARNY]


def test_un_sitemap_qui_perd_un_cinquieme_du_catalogue_est_suspect():
    assert liens.absentes_du_sitemap([CHARNY, *AUTRES], AUTRES[:7], SITE, MOTIF) is None


def test_deux_absences_a_deux_jours_distincts_avant_le_retrait():
    journal = {}
    liens.noter_sitemap(journal, [CHARNY], AUTRES, "2026-11-12")
    liens.noter_sitemap(journal, [CHARNY], AUTRES, "2026-11-12")   # même jour : un seul constat
    assert CHARNY not in liens.morts_confirmes(journal)
    liens.noter_sitemap(journal, [CHARNY], AUTRES, "2026-11-13")
    assert CHARNY in liens.morts_confirmes(journal)
    gardees, retirees = liens.sans_liens_morts([{"url": CHARNY}, {"url": AUTRES[0]}], journal)
    assert retirees == 1 and gardees == [{"url": AUTRES[0]}]


def test_revenue_au_sitemap_elle_est_innocentee_mais_pas_ce_qu_a_vu_le_verificateur():
    redirigee = AUTRES[1]
    journal = {redirigee: {"constats": 1, "dernier": "2026-11-11",
                           "motif": "redirigé vers https://www.iadfrance.fr/liste"}}
    liens.noter_sitemap(journal, [CHARNY], AUTRES, "2026-11-12")
    liens.noter_sitemap(journal, [], [CHARNY, *AUTRES], "2026-11-13")
    assert CHARNY not in journal
    assert redirigee in journal, "la redirection observée reste au journal"


def test_un_fichier_de_sitemap_illisible_rend_la_lecture_incomplete(monkeypatch):
    pages = {
        "index.xml": b"<sitemapindex><sitemap><loc>a.xml</loc></sitemap>"
                     b"<sitemap><loc>b.xml</loc></sitemap></sitemapindex>",
        "a.xml": f"<urlset><url><loc>{AUTRES[0]}</loc></url></urlset>".encode(),
        "b.xml": b"",                                    # illisible ce jour-là
    }
    monkeypatch.setattr(collecteur, "lire", lambda url: pages.get(url, b""))
    adresses, complet = collecteur.adresses_du_sitemap(["index.xml"], MOTIF)
    assert adresses == [AUTRES[0]]
    assert complet is False
    pages["b.xml"] = f"<urlset><url><loc>{CHARNY}</loc></url></urlset>".encode()
    adresses, complet = collecteur.adresses_du_sitemap(["index.xml"], MOTIF)
    assert complet is True and sorted(adresses) == sorted([AUTRES[0], CHARNY])


def test_le_collecteur_ecrit_le_journal(tmp_path, monkeypatch):
    journal = tmp_path / "liens_morts.json"
    monkeypatch.setattr(collecteur, "JOURNAL_MORTS", journal)
    monkeypatch.setattr(collecteur, "DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(collecteur, "annonces_deja_connues",
                        lambda: {u: "2026-10-17" for u in [CHARNY, *AUTRES]})
    reseau = {"site": SITE, "motif_annonce": MOTIF}
    collecteur.noter_absentes_du_sitemap(AUTRES, reseau, "iad")
    contenu = json.loads(journal.read_text(encoding="utf-8"))
    assert list(contenu) == [CHARNY]
    assert contenu[CHARNY]["motif"] == liens.MOTIF_SITEMAP


def test_le_journal_survit_a_une_reprise_de_push():
    """Le workflow se replace sur la version distante quand son push est
    refusé ; le journal des morts doit être reporté comme les autres
    mémoires du passage, sinon les constats du sitemap se perdent."""
    texte = (RACINE / ".github" / "workflows" / "mandataires.yml").read_text(encoding="utf-8")
    assert texte.count("liens_morts.json; do") == 2
