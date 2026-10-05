"""On commence par ce qui bouge : les adresses du sitemap, les plus récentes
d'abord.

Mesuré au déroulé du 5 octobre 2026 : 161 pages ouvertes sur 435 étaient des
biens déjà vendus — Dorimmo 39 sur 40, Du Côté de Chez Vous 39 sur 40,
Ernoult 32 sur 39 — et trois seulement le disaient dans leur adresse : une
règle d'adresse n'en vaut pas la peine, la mesure l'a dit. Ces agences
laissent leurs ventes passées dans le sitemap, et le budget de quarante-cinq
pages s'y épuise avant d'atteindre un bien à vendre.

Une annonce vendue n'est plus modifiée ; une annonce en vente l'est encore.
Le sitemap le dit dans <lastmod>. On n'exclut rien : on ordonne, les plus
récentes d'abord, l'ordre du sitemap départageant les égalités, les adresses
sans date en dernier. Un site qui ne date rien n'est pas réordonné.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "collecteur_lastmod", RACINE / "scripts" / "collecter_navigateur.py")
collecteur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collecteur)

BASE = "https://agence-exemple.fr"


def _sitemap(entrees):
    return "<urlset>" + "".join(
        f"<url><loc>{u}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>"
        for u, d in entrees) + "</urlset>"


class _Reponse:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


def _requests(reponses):
    class Faux:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return _Reponse(200, reponses[url]) if url in reponses else _Reponse(404, "")
    return Faux


def test_le_sitemap_se_lit_avec_ses_dates():
    xml = _sitemap([(f"{BASE}/vente/maison-1", "2026-09-30T08:00:00+02:00"),
                    (f"{BASE}/vente/maison-2", "")])
    assert collecteur._entrees_sitemap(xml) == [
        (f"{BASE}/vente/maison-1", "2026-09-30T08:00:00"), (f"{BASE}/vente/maison-2", "")]
    index = f"<sitemapindex><sitemap><loc>{BASE}/sitemap-biens.xml</loc></sitemap></sitemapindex>"
    assert collecteur._entrees_sitemap(index) == [(f"{BASE}/sitemap-biens.xml", "")], \
        "un index sans bloc <url> rend ses <loc>, sans date"


def test_les_plus_recentes_d_abord_les_non_datees_en_dernier(monkeypatch):
    entrees = [(f"{BASE}/vente/maison-vieille", "2025-03-01"),
               (f"{BASE}/vente/maison-sans-date", ""),
               (f"{BASE}/vente/maison-fraiche", "2026-10-04"),
               (f"{BASE}/vente/maison-recente", "2026-09-28"),
               (f"{BASE}/vente/maison-meme-jour", "2026-10-04")]
    monkeypatch.setattr(collecteur, "requests", _requests({f"{BASE}/sitemap.xml": _sitemap(entrees)}))
    diag = {}
    urls = collecteur._sitemap_urls(BASE, 0.0, None, diag)
    assert urls == [f"{BASE}/vente/maison-fraiche", f"{BASE}/vente/maison-meme-jour",
                    f"{BASE}/vente/maison-recente", f"{BASE}/vente/maison-vieille",
                    f"{BASE}/vente/maison-sans-date"], \
        "du plus récent au plus ancien, l'ordre du sitemap départage, sans date en dernier"
    assert diag["sitemap"] == "ok 5" and diag["sitemap_dates"] == 4


def test_un_site_qui_ne_date_rien_garde_son_ordre(monkeypatch):
    entrees = [(f"{BASE}/vente/maison-{i}", "") for i in (3, 1, 2)]
    monkeypatch.setattr(collecteur, "requests", _requests({f"{BASE}/sitemap.xml": _sitemap(entrees)}))
    diag = {}
    assert collecteur._sitemap_urls(BASE, 0.0, None, diag) == [u for u, _ in entrees]
    assert "sitemap_dates" not in diag


def test_les_sous_sitemaps_apportent_leurs_dates_aussi(monkeypatch):
    index = f"<sitemapindex><sitemap><loc>{BASE}/biens.xml</loc></sitemap></sitemapindex>"
    sous = _sitemap([(f"{BASE}/vente/maison-ancienne", "2026-01-10"),
                     (f"{BASE}/vente/maison-du-jour", "2026-10-05")])
    monkeypatch.setattr(collecteur, "requests",
                        _requests({f"{BASE}/sitemap.xml": index, f"{BASE}/biens.xml": sous}))
    diag = {}
    assert collecteur._sitemap_urls(BASE, 0.0, None, diag) == [
        f"{BASE}/vente/maison-du-jour", f"{BASE}/vente/maison-ancienne"]
    assert diag["sitemap_dates"] == 2
