"""Une agence qui coûte son budget sans rien rapporter peut être endormie.

Quatre minutes et demie, c'est le budget d'une agence sur les vingt-huit d'un
passage. Cinq sites le consomment entièrement et n'ont jamais livré une seule
annonce en trois tournées. Comme ils se suivent dans l'alphabet, ils tombent
dans la même tournée : le 11 août le passage y a laissé quatre-vingts pour
cent de sa récolte, celui du 13 s'est fait tuer par le temps.

Ils sont mis en veille plutôt que supprimés : la raison reste écrite à côté
d'eux, et un mot suffit à les réveiller. La désignation explicite (`-s`) passe
outre, sans quoi on ne pourrait plus jamais aller vérifier s'ils vont mieux.
"""

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecteur", RACINE / "scripts" / "collecter_navigateur.py")
collecteur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collecteur)

CONFIG_ESSAI = {"agences": [
    {"nom": "Agence Vive", "site": "https://vive.fr", "index": []},
    {"nom": "Agence Endormie", "site": "https://endormie.fr", "index": [],
     "actif": False, "veille": "budget entier brûlé, 0 annonce"},
    {"nom": "Agence Sans Drapeau", "site": "https://sansdrapeau.fr", "index": []},
]}


def _config(tmp_path, monkeypatch):
    fichier = tmp_path / "agences.json"
    fichier.write_text(json.dumps(CONFIG_ESSAI, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(collecteur, "CONFIG", fichier)


def test_l_agence_en_veille_sort_de_la_rotation(tmp_path, monkeypatch):
    _config(tmp_path, monkeypatch)
    noms = [a["nom"] for a in collecteur._configurees()]
    assert noms == ["Agence Vive", "Agence Sans Drapeau"]


def test_l_absence_de_drapeau_vaut_active(tmp_path, monkeypatch):
    """Deux cent trente agences n'ont pas le drapeau : elles doivent toutes
    continuer de tourner."""
    _config(tmp_path, monkeypatch)
    assert "Agence Sans Drapeau" in [a["nom"] for a in collecteur._configurees()]


def test_on_peut_toujours_aller_voir_une_agence_endormie(tmp_path, monkeypatch):
    """C'est ainsi qu'on la réveillera : en la désignant explicitement."""
    _config(tmp_path, monkeypatch)
    assert len(collecteur._configurees(toutes=True)) == 3
    cibles = collecteur._cibles("https://endormie.fr", "", "")
    assert [c["nom"] for c in cibles] == ["Agence Endormie"], (
        "désignée à la main, elle garde son identité et se visite")


def test_la_vraie_configuration_reste_lisible_et_majoritairement_active():
    """Garde-fou sur le fichier réel : la mise en veille doit rester
    l'exception, jamais un rabotage silencieux du catalogue."""
    conf = json.loads(
        (RACINE / "scraper" / "refuge_scraper" / "agences_sites.json")
        .read_text(encoding="utf-8"))["agences"]
    endormies = [a for a in conf if not a.get("actif", True)]
    assert len(endormies) < len(conf) * 0.1, "plus d'un dixième en veille : à revoir"
    for a in endormies:
        assert a.get("veille"), f"{a['nom']} endormie sans raison écrite"
