"""Un article de blog n'est pas une annonce, même quand son adresse y ressemble.

Le filtre d'adresses ne retenait que ce qui RESSEMBLE à une annonce — un
segment « vente », « bien », « maison »… — et « /blog/revue-de-presse-1/
vendre-votre-bien-en-48h » lui ressemble. Mesuré au déroulé, premier jour où
il montre un exemple de page illisible : Benedic, 25 pages ouvertes sur 30
étaient des articles de blog ; Apirem la veille, 13 sur 19 ; Aurélie Bonnet,
un conseil sur les mandats rangé sous /vente/. Le budget de quarante-cinq
pages par agence partait en lecture de presse.

Les rubriques éditoriales sont écartées par segment entier du chemin : un
slug d'annonce qui contiendrait « guide » n'est pas visé.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "collecteur_rubriques", RACINE / "scripts" / "collecter_navigateur.py")
collecteur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collecteur)

BASE = "https://agence-exemple.fr"


def test_les_rubriques_editoriales_ne_sont_pas_des_annonces():
    for url in (
        "https://www.benedicsa.com/blog/revue-de-presse-1/vendre-votre-bien-en-48h-des-solutions-innovantes-77",
        f"{BASE}/actualites/vente-maison-nos-conseils/",
        f"{BASE}/conseils/bien-vendre-sa-maison",
        f"{BASE}/news/maison-du-mois",
        # Taxinomies WordPress : Apirem, 13 pages sur 19 le 8 octobre.
        "https://www.apirem.fr/category/vente-a-remere-et-portage-immobilier/",
        f"{BASE}/tag/maison-de-caractere/",
        f"{BASE}/author/agence/vente-maison-2",
    ):
        assert not collecteur._est_page_de_bien(url), url


def test_une_annonce_reste_une_annonce():
    for url in (
        f"{BASE}/vente/maison-4-pieces-belleme-61130/",
        f"{BASE}/biens/maison-guide-michelin-123",      # « guide » dans le slug, pas en rubrique
        f"{BASE}/annonces/news-letter-house-77",         # idem pour « news »
        f"{BASE}/vente/maison-category-a-5",             # et pour « category »
        f"{BASE}/vente/mandat-exclusif-ou-mandat-simple/",  # rangé sous /vente/ : on ne devine pas
    ):
        assert collecteur._est_page_de_bien(url), url


class _Reponse:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


def test_le_sitemap_laisse_les_articles_de_cote(monkeypatch):
    sitemap = (f"<urlset><url><loc>{BASE}/blog/vendre-sa-maison-en-2026</loc></url>"
               f"<url><loc>{BASE}/vente/maison-1</loc></url>"
               f"<url><loc>{BASE}/actualites/maison-du-mois</loc></url></urlset>")

    class Faux:
        @staticmethod
        def get(url, headers=None, timeout=None):
            if url == f"{BASE}/sitemap.xml":
                return _Reponse(200, sitemap)
            return _Reponse(404, "")

    monkeypatch.setattr(collecteur, "requests", Faux)
    diag = {}
    assert collecteur._sitemap_urls(BASE, 0.0, None, diag) == [f"{BASE}/vente/maison-1"]
    assert diag["sitemap"] == "ok 1", "le déroulé compte les annonces, pas les articles"
