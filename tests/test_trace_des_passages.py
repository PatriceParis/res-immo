"""Un passage qui n'a rien trouvé doit se distinguer d'un passage qui a planté.

Le journal git est le seul signal de surveillance des tâches programmées :
« un commit du robot qui manque à l'appel vaut alerte ». Encore faut-il que
l'absence veuille dire quelque chose.

Trois passages sur quatre ne committaient que s'ils avaient trouvé du neuf.
Rien trouvé et rien tourné laissaient donc la même trace — aucune. Le 17 août,
`mandataires.yml` n'a rien poussé à 15 h ; deux points d'étape plus tard, la
cause restait indécidable, non par manque de journaux mais parce que le
silence était ambigu par construction.

`collecte.yml` avait déjà réglé cela pour lui seul, et son commentaire le dit
en toutes lettres : « impossible, depuis le seul journal git, de distinguer un
passage qui n'a pas eu lieu d'un passage qui n'a rien trouvé. Ce fichier
tranche, et il tient dans une ligne. » Ces tests étendent l'exigence aux trois
autres.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "marquer_passage", RACINE / "scripts" / "marquer_passage.py")
MARQUEUR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MARQUEUR)

# Les passages programmés qui écrivent dans data/ et committent. `collecte`
# tient déjà sa trace par data/dernier_passage.json, écrit dans son propre
# script — il porte donc son marqueur sous un autre nom, et fait exception.
PASSAGES = {"mandataires.yml": "mandataires",
            "verifier-liens.yml": "liens",
            "sites.yml": "sites"}


def etape_de_publication(fichier: str) -> str:
    plan = yaml.safe_load((RACINE / ".github" / "workflows" / fichier)
                          .read_text(encoding="utf-8"))
    return next(etape["run"] for travail in plan["jobs"].values()
                for etape in travail["steps"]
                if "run" in etape and "git push" in etape["run"])


def test_chaque_passage_laisse_une_trace_avant_de_juger_s_il_committe():
    """LE test. Le marquage doit précéder le test « y a-t-il de quoi
    committer ? », sinon il ne change rien : le passage muet reste muet."""
    for fichier, nom in PASSAGES.items():
        script = etape_de_publication(fichier)
        assert f"marquer_passage.py {nom}" in script, (
            f"{fichier} ne laisse aucune trace quand il ne trouve rien : son "
            f"silence est indiscernable d'une panne")
        marquage = script.index(f"marquer_passage.py {nom}")
        for garde in ('if [ -n "$(git status --porcelain data/)" ]',
                      'if [ -n "$(git diff --cached --name-only)" ]'):
            if garde in script:
                assert marquage < script.index(garde), (
                    f"{fichier} : le marquage doit précéder le test de "
                    f"changement, sinon il arrive trop tard pour compter")


def test_la_trace_est_indexee_avec_le_reste():
    """Écrire le fichier ne suffit pas : non indexé, il ne sera pas committé
    et le journal git restera muet."""
    for fichier, nom in PASSAGES.items():
        script = etape_de_publication(fichier)
        indexe = (f"dernier_passage_{nom}.json" in script
                  or "git add data/" in script)   # mandataires indexe tout data/
        assert indexe, (
            f"{fichier} écrit sa trace mais ne l'indexe pas : elle ne sera "
            f"jamais committée")


def test_la_trace_est_refaite_apres_s_etre_replace():
    """Le « reset --hard » de la reprise efface la trace comme le reste : sans
    la refaire, un passage qui a dû se replacer redevient muet."""
    for fichier, nom in PASSAGES.items():
        script = etape_de_publication(fichier)
        reprise = script[script.index("git reset --hard origin/main"):]
        assert f"marquer_passage.py {nom}" in reprise, (
            f"{fichier} : la trace doit être refaite après le reset")


def test_le_marqueur_ecrit_bien_un_fichier_par_passage(tmp_path, monkeypatch):
    """Un fichier par passage, et non une entrée dans un fichier commun : deux
    passages qui se replacent l'un après l'autre s'écraseraient."""
    monkeypatch.setattr(MARQUEUR, "RACINE", tmp_path)
    monkeypatch.setattr(MARQUEUR, "fichiers_touches", lambda: [])
    premier = MARQUEUR.marquer("mandataires", {})
    second = MARQUEUR.marquer("liens", {"retires": 3})
    assert premier != second
    assert json.loads(premier.read_text(encoding="utf-8"))["passage"] == "mandataires"
    contenu = json.loads(second.read_text(encoding="utf-8"))
    assert contenu["retires"] == 3 and contenu["quand"]


def test_un_nom_de_passage_ne_peut_pas_designer_un_autre_fichier(tmp_path, monkeypatch):
    """Le nom vient du workflow, pas d'un inconnu — mais un chemin qui remonte
    l'arborescence ne doit jamais pouvoir s'écrire."""
    monkeypatch.setattr(MARQUEUR, "RACINE", tmp_path)
    vise = MARQUEUR.chemin_du_passage("../../etc/passwd")
    assert vise.parent == tmp_path / "data"


def test_le_marqueur_tourne_vraiment(tmp_path):
    """Exécuté pour de bon : un script de surveillance qui plante ne
    surveillerait rien, et le `|| true` du workflow le masquerait.

    On l'exécute depuis une COPIE : le script écrit sous la racine déduite de
    son propre chemin, et un test ne doit jamais toucher au dépôt.
    """
    (tmp_path / "scripts").mkdir()
    copie = tmp_path / "scripts" / "marquer_passage.py"
    copie.write_text((RACINE / "scripts" / "marquer_passage.py")
                     .read_text(encoding="utf-8"), encoding="utf-8")

    fait = subprocess.run([sys.executable, str(copie), "mandataires",
                           "annonces=2407"],
                          cwd=tmp_path, capture_output=True, text=True,
                          timeout=120)
    assert fait.returncode == 0, fait.stderr
    ecrit = tmp_path / "data" / "dernier_passage_mandataires.json"
    assert ecrit.exists(), "le marqueur n'a rien écrit"
    assert json.loads(ecrit.read_text(encoding="utf-8"))["annonces"] == 2407
