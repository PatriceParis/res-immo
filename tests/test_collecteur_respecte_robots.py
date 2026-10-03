"""Le collecteur de production lit robots.txt et consigne ce qui s'est passé.

Mesuré le 3 octobre : ni le collecteur Playwright — celui que collecte.yml
lance — ni son déroulé ne savaient qu'un robots.txt existait. La page /robot
promettait pourtant qu'il le lisait. Et quand AdressImmo et Mosellane sont
passées de trente pages à zéro, le journal disait seulement « index : 0
lien(s) » : un sitemap refusé en 403 et un sitemap absent finissaient par la
même ligne.

Ces tests exercent les fonctions du script avec un `requests` factice : pas
de réseau, pas de navigateur, et le vrai module chargé par son chemin.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import robot, robots  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecteur_robots", RACINE / "scripts" / "collecter_navigateur.py")
collecteur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collecteur)

BASE = "https://agence-exemple.fr"
SITEMAP = ("<urlset><url><loc>https://agence-exemple.fr/vente/maison-1</loc></url>"
           "<url><loc>https://agence-exemple.fr/vente/maison-2</loc></url>"
           "<url><loc>https://agence-exemple.fr/contact</loc></url></urlset>")


class _Reponse:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


def _requests_factice(reponses: dict, vus: list):
    class Faux:
        @staticmethod
        def get(url, headers=None, timeout=None):
            vus.append((url, (headers or {}).get("User-Agent")))
            if url not in reponses:
                raise ConnectionError(url)
            return _Reponse(*reponses[url])
    return Faux


def test_le_sitemap_se_lit_sous_notre_nom_et_le_diag_dit_ok(monkeypatch):
    vus = []
    monkeypatch.setattr(collecteur, "requests",
                        _requests_factice({f"{BASE}/sitemap.xml": (200, SITEMAP)}, vus))
    diag = {}
    urls = collecteur._sitemap_urls(BASE, 0.0, None, diag)
    assert urls == [f"{BASE}/vente/maison-1", f"{BASE}/vente/maison-2"]
    assert diag["sitemap"] == "ok 2" and diag["sitemap_statut"] == 200
    assert all(ua == robot.USER_AGENT for _, ua in vus), "le robot dit son nom, ici aussi"


def test_un_sitemap_refuse_est_dit_refuse_et_non_absent(monkeypatch):
    """Le cas AdressImmo/Mosellane : zéro page, et avant ce test aucune ligne
    ne distinguait un 403 d'un fichier qui n'existe pas."""
    monkeypatch.setattr(collecteur, "requests", _requests_factice(
        {f"{BASE}/sitemap.xml": (403, ""), f"{BASE}/sitemap_index.xml": (403, ""),
         f"{BASE}/sitemap-index.xml": (403, "")}, []))
    diag = {}
    assert collecteur._sitemap_urls(BASE, 0.0, None, diag) == []
    assert diag["sitemap"] == "HTTP 403" and diag["sitemap_statut"] == 403
    diag = {}
    monkeypatch.setattr(collecteur, "requests", _requests_factice({}, []))
    assert collecteur._sitemap_urls(BASE, 0.0, None, diag) == []
    assert diag["sitemap"].startswith("injoignable")


def test_robots_txt_ferme_le_sitemap_et_les_pages_qu_il_nomme(monkeypatch):
    vus = []
    monkeypatch.setattr(collecteur, "requests", _requests_factice(
        {f"{BASE}/sitemap.xml": (200, SITEMAP), f"{BASE}/autre-sitemap.xml": (200, SITEMAP)}, vus))
    permission = robots.interpreter(
        f"User-agent: {robot.NOM}\nDisallow: /sitemap.xml\nDisallow: /vente/maison-2\n"
        f"Sitemap: {BASE}/autre-sitemap.xml\n", 200, BASE)
    diag = {}
    urls = collecteur._sitemap_urls(BASE, 0.0, permission, diag)
    assert f"{BASE}/sitemap.xml" not in [u for u, _ in vus], "un sitemap interdit n'est pas ouvert"
    assert vus[0][0] == f"{BASE}/autre-sitemap.xml", "celui que robots.txt déclare passe en premier"
    assert urls == [f"{BASE}/vente/maison-1"], "une page interdite ne sort pas du sitemap"


def test_les_liens_d_index_passent_aussi_au_filtre():
    permission = robots.interpreter("User-agent: *\nDisallow: /vente/\n", 200, BASE)
    assert collecteur._autorisees([f"{BASE}/vente/x", f"{BASE}/biens/y"], permission) == [f"{BASE}/biens/y"]
    assert collecteur._autorisees([f"{BASE}/vente/x"], None) == [f"{BASE}/vente/x"], "sans règles, tout passe"


def test_notre_panne_reseau_ne_vaut_pas_interdiction(monkeypatch):
    monkeypatch.setattr(collecteur, "requests", _requests_factice({}, []))
    assert collecteur._chercher_robots(f"{BASE}/robots.txt") == (0, None)
    permission = robots.lire(BASE, collecteur._chercher_robots)
    assert not permission.tout_interdit(BASE)


def test_un_site_qui_nous_ferme_sa_racine_est_lu_comme_tel(monkeypatch):
    monkeypatch.setattr(collecteur, "requests", _requests_factice(
        {f"{BASE}/robots.txt": (200, f"User-agent: {robot.NOM}\nDisallow: /\n")}, []))
    permission = robots.lire(BASE, collecteur._chercher_robots)
    assert permission.tout_interdit(BASE)
