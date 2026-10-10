"""L'enrichissement Géorisques rend la main quand l'API ne répond pas.

Mesuré sur les journaux de collecte : le 12 septembre 2026, 17 biens
enrichis pour 14 échecs ; le 19, 50 pour 21 ; le 25, 0 pour 60 ; le 29 et le
3 octobre, 0 pour 59 — et ces 59 échecs ont duré 610 secondes, soit le délai
de dix secondes du client, appel après appel, jusqu'au budget de l'étape. Le
journal disait seulement « API injoignable », sans la raison. Quarante minutes
de runner par jour à attendre une API qui ne répondait plus depuis une
semaine.

Ces tests exécutent le vrai script sur une base SQLite jetable et une API
factice : pas de réseau.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db, georisques  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "enrichir_risques_test", RACINE / "scripts" / "enrichir_risques.py")
enrichir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enrichir)

REPONSE = {"inondation_commune": False, "argile_commune": True, "argile": None,
           "feu_foret_commune": False, "seisme_commune": True, "radon_commune": True,
           "seveso_km": None, "icpe_commune": False, "portee": "commune",
           "source": "georisques"}


@pytest.fixture()
def base(tmp_path, monkeypatch):
    """Douze biens géolocalisés, aucun enrichi."""
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "refuge.db"))
    conn = db.connexion()
    for i in range(12):
        db.upsert_annonce(conn, {
            "id": f"b{i}", "source": "agence", "titre": f"Maison {i}", "prix": 200000,
            "commune": f"Commune {i}", "lat": 48.0 + i / 100, "lon": 1.0, "risques": {}})
    conn.commit()
    conn.close()
    monkeypatch.setattr(sys, "argv", ["enrichir_risques.py", "--max", "200"])
    return tmp_path


def test_dix_echecs_d_affilee_suffisent_a_rendre_la_main(base, monkeypatch, capsys):
    appels = []

    def api_muette(lat, lon, timeout=10):
        appels.append((lat, lon))
        georisques.DERNIERE_ERREUR = "ReadTimeout"
        return None

    monkeypatch.setattr(georisques, "risques_pour", api_muette)
    enrichir.main()
    sortie = capsys.readouterr().out
    assert len(appels) == enrichir.ECHECS_D_AFFILEE_MAX == 10, \
        "on n'attend pas douze fois dix secondes pour apprendre la même chose"
    assert "ReadTimeout" in sortie, "le journal dit POURQUOI, pas seulement « injoignable »"
    assert "⛔" in sortie and "0 annonce(s) enrichie(s), 10 échec(s)" in sortie


def test_un_succes_remet_le_compteur_a_zero(base, monkeypatch, capsys):
    """Des échecs épars sur quelques points — un point en mer, une commune
    inconnue — ne sont pas une panne : on continue."""
    appels = []

    def api_capricieuse(lat, lon, timeout=10):
        appels.append(lat)
        if len(appels) % 3 == 0:          # un échec sur trois, jamais cinq d'affilée
            georisques.DERNIERE_ERREUR = "HTTP 404"
            return None
        return dict(REPONSE)

    monkeypatch.setattr(georisques, "risques_pour", api_capricieuse)
    monkeypatch.setattr(georisques, "exposition_argile", lambda lat, lon, timeout=10: 1)
    monkeypatch.setattr(enrichir.time, "sleep", lambda *_: None)
    enrichir.main()
    sortie = capsys.readouterr().out
    assert len(appels) == 12, "tous les biens ont été tentés"
    assert "8 annonce(s) enrichie(s), 4 échec(s)" in sortie
    assert "⛔" not in sortie


def test_la_raison_de_l_echec_est_nommee(monkeypatch):
    """Le client avalait l'exception ; il la garde désormais, lisible."""
    def lever(*a, **k):
        raise requests.ReadTimeout("lecture trop longue")
    monkeypatch.setattr(georisques.requests, "get", lever)
    assert georisques.risques_pour(48.0, 1.0) is None
    assert georisques.DERNIERE_ERREUR == "ReadTimeout"

    class _Reponse:
        status_code = 503
        def raise_for_status(self):
            raise requests.HTTPError(response=self)
    monkeypatch.setattr(georisques.requests, "get", lambda *a, **k: _Reponse())
    assert georisques.risques_pour(48.0, 1.0) is None
    assert georisques.DERNIERE_ERREUR == "HTTP 503"
    assert georisques.exposition_argile(48.0, 1.0) is None
    assert georisques.DERNIERE_ERREUR == "HTTP 503"
