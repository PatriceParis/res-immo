"""Une découverte tuée au plafond doit quand même le dire.

Le 1er septembre, `decouverte.yml` — le passage mensuel qui cherche de
nouvelles agences — a été annulé par son plafond de 120 minutes. L'étape qui
committe a été SAUTÉE : GitHub n'exécute pas les étapes suivantes d'un travail
annulé, sauf celles marquées `if: always()`. Ni commit, ni marqueur — ce
passage n'en posait aucun —, et pendant un mois son silence a ressemblé à
« rien de neuf ce mois-ci ». Il ne s'est jamais exécuté jusqu'au bout depuis
que le périmètre couvre 43 zones.

Ces tests EXÉCUTENT l'étape de publication comme GitHub l'exécute — `bash -e`,
dépôt jetable relié à un distant nu —, avec l'état que GitHub lui aurait
transmis. Ils ne vérifient pas que GitHub honore `always()` : cela, seul le
prochain plafond le dira. Ils vérifient que, l'étape une fois lancée, elle
publie ce qu'elle doit et le dit avec le bon libellé — car un passage annulé
qui se ferait passer pour une découverte tromperait la surveillance qu'il
vient armer.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

TRACE = "data/dernier_passage_decouverte.json"
CONFIG = "scraper/refuge_scraper/agences_sites.json"
RAPPORT = "data/agences_candidates.json"


def script_de_publication() -> str:
    """Le script shell de l'étape qui committe, tel que bash le recevra."""
    plan = yaml.safe_load((RACINE / ".github" / "workflows" / "decouverte.yml")
                          .read_text(encoding="utf-8"))
    scripts = [etape["run"] for travail in plan["jobs"].values()
               for etape in travail["steps"]
               if "run" in etape and "git push" in etape["run"]]
    assert len(scripts) == 1, "decouverte.yml : une seule étape doit pousser"
    return scripts[0]


def _git(*args, cwd, **kw):
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                          text=True, **kw)


def depot_jetable(tmp_path: Path) -> tuple[Path, Path]:
    """Un dépôt de travail relié à un dépôt distant nu.

    Rien ici ne touche au vrai dépôt : un test qui publierait pour de bon
    serait pire que pas de test du tout.
    """
    distant = tmp_path / "distant.git"
    _git("init", "--bare", "-b", "main", str(distant), cwd=tmp_path)

    travail = tmp_path / "travail"
    travail.mkdir()
    _git("init", "-b", "main", cwd=travail)
    _git("config", "user.name", "essai", cwd=travail)
    _git("config", "user.email", "essai@example.invalid", cwd=travail)

    (travail / "data").mkdir()
    (travail / "scripts").mkdir()
    (travail / "scraper" / "refuge_scraper").mkdir(parents=True)
    # Le marqueur réel écrit un horodatage et ce qu'il a touché ; ici sa seule
    # vertu est d'exister et de porter l'état qu'on lui passe.
    (travail / "scripts" / "marquer_passage.py").write_text(
        "import json, pathlib, sys\n"
        "precisions = dict(a.partition('=')[::2] for a in sys.argv[2:])\n"
        "pathlib.Path('data/dernier_passage_decouverte.json').write_text(\n"
        "    json.dumps({'passage': sys.argv[1], 'quand': 'essai',\n"
        "                **precisions}) + '\\n')\n",
        encoding="utf-8")
    (travail / CONFIG).write_text('{"agences": []}\n', encoding="utf-8")
    (travail / RAPPORT).write_text("[]\n", encoding="utf-8")
    _git("add", "-A", cwd=travail)
    _git("commit", "-m", "socle", cwd=travail)
    _git("remote", "add", "origin", str(distant), cwd=travail)
    _git("push", "-u", "origin", "main", cwd=travail)
    return travail, distant


def jouer(script: str, travail: Path, tmp_path: Path, etat: str):
    """Exécuter l'étape comme GitHub l'exécute : `bash -e`, et l'état du
    travail dans ETAT — c'est ce que `env: ETAT: ${{ job.status }}` lui donne."""
    temp = tmp_path / "runner_temp"
    temp.mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", "-e", "-c", script], cwd=travail, capture_output=True,
        text=True, env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                        "HOME": str(tmp_path), "RUNNER_TEMP": str(temp),
                        "GIT_TERMINAL_PROMPT": "0", "ETAT": etat}, timeout=300)


def tete(distant: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=distant).stdout.strip()


def fichiers_pousses(distant: Path, depuis: str) -> list[str]:
    """Ce que le script a réellement ajouté au dépôt distant.

    On compare à la tête d'AVANT plutôt que de lire le dernier commit : quand
    le script ne pousse rien, le dernier commit est celui du socle du test, et
    un contrôle qui le lit croit voir l'œuvre du script.
    """
    sortie = _git("diff", "--name-only", f"{depuis}..HEAD", cwd=distant).stdout
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def message_du_dernier_commit(distant: Path) -> str:
    return _git("log", "-1", "--format=%s", cwd=distant).stdout.strip()


def test_un_passage_annule_au_plafond_laisse_une_trace_poussee(tmp_path):
    """LE test. C'est le cas du 1er septembre : le sondage est tué avant
    d'avoir écrit quoi que ce soit, les fichiers sont intacts, et l'étape
    reçoit « cancelled ». Elle doit pousser la trace, rien d'autre, et le
    dire sans se réclamer d'une découverte."""
    travail, distant = depot_jetable(tmp_path)
    avant = tete(distant)
    fait = jouer(script_de_publication(), travail, tmp_path, etat="cancelled")
    pousses = fichiers_pousses(distant, avant)
    assert TRACE in pousses, (
        "un passage annulé au plafond ne pousse aucune trace : son silence est "
        f"indiscernable d'un mois sans nouveauté — {fait.stderr}")
    assert CONFIG not in pousses, (
        "un passage annulé a publié la configuration de collecte alors que le "
        "sondage ne l'a pas réécrite")
    assert message_du_dernier_commit(distant).startswith(
        "Découverte : passage sans nouveauté (état cancelled"), (
        "le libellé ne dit pas que le passage a été annulé : "
        f"« {message_du_dernier_commit(distant)} »")
    trace = json.loads(_git("show", f"HEAD:{TRACE}", cwd=distant).stdout)
    assert trace["etat"] == "cancelled", trace


def test_un_passage_reussi_sans_nouveaute_le_dit(tmp_path):
    """L'autre silence : tout a tourné, aucune agence nouvelle. Visible, et
    distinct du passage annulé par l'état qu'il porte."""
    travail, distant = depot_jetable(tmp_path)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path, etat="success")
    assert TRACE in fichiers_pousses(distant, avant)
    assert message_du_dernier_commit(distant).startswith(
        "Découverte : passage sans nouveauté (état success"), (
        f"« {message_du_dernier_commit(distant)} »")


def test_une_agence_nouvelle_part_sous_le_libelle_de_decouverte(tmp_path):
    """L'autre sens de la mesure. Rendre le silence visible ne doit rien
    changer au cas ordinaire : quand le sondage a branché une agence, la
    configuration part, la trace l'accompagne, et le libellé reste celui que
    la surveillance cherche."""
    travail, distant = depot_jetable(tmp_path)
    avant = tete(distant)
    # Ce que le script aurait écrit après la dernière zone.
    (travail / CONFIG).write_text(
        json.dumps({"agences": [{"nom": "Agence de l'Essai",
                                 "site": "https://essai.example"}]}) + "\n",
        encoding="utf-8")
    jouer(script_de_publication(), travail, tmp_path, etat="success")
    pousses = fichiers_pousses(distant, avant)
    assert CONFIG in pousses and TRACE in pousses, (
        f"le passage ordinaire ne publie plus sa configuration : {pousses}")
    assert message_du_dernier_commit(distant).startswith(
        "Découverte : agences des zones visées"), (
        "le passage ordinaire ne s'annonce plus comme une découverte : "
        f"« {message_du_dernier_commit(distant)} »")
