"""Une pièce jointe, une pagination ou la racine d'une archive ne sont pas des
annonces, même sous un chemin d'annonce.

Mesuré au déroulé du 4 octobre 2026, premier passage où il compte les adresses
écartées avant ouverture : 86 pages « illisibles » sur 468, et les exemples
disent lesquelles. Bouctot, 30 pages sur 36 : les pièces jointes WordPress de
chaque bien, « /project/maison-f5-dans-le-cotentin/image002/ ». Picart, 21
sur 45 : la racine de l'archive « /property/ » et ses pages. Toutes ouvertes,
toutes vides — le dernier segment du chemin le disait d'avance.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "collecteur_techniques", RACINE / "scripts" / "collecter_navigateur.py")
collecteur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collecteur)

TECHNIQUES = [
    "https://agence-immobiliere-cherbourg.net/project/maison-f5-dans-le-cotentin/image002/",
    "https://agence-immobiliere-cherbourg.net/project/maison-f5-dans-le-cotentin/DSC_0417/",
    "https://www.picartimmobilier.fr/property/",
    "https://www.picartimmobilier.fr/property/page/2/",
    "https://agence.fr/vente/maison-4-pieces-caen/feed/",
    "https://agence.fr/annonces",
]
ANNONCES = [
    "https://www.picartimmobilier.fr/property/maison-de-ville-cherbourg/",
    "https://agence-immobiliere-cherbourg.net/project/maison-f5-dans-le-cotentin/",
    "https://agence.fr/vente/maison-p-1234",                 # un « p » suivi d'un nombre n'est pas une photo
    "https://agence.fr/annonces/ref-4521",
    "https://agence.fr/biens/belle-photo-de-maison-12",      # « photo » dans le slug, pas en segment
    "https://agence.fr/vente/maison-belleme-61130.html",     # adresse plate, un seul segment
]


def test_les_pages_techniques_ne_sont_pas_ouvertes():
    for url in TECHNIQUES:
        assert not collecteur._est_page_de_bien(url), url


def test_les_annonces_passent_toujours():
    for url in ANNONCES:
        assert collecteur._est_page_de_bien(url), url


class _Reponse:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


def test_le_sitemap_de_bouctot_ne_coute_plus_que_ses_biens(monkeypatch):
    base = "https://agence-immobiliere-cherbourg.net"
    biens = [f"{base}/project/maison-{i}/" for i in range(6)]
    jointes = [f"{base}/project/maison-{i}/image00{j}/" for i in range(6) for j in range(5)]
    sitemap = "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in biens + jointes) + "</urlset>"

    class Faux:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return _Reponse(200, sitemap) if url == f"{base}/sitemap.xml" else _Reponse(404, "")

    monkeypatch.setattr(collecteur, "requests", Faux)
    diag = {}
    assert collecteur._sitemap_urls(base, 0.0, None, diag) == biens
    assert diag["sitemap"] == "ok 6" and diag["adresses_ecartees"] == 30
