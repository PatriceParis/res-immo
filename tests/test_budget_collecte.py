"""Une agence lente ne doit pas prendre le tour des autres.

Un passage de trente-quatre minutes n'a visité que TROIS agences pour dix-huit
biens : le budget global disait quand s'arrêter, jamais comment répartir. Le
budget par agence a été écrit pour cela — mais écrit sans pouvoir être
exécuté, le poste de développement n'ayant pas le réseau. Deux passages
programmés n'ont rien poussé ensuite, et rien ne permettait de dire si la
cause était là ou ailleurs.

Ces tests font tourner la vraie boucle de collecte sur un faux navigateur :
pas de réseau, pas de Chromium, mais le code qui décide, lui, est bien le
sien. C'est ce qui manquait pour ne plus corriger à l'aveugle.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

collecteur = pytest.importorskip(
    "scripts.collecter_navigateur",
    reason="Playwright absent : le module de collecte ne s'importe pas")


class _FausseHorloge:
    """Le temps n'avance que quand on le lui demande — les tests sont donc
    instantanés, et la lenteur d'une agence se décrète au lieu de s'attendre."""

    def __init__(self):
        self.maintenant = 1000.0

    def __call__(self):
        return self.maintenant

    def avancer(self, secondes):
        self.maintenant += secondes


class _FaussePage:
    def goto(self, *a, **k): pass
    def wait_for_timeout(self, *a, **k): pass
    def content(self): return "<html></html>"

    @property
    def mouse(self):
        return self

    def wheel(self, *a, **k): pass


class _FauxNavigateur:
    def new_context(self, **k): return self
    def new_page(self): return _FaussePage()
    def close(self): pass


class _FauxPlaywright:
    def __enter__(self): return self
    def __exit__(self, *a): return False

    @property
    def chromium(self):
        return self

    def launch(self, **k): return _FauxNavigateur()


@pytest.fixture()
def collecte(tmp_path, monkeypatch):
    """La vraie boucle de `main()`, sans réseau ni base réelle."""
    (tmp_path / "data").mkdir()
    horloge = _FausseHorloge()
    monkeypatch.setattr(collecteur.time, "monotonic", horloge)
    monkeypatch.setattr(collecteur.time, "sleep", lambda *_: None)
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur, "_noter_visite", lambda *a, **k: None)
    monkeypatch.setattr(collecteur.db, "connexion",
                        lambda: collecteur.db.connexion.__wrapped__()
                        if hasattr(collecteur.db.connexion, "__wrapped__") else _FausseBase())
    return horloge


class _FausseBase:
    def execute(self, *a, **k): return self
    def fetchone(self): return None
    def fetchall(self): return []
    def commit(self): pass
    def close(self): pass


def _lancer(monkeypatch, horloge, agences, secondes_par_page, minutes_par_agence=4.0,
            minutes_max=28.0):
    """Fait tourner la collecte et renvoie les agences réellement visitées."""
    visitees = []

    monkeypatch.setattr(collecteur, "_cibles",
                        lambda *a, **k: [{"nom": n, "site": f"https://{n}.fr"}
                                         for n in agences])

    def urls(page, cible, base, maxi, fin_prevue=0.0):
        visitees.append(cible["nom"])
        return [f"{base}/bien-{i}" for i in range(30)]

    monkeypatch.setattr(collecteur, "_urls_a_visiter", urls)

    def extraire(html, url, **k):
        # Chaque page coûte son temps : c'est le seul point où l'horloge avance.
        horloge.avancer(secondes_par_page[k.get("agence")])
        return None       # aucun bien retenu : on ne mesure que le temps

    monkeypatch.setattr(collecteur, "extraire_annonce", extraire)
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    monkeypatch.setattr(sys, "argv",
                        ["collecter_navigateur.py",
                         "--minutes-par-agence", str(minutes_par_agence),
                         "--minutes-max", str(minutes_max)])
    collecteur.main()
    return visitees


def test_une_agence_lente_ne_confisque_pas_le_budget(collecte, monkeypatch):
    """Le cas mesuré en production : trente pages à vingt secondes chez la
    première agence, et les suivantes n'étaient jamais atteintes."""
    visitees = _lancer(monkeypatch, collecte,
                       agences=["Lente", "Rapide 1", "Rapide 2"],
                       secondes_par_page={"Lente": 60, "Rapide 1": 1, "Rapide 2": 1},
                       minutes_par_agence=4.0, minutes_max=12.0)
    # Sans le budget par agence, « Lente » consommerait trente pages à une
    # minute pièce et serait seule visitée — c'est exactement ce qui s'est
    # produit en production.
    assert visitees == ["Lente", "Rapide 1", "Rapide 2"], \
        "les agences suivantes doivent avoir leur tour"


def test_le_budget_global_reste_la_borne_ultime(collecte, monkeypatch):
    """Le budget par agence ne doit pas permettre de dépasser le budget total :
    c'est lui qui garantit que l'export et le commit auront lieu."""
    visitees = _lancer(monkeypatch, collecte,
                       agences=[f"Agence {n}" for n in range(20)],
                       secondes_par_page={f"Agence {n}": 20 for n in range(20)},
                       minutes_par_agence=4.0, minutes_max=12.0)
    assert len(visitees) <= 4, \
        "douze minutes de budget global, quatre par agence : trois ou quatre tours"
    assert len(visitees) >= 3


def test_la_collecte_va_jusqu_au_bout_sans_lever(collecte, monkeypatch):
    """Le workflow masque l'échec du collecteur derrière `|| true` : une
    exception ici ne se verrait qu'à l'absence de commit, des heures plus
    tard. C'est arrivé — d'où ce test, qui exige simplement que la boucle
    complète se termine."""
    visitees = _lancer(monkeypatch, collecte,
                       agences=["A", "B"],
                       secondes_par_page={"A": 1, "B": 1})
    assert visitees == ["A", "B"]
