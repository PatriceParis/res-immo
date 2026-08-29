"""Une collecte qui n'a rien pu publier doit quand même le dire.

`collecte.yml` porte en commentaire l'exigence qui fonde toute la
surveillance : « TOUJOURS laisser une trace dans le dépôt, même quand la
collecte n'a rien changé […] impossible, depuis le seul journal git, de
distinguer un passage qui n'a pas eu lieu d'un passage qui n'a rien trouvé ».
`tests/test_trace_des_passages.py` étend cette exigence aux trois autres
passages et exempte la collecte, « qui tient déjà sa trace ».

Elle ne la tenait pas. Le fichier était bien écrit, mais il n'était indexé
que dans la branche `if [ "$N" -gt 0 ]` : quand l'export ne rendait aucun
catalogue, le script imprimait deux lignes dans le journal du run et sortait
sans rien committer. Et comme une étape `run` s'exécute sous `bash -e`, un
`exporter_reel.py` sorti en erreur tuait l'étape encore plus tôt, avant même
le calcul de `N`.

Ces deux chemins produisent exactement la signature observée du 27 au 29
août : quatre créneaux programmés sur six sans le moindre commit, donc
impossibles à distinguer d'un run qui n'a jamais démarré.

Le test central n'inspecte pas le texte du script : il l'EXÉCUTE, dans un
dépôt jetable, avec un export qui échoue — le pire cas — et vérifie qu'un
commit atteint quand même le dépôt distant.
"""

import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

TRACE = "data/dernier_passage.json"
CATALOGUE = "data/annonces_reel.json"


def script_de_publication() -> str:
    """Le script shell de l'étape qui committe, tel que bash le recevra.

    On passe par le parseur YAML plutôt que par le fichier brut : c'est lui
    qui retire l'indentation commune du bloc, et c'est ce retrait qui rend
    valides les fins de heredoc du script.
    """
    plan = yaml.safe_load((RACINE / ".github" / "workflows" / "collecte.yml")
                          .read_text(encoding="utf-8"))
    scripts = [etape["run"] for travail in plan["jobs"].values()
               for etape in travail["steps"]
               if "run" in etape and "git push" in etape["run"]]
    assert len(scripts) == 1, "collecte.yml : une seule étape doit pousser"
    return scripts[0]


def _git(*args, cwd, **kw):
    return subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                          text=True, **kw)


def depot_jetable(tmp_path: Path, export_echoue) -> tuple[Path, Path]:
    """Un dépôt de travail relié à un dépôt distant nu, et son `exporter_reel`.

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
    # L'export : soit il plante (bash -e devait alors tuer l'étape), soit il
    # rend un catalogue vide (N=0, branche stérile). Les deux chemins mènent
    # au même silence, on veut les deux couverts.
    if export_echoue is True:
        export = "import sys; sys.exit(1)"
    elif export_echoue is False:
        export = "open('data/annonces_reel.json','w').write('[]')\n"
    else:                       # None : l'export réussit et rend un catalogue
        export = ("open('data/annonces_reel.json','w')"
                  ".write('[{\"id\": \"x\"}, {\"id\": \"y\"}]')\n")
    (travail / "scripts" / "exporter_reel.py").write_text(
        export, encoding="utf-8")
    (travail / CATALOGUE).write_text("[]\n", encoding="utf-8")
    _git("add", "-A", cwd=travail)
    _git("commit", "-m", "socle", cwd=travail)
    _git("remote", "add", "origin", str(distant), cwd=travail)
    _git("push", "-u", "origin", "main", cwd=travail)
    return travail, distant


def jouer(script: str, travail: Path, tmp_path: Path):
    """Exécuter l'étape comme GitHub l'exécute : `bash -e`."""
    temp = tmp_path / "runner_temp"
    temp.mkdir(exist_ok=True)
    (temp / "code_collecteur").write_text("0\n", encoding="utf-8")
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
    un contrôle qui le lit croit voir l'œuvre du script alors qu'il regarde la
    sienne. La première version de ce fichier tombait dans ce piège.
    """
    sortie = _git("diff", "--name-only", f"{depuis}..HEAD", cwd=distant).stdout
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def test_un_export_qui_plante_laisse_quand_meme_une_trace_poussee(tmp_path):
    """LE test. C'est le cas qui a rendu quatre créneaux sur six muets.

    Sous `bash -e`, un export sorti en erreur interrompt l'étape sur place :
    aucun commit, aucune trace, et depuis le journal git le passage ressemble
    trait pour trait à un run qui n'a jamais eu lieu.
    """
    travail, distant = depot_jetable(tmp_path, export_echoue=True)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path)
    assert TRACE in fichiers_pousses(distant, avant), (
        "un export qui plante ne pousse aucune trace : son silence est "
        "indiscernable d'un passage qui n'a jamais démarré")


def test_un_catalogue_vide_laisse_quand_meme_une_trace_poussee(tmp_path):
    """L'autre chemin vers le même silence : l'export réussit mais ne rend
    rien, `N` vaut 0, et la branche stérile ne committait pas."""
    travail, distant = depot_jetable(tmp_path, export_echoue=False)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path)
    assert TRACE in fichiers_pousses(distant, avant), (
        "un passage sans catalogue ne pousse aucune trace")


def test_le_catalogue_n_est_jamais_pousse_quand_l_export_a_echoue(tmp_path):
    """Le garde-fou du correctif. Rendre le passage visible ne doit pas
    devenir un moyen de publier un catalogue tronqué : quand l'export a
    échoué, le fichier présent sur le disque n'est plus digne de foi et ne
    doit surtout pas partir."""
    travail, distant = depot_jetable(tmp_path, export_echoue=True)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path)
    assert CATALOGUE not in fichiers_pousses(distant, avant), (
        "le catalogue est poussé alors que l'export a échoué : on publierait "
        "un fichier dont on sait qu'il n'a pas été reconstruit")


def message_du_dernier_commit(distant: Path) -> str:
    return _git("log", "-1", "--format=%s", cwd=distant).stdout.strip()


def test_le_passage_normal_publie_toujours_son_catalogue(tmp_path):
    """L'autre sens de la mesure. Rendre le silence visible ne doit rien
    changer au cas ordinaire : le catalogue part, la trace l'accompagne, et le
    libellé reste celui que la surveillance cherche — « ^Collecte auto ». Un
    correctif qui ferait passer un vrai passage pour un passage sans
    publication tromperait précisément l'alerte qu'il vient armer.

    Le dépôt jetable ne contient que le catalogue : les quatre journaux de
    diagnostic manquent. C'est voulu, et ce test les couvre donc aussi, car
    « git add » sur un chemin absent sort en 128 sans rien indexer — sous
    `bash -e`, un seul journal manquant suffisait à tuer l'étape entière, et
    ce passage-là ne poussait pas même son catalogue.
    """
    travail, distant = depot_jetable(tmp_path, export_echoue=None)
    avant = tete(distant)
    jouer(script_de_publication(), travail, tmp_path)
    pousses = fichiers_pousses(distant, avant)
    assert CATALOGUE in pousses and TRACE in pousses, (
        f"le passage normal ne publie plus son catalogue : {pousses}")
    assert message_du_dernier_commit(distant).startswith("Collecte auto"), (
        "le passage normal ne s'annonce plus comme une collecte réussie : "
        f"« {message_du_dernier_commit(distant)} »")
