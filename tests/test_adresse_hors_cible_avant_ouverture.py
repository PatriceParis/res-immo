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


def test_la_version_traduite_d_une_annonce_n_est_pas_ouverte():
    """Mesuré le 11 octobre 2026 : quarante-sept pages anglaises au fichier,
    trente-six servies, dont vingt-trois doublons d'une page française déjà
    là et treize sans prix lisible ou au titre anglais ; chez Accord
    Immobilier, dix-neuf pages anglaises refusées en 403, ouvertes pour rien.
    Le chemin le dit dès son premier segment."""
    traduites = [
        "https://www.fabien-lotz-immobilier.com/en/realestate-adverts/offer/epinal/propriete-12",
        "https://www.leforestier-immobilier.com/en/property/cottage-reimagined",
        "https://www.accord-immobilier.net/en/realestate-adverts/offer/remiremont/maison-3",
        "https://www.rouen-sothebysrealty.com/en/sales/house-rouen-76",
        "https://agence.fr/de/immobilien/haus-12",
        "https://agence.fr/en-gb/property/house-12",
    ]
    for url in traduites:
        assert qualite.motif_url_hors_cible(url) == "langue", url
        assert qualite.motif_de_rejet({"titre": "Cottage reimagined near Dieppe", "url": url,
                                       "type_bien": "maison", "surface_m2": 120,
                                       "prix": 250000}) == "langue", url
        assert not collecteur._est_page_de_bien(url), url
    # La page française, ou un chemin qui contient « en » sans en être un.
    for url in ("https://www.fabien-lotz-immobilier.com/realestate-adverts/offer/epinal/propriete-12",
                "https://www.rouen-sothebysrealty.com/fr/ventes/maison-rouen-76",
                "https://agence.fr/vente/maison-en-pierre-belleme-61130",
                "https://agence.fr/vente/en-exclusivite/maison-5-pieces-12",
                "https://agence.fr/annonces/maison/en/12"):
        assert qualite.motif_url_hors_cible(url) is None, url


def test_une_page_de_rubrique_n_est_pas_une_annonce():
    """Mesuré le 12 octobre 2026 : cent deux biens servis venaient d'une
    adresse de rubrique — « /vente/maison », « /vente/maison-ancienne »,
    « /immobilier/vente/maison » — chez vingt-cinq agences du même gabarit.
    La page liste les biens d'un type ; l'extracteur y lit le premier de la
    liste, sous une adresse qui ne change pas : le même bien deux fois sous
    deux rubriques, et un changement de premier bien pris pour une baisse de
    prix. Le dernier segment est un mot de type, sans chiffre et sans titre."""
    rubriques = [
        "https://www.cric.fr/vente/maison",
        "https://www.alain-guyony.com/vente/maison-ancienne",
        "https://www.amrimmo.com/vente/maison-plain-pied/",
        "https://www.thillard-duhamel.com/immobilier/vente/maison",
        "https://www.alain-guyony.com/vente/manoir",
        "https://www.agence.fr/vente/76-le-havre/maison",
        "https://www.novadimm.com/vente/fonds-de-commerce",
    ]
    for url in rubriques:
        assert qualite.motif_url_hors_cible(url) in ("rubrique", "url_type_exclu"), url
        assert qualite.motif_de_rejet({"titre": "Maison de famille avec jardin", "url": url,
                                       "type_bien": "maison", "surface_m2": 120,
                                       "prix": 290000}) in ("rubrique", "url_type_exclu"), url
        assert not collecteur._est_page_de_bien(url), url
    assert qualite.motif_url_hors_cible("https://www.cric.fr/vente/maison") == "rubrique"
    # Une vraie annonce : un libellé, un identifiant, ou un slug sous /annonce/ ou /bien/.
    for url in ("https://a-tri-home.fr/bien/ifs-sortie-caen/",
                "https://aureliebonnet.fr/annonce/vue-degagee-balcon/",
                "https://www.lhimmo.com/annonce/maison-de-ville-renovee/",
                "https://www.agence.fr/vente/maison-5-pieces-belleme-61130",
                "https://www.agence.fr/vente/2-auxerre/maison/3555-centre-ville-local-professionnel-ou-habitation",
                "https://www.agence.fr/vente/maison-de-ville-renovee-caen",
                "https://www.agence.fr/vente/maison/12-belle-maison-de-bourg/",
                "https://www.immobiliersaintjoseph.com/vente/maison/865-tourville-sur-sienne"):
        assert qualite.motif_url_hors_cible(url) is None, url


def test_le_type_en_tete_du_libelle_condamne_l_adresse():
    """Mesuré le 13 octobre 2026 : cent vingt et un biens servis dont le libellé
    d'adresse commence par un type hors cible — « appartement-t2-2-pieces-
    deauville-14800,VA4416 » sous le titre « DEAUVILLE - 2 CHAMBRES »,
    « immeuble-de-rapport », « 6537-appartement », « vente-appartement-lille-… ».
    Le gabarit forge le libellé à partir du type ; le titre ne le dit pas."""
    for url in ("https://agence.fr/vente/appartement-t2-2-pieces-deauville-14800,VA4416",
                "https://agence.fr/annonce/immeuble-de-rapport",
                "https://agence.fr/annonces/6537-appartement",
                "https://agence.fr/biens/vente-appartement-lille-59000-lille-647-it",
                "https://agence.fr/annonce/terrain-a-batir-vincelles-89290/",
                "https://agence.fr/annonce/bureau-71m%c2%b2-tours",
                "https://agence.fr/annonce/a-vendre-locaux-commerciaux-lille/"):
        assert qualite.motif_url_hors_cible(url) == "url_type_exclu", url
        assert not collecteur._est_page_de_bien(url), url
    # Le type ailleurs qu'en tête, ou une maison : rien à redire.
    for url in ("https://agence.fr/vente/maison-5-pieces-belleme-61130",
                "https://agence.fr/annonce/vente-maison-caen-14000-12",
                "https://agence.fr/annonce/2658-ensemble-immobilier-amfreville-maison-principale",
                "https://agence.fr/annonce/maison-avec-appartement-independant-12",
                "https://agence.fr/annonce/longere-avec-garage-et-terrain-3",
                "https://www.century21-exemple.com/trouver_logement/detail/15516812038/"):
        assert qualite.motif_url_hors_cible(url) is None, url
