"""Une vérification des liens qui n'a rien pu publier doit quand même le dire.

Le 23 septembre, `verifier-liens` n'a laissé ni commit ni marquage : rien, de
son créneau de 05 h jusqu'au lendemain. Or ce passage pose sa trace même quand
il ne trouve aucun lien mort — son silence signifie donc qu'il n'a pas atteint
sa publication, pas qu'il n'avait rien à dire.

La cause est celle déjà refermée dans `collecte.yml` le 29 août, restée ici
sous la même forme : une étape `run` s'exécute sous `bash -e`, et l'export
placé en tête n'était pas gardé. Un `exporter_reel.py` sorti en erreur tuait
l'étape sur place — avant le marquage, avant l'indexation, avant tout — et le
passage devenait indiscernable d'un run qui n'a jamais démarré. La même
remarque vaut pour `git add`, qui sort en 128 sans rien indexer quand un
chemin manque.

Ces tests n'inspectent pas le texte du script : ils l'EXÉCUTENT comme GitHub
l'exécute, dans un dépôt jetable relié à un dépôt distant nu.
"""

import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

TRACE = "data/dernier_passage_liens.json"
CATALOGUE = "data/annonces_reel.json"
JOURNAUX = ("data/liens_morts.json", "data/liens_verifies.json")


def script_de_publication() -> str:
    """Le script shell de l'étape qui committe, tel que bash le recevra."""
    plan = yaml.safe_load((RACINE / ".github" / "workflows" / "verifier-liens.yml")
                          .read_text(encoding="utf-8"))
    scripts = [etape["run"] for travail in plan["jobs"].values()
               for etape in travail["steps"]
               if "run" in etape and "git push" in etape["run"]]
    assert len(scripts) == 1, "verifier-liens.yml : une seule étape doit pousser"
    return scripts[0]


def _git(*args, cwd, **kw):
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                          text=True, **kw)


def depot_jetable(tmp_path: Path, export_echoue: bool) -> tuple[Path, Path]:
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
    (travail / "scripts" / "exporter_reel.py").write_text(
        "import sys; sys.exit(1)" if export_echoue
        else "open('data/annonces_reel.json','w').write('[{\"id\": \"x\"}]')\n",
        encoding="utf-8")
    # Le marqueur réel écrit un horodatage ; ici sa seule vertu est d'exister.
    (travail / "scripts" / "marquer_passage.py").write_text(
        "import json, pathlib\n"
        "pathlib.Path('data/dernier_passage_liens.json').write_text(\n"
        "    json.dumps({'passage': 'liens', 'quand': 'essai'}) + '\\n')\n",
        encoding="utf-8")
    for fichier in (CATALOGUE,) + JOURNAUX:
        (travail / fichier).write_text("[]\n", encoding="utf-8")
    _git("add", "-A", cwd=travail)
    _git("commit", "-m", "socle", cwd=travail)
    _git("remote", "add", "origin", str(distant), cwd=travail)
    _git("push", "-u", "origin", "main", cwd=travail)
    return travail, distant


def jouer(script: str, travail: Path, tmp_path: Path):
    """Exécuter l'étape comme GitHub l'exécute : `bash -e`."""
    temp = tmp_path / "runner_temp"
    temp.mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", "-e", "-c", script], cwd=travail, capture_output=True,
        text=True, env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                        "HOME": str(tmp_path), "RUNNER_TEMP": str(temp),
                        "GIT_TERMINAL_PROMPT": "0"}, timeout=300)


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


def test_un_export_qui_plante_laisse_quand_meme_une_trace_poussee(tmp_path):
    """LE test. C'est le cas qui a rendu le 23 septembre muet.

    Sous `bash -e`, un export sorti en erreur interrompait l'étape sur place :
    aucun commit, aucune trace, et depuis le journal git le passage ressemblait
    trait pour trait à un run qui n'a jamais démarré.
    """
    travail, distant = depot_jetable(tmp_path, export_echoue=True)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path)
    assert TRACE in fichiers_pousses(distant, avant), (
        "un export qui plante ne pousse aucune trace : son silence est "
        "indiscernable d'un passage qui n'a jamais démarré")


def test_le_catalogue_n_est_jamais_pousse_quand_l_export_a_echoue(tmp_path):
    """Le garde-fou du correctif. Rendre le passage visible ne doit pas
    devenir un moyen de publier un catalogue que l'export n'a pas reconstruit.
    """
    travail, distant = depot_jetable(tmp_path, export_echoue=True)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path)
    assert CATALOGUE not in fichiers_pousses(distant, avant), (
        "le catalogue est poussé alors que l'export a échoué : on publierait "
        "un fichier dont on sait qu'il n'a pas été reconstruit")


def test_un_passage_rate_ne_se_reclame_pas_d_une_verification(tmp_path):
    """La surveillance cherche « ^Liens vérifiés ». Un passage qui n'a rien
    publié doit rester visible sans se faire passer pour un passage réussi."""
    travail, distant = depot_jetable(tmp_path, export_echoue=True)
    jouer(script_de_publication(), travail, tmp_path)
    assert not message_du_dernier_commit(distant).startswith("Liens vérifiés"), (
        "un passage sans publication s'annonce comme une vérification réussie : "
        f"« {message_du_dernier_commit(distant)} »")


def test_le_passage_normal_publie_toujours_son_catalogue(tmp_path):
    """L'autre sens de la mesure. Rendre le silence visible ne doit rien
    changer au cas ordinaire : le catalogue part, la trace l'accompagne, et le
    libellé reste celui que la surveillance cherche.

    Le dépôt jetable ne contient que les fichiers du dépôt réel ; ce test
    couvre aussi l'indexation, car « git add » sur un chemin absent sort en 128
    sans rien indexer et tuait l'étape entière.
    """
    travail, distant = depot_jetable(tmp_path, export_echoue=False)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path)
    pousses = fichiers_pousses(distant, avant)
    assert CATALOGUE in pousses and TRACE in pousses, (
        f"le passage normal ne publie plus son catalogue : {pousses}")
    assert message_du_dernier_commit(distant).startswith("Liens vérifiés"), (
        "le passage normal ne s'annonce plus comme une vérification réussie : "
        f"« {message_du_dernier_commit(distant)} »")
