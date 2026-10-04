"""Ce que l'adresse condamne, on ne l'ouvre pas.

Le filtre qualité rejette après extraction toute page dont l'adresse dit
« location », « appartement », « terrain », « autres »… Mesuré au déroulé du
4 octobre 2026 : 265 des 490 pages ouvertes étaient hors cible et 101 déjà
vendues — trois pages sur quatre ouvertes pour rien, sur un budget de
quarante-cinq par agence. Le collecteur applique désormais la même règle
AVANT d'ouvrir. Une seule définition, dans app/qualite.py, pour les deux
usages : deux copies d'une règle finissent toujours par diverger.

Même règle, appliquée plus tôt : le catalogue ne peut pas changer, seules les
pages ouvertes diminuent. Le test d'équivalence le garantit.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import qualite  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecteur_adresses", RACINE / "scripts" / "collecter_navigateur.py")
collecteur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collecteur)

BASE = "https://agence-exemple.fr"
ADRESSES = [
    f"{BASE}/vente/maison-5-pieces-belleme-61130",
    f"{BASE}/vente/appartements/t3-centre-ville-12",
    f"{BASE}/location/maison-de-bourg-7",
    f"{BASE}/vente/terrains/parcelle-viabilisee-9",
    f"{BASE}/vente/autres/1",
    f"{BASE}/biens/maison-a-louer-ou-a-vendre-3",
    f"{BASE}/annonces/longere-renovee-21",
]


def test_l_adresse_seule_nomme_le_motif():
    assert qualite.motif_url_hors_cible(f"{BASE}/vente/appartements/t3-12") == "url_type_exclu"
    assert qualite.motif_url_hors_cible(f"{BASE}/location/maison-7") == "location"
    assert qualite.motif_url_hors_cible(f"{BASE}/vente/maison-5-pieces-61130") is None
    assert qualite.motif_url_hors_cible("") is None


def test_meme_regle_avant_et_apres_l_ouverture():
    """Ce que l'adresse écarte avant d'ouvrir est exactement ce que le filtre
    qualité aurait écarté après, pour ce motif : ni plus, ni moins."""
    for url in ADRESSES:
        bien = {"titre": "Maison cinq pièces avec jardin et cave", "url": url,
                "surface_m2": 120.0, "prix": 180000, "pieces": 5}
        apres = qualite.motif_de_rejet(bien)
        avant = qualite.motif_url_hors_cible(url)
        if avant is None:
            assert apres is None, (url, apres)
        else:
            assert apres == avant, (url, avant, apres)


def test_le_collecteur_n_ouvre_pas_ce_que_l_adresse_condamne():
    retenues = [u for u in ADRESSES if collecteur._est_page_de_bien(u)]
    assert retenues == [f"{BASE}/vente/maison-5-pieces-belleme-61130",
                        f"{BASE}/annonces/longere-renovee-21"]


class _Reponse:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


def test_le_deroule_compte_les_adresses_ecartees(monkeypatch):
    sitemap = "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in ADRESSES) + "</urlset>"

    class Faux:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return _Reponse(200, sitemap) if url == f"{BASE}/sitemap.xml" else _Reponse(404, "")

    monkeypatch.setattr(collecteur, "requests", Faux)
    diag = {}
    urls = collecteur._sitemap_urls(BASE, 0.0, None, diag)
    assert len(urls) == 2 and diag["sitemap"] == "ok 2"
    assert diag["adresses_ecartees"] == 5, "cinq adresses condamnées, cinq pages rendues au budget"
