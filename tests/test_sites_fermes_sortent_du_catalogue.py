"""Un site qui nous ferme sa porte ne garde pas ses biens au catalogue.

La page /robot et LEGAL.md le promettent depuis le 3 octobre 2026 : « un site
qui ferme sa racine au robot n'est plus visité, et ses biens sortent du
catalogue comme des biens disparus ». Le collecteur tenait la première
moitié. Pas la seconde : la règle de sortie ne connaissait que les cibles
ayant rendu des biens ce passage-ci, et un site fermé n'en rend aucun — ses
biens étaient donc conservés « faute de l'avoir visité », indéfiniment.
Mesuré le 11 octobre 2026 : Bias Immobilier, fermé depuis le 28 septembre,
Ifc Conseils et Les Clés de la Suisse Normande servaient encore vingt biens.

Le collecteur consigne désormais les sites fermés, et l'export les compte
parmi les cibles qui font autorité : leurs biens prennent une absence par
passage fermé, et sortent à la deuxième, comme tout bien disparu.
"""

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import historique, robot  # noqa: E402

collecteur = pytest.importorskip(
    "scripts.collecter_navigateur",
    reason="Playwright absent : le module de collecte ne s'importe pas")


def test_le_journal_des_sites_fermes_vit_a_cote_de_celui_des_tronquees(tmp_path, monkeypatch):
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    assert historique.visites_fermees() == set(), "absent : rien de plus que l'ancien comportement"
    historique.noter_visites_fermees({("Agence A", "a.fr"), ("Agence B", "b.fr")})
    assert (tmp_path / "visites_fermees.json").exists(), "un test qui déplace l'un déplace l'autre"
    assert historique.visites_fermees() == {("Agence A", "a.fr"), ("Agence B", "b.fr")}
    historique.noter_visites_fermees(set())
    assert historique.visites_fermees() == set(), "le journal est remplacé, jamais cumulé"


def _bien(ident, agence, site, absences=0):
    return {"id": ident, "agence": agence, "agence_url": site,
            "absences": absences, "titre": f"Maison {ident}"}


def test_un_site_ferme_fait_autorite_et_ses_biens_s_absentent(tmp_path, monkeypatch):
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    historique.noter_visite_tronquee({("Tronquée", "tronquee.fr")})
    historique.noter_visites_fermees({("Fermée", "fermee.fr")})
    collectes = [_bien("o1", "Ouverte", "https://ouverte.fr"),
                 _bien("t1", "Tronquée", "https://tronquee.fr")]
    autorite = historique.cibles_qui_font_autorite(collectes)
    assert autorite == {("Ouverte", "ouverte.fr"), ("Fermée", "fermee.fr")}

    precedentes = [_bien("o2", "Ouverte", "https://ouverte.fr"),
                   _bien("t2", "Tronquée", "https://tronquee.fr"),
                   _bien("f1", "Fermée", "https://fermee.fr"),
                   _bien("f2", "Fermée", "https://fermee.fr", absences=1),
                   _bien("n1", "Non visitée", "https://ailleurs.fr")]
    apres = {b["id"]: b for b in
             historique.fusionner(precedentes, collectes, autorite, "2026-10-11")}
    assert apres["f1"]["absences"] == 1, "première visite fermée : une absence"
    assert "f2" not in apres, "deuxième : le bien sort, comme tout bien disparu"
    assert apres["t2"]["absences"] == 0 and apres["n1"]["absences"] == 0, (
        "tronquée ou non visitée : on ne conclut rien")
    assert apres["o2"]["absences"] == 1, "la cible ouverte fait autorité comme avant"


class _FaussePage:
    def goto(self, *a, **k): pass
    def wait_for_timeout(self, *a, **k): pass
    def content(self): return "<html></html>"
    def eval_on_selector_all(self, *a, **k): return []
    def set_default_timeout(self, ms): pass
    def set_default_navigation_timeout(self, ms): pass

    @property
    def mouse(self):
        return self

    def wheel(self, *a, **k): pass


class _FauxPlaywright:
    def __enter__(self): return self
    def __exit__(self, *a): return False

    @property
    def chromium(self):
        return self

    def launch(self, **k): return self
    def new_context(self, **k): return self
    def new_page(self): return _FaussePage()
    def close(self): pass


class _FausseBase:
    def execute(self, *a, **k): return self
    def fetchone(self): return None
    def fetchall(self): return []
    def commit(self): pass
    def close(self): pass


def test_le_collecteur_consigne_le_site_qui_lui_ferme_sa_racine(tmp_path, monkeypatch):
    """La vraie boucle, sur un faux navigateur et un faux réseau : le site
    fermé est consigné, l'ouvert ne l'est pas, et le déroulé le dit."""
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur, "_noter_visite", lambda *a, **k: None)
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    monkeypatch.setattr(collecteur.time, "sleep", lambda *_: None)
    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [
        {"nom": "Fermée", "site": "https://fermee.fr"},
        {"nom": "Ouverte", "site": "https://ouverte.fr"}])

    def robots_txt(url):
        if url.startswith("https://fermee.fr"):
            return 200, f"User-agent: {robot.NOM}\nDisallow: /\n"
        return 404, None

    monkeypatch.setattr(collecteur, "_chercher_robots", robots_txt)
    monkeypatch.setattr(collecteur, "_urls_a_visiter",
                        lambda page, cible, base, maxi, fin_prevue=0.0, permission=None,
                        diag=None: [f"{base}/bien-1"])
    monkeypatch.setattr(collecteur, "extraire_annonce", lambda html, url, **k: None)
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()

    assert historique.visites_fermees() == {("Fermée", "fermee.fr")}
    deroule = json.loads((tmp_path / "deroule.json").read_text(encoding="utf-8"))
    agences = deroule.get("agences", deroule) if isinstance(deroule, dict) else deroule
    fins = {a["agence"]: a["fin"] for a in agences}
    assert fins["Fermée"] == "robots.txt interdit" and fins["Ouverte"] != "robots.txt interdit"
    assert ("Fermée", "fermee.fr") in historique.cibles_qui_font_autorite([]), (
        "sans un seul bien rendu, le site fermé fait autorité")
    assert ("Ouverte", "ouverte.fr") not in historique.visites_fermees()
