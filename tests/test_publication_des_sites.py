"""Un passage interrompu doit laisser une trace — sinon il n'a jamais eu lieu.

Le 17 août au soir, `sites.yml` n'avait produit AUCUN commit depuis sa
création, alors qu'il tourne toutes les nuits à 1 h. `data/sites_cherches.json`
n'existait toujours pas. Deux fautes indépendantes, chacune suffisante :

1. **Le script ne publiait qu'à la toute fin.** Sonder trois cents agences —
   jusqu'à huit domaines chacune, quinze secondes de délai d'attente — dépasse
   les quarante-cinq minutes que le workflow accorde. `timeout` tuait donc le
   processus avant son unique écriture, et le `|| true` masquait la mise à
   mort. Rien n'était écrit, pas même le journal de rotation — de sorte que la
   nuit suivante reprenait les mêmes premières agences. La rotation morte,
   pour la quatrième fois cette semaine, sous une forme nouvelle.

2. **`git add` sur un chemin absent sort en 128 sans rien indexer.** Même si le
   script avait produit le recensement, nommer `sites_cherches.json` dans la
   même commande faisait échouer l'étape entière — et avec elle le commit du
   travail réellement fait.

Ces tests EXÉCUTENT les deux corrections plutôt que de les relire : l'un
simule une mise à mort en cours de lot, l'autre lance le préambule du commit
tel que le workflow l'exécutera, dans un dépôt jetable.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "resoudre_sites", RACINE / "scripts" / "resoudre_sites.py")
RESOLUTION = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RESOLUTION)


def agence(rang: int) -> dict:
    """Une agence du registre au nom distinctif, donc réellement cherchable."""
    return {"nom": f"CABINET BERTHOLLET {rang}", "departement": "71",
            "source": "registre", "commune": "Chalon-Sur-Saone",
            "siret": f"{rang:014d}"}


def test_le_journal_survit_a_une_mise_a_mort_en_cours_de_lot(tmp_path, monkeypatch):
    """LE test. Le passage est tué au 30ᵉ sondage : ce qu'il avait déjà fait
    doit être sur le disque.

    Sans publication en chemin, le journal n'existe pas du tout et la nuit
    suivante recommence à la première agence — le script tourne à vide
    indéfiniment, ce qu'il a fait depuis sa création.
    """
    recensement, journal = tmp_path / "recensees.json", tmp_path / "cherches.json"
    recensement.write_text(json.dumps([agence(r) for r in range(60)]),
                           encoding="utf-8")
    monkeypatch.setattr(RESOLUTION, "RECENSEMENT", recensement)
    monkeypatch.setattr(RESOLUTION, "JOURNAL", journal)
    monkeypatch.setattr(sys, "argv", ["resoudre_sites.py", "--lot", "60"])

    sondages = []

    def sonder(agence_cherchee, delai):
        sondages.append(agence_cherchee)
        if len(sondages) >= 30:
            raise KeyboardInterrupt("le couperet des 45 minutes")
        return None

    monkeypatch.setattr(RESOLUTION, "chercher_le_site", sonder)
    with pytest.raises(KeyboardInterrupt):
        RESOLUTION.main()

    assert journal.exists(), (
        "le passage a sondé trente agences et n'a rien écrit : tué avant sa "
        "seule publication, il n'apprend rien à celui de demain")
    retenues = json.loads(journal.read_text(encoding="utf-8"))
    assert len(retenues) == RESOLUTION.PAR_PUBLICATION, (
        f"la publication doit intervenir tous les "
        f"{RESOLUTION.PAR_PUBLICATION} sondages")


def test_les_agences_deja_sondees_ne_repassent_pas_devant(tmp_path, monkeypatch):
    """Ce que le journal sauvé doit produire : la rotation avance vraiment.

    Le passage suivant repart des agences que le précédent n'a pas atteintes.
    C'est l'unique raison d'écrire ce journal en chemin.
    """
    lot = [agence(r) for r in range(60)]
    deja = {RESOLUTION._cle(a): "2026-08-17" for a in lot[:25]}
    ordre = RESOLUTION.ordre_de_recherche(lot, deja)
    assert RESOLUTION._cle(ordre[0]) not in deja, (
        "une agence déjà sondée hier repasse en tête")


def test_un_site_trouve_est_verse_des_la_publication_intermediaire(tmp_path, monkeypatch):
    """Une trouvaille faite au dixième sondage ne doit pas attendre la fin du
    lot pour être écrite : c'est la moitié utile de la publication en chemin."""
    recensement, journal = tmp_path / "recensees.json", tmp_path / "cherches.json"
    recensement.write_text(json.dumps([agence(r) for r in range(60)]),
                           encoding="utf-8")
    monkeypatch.setattr(RESOLUTION, "RECENSEMENT", recensement)
    monkeypatch.setattr(RESOLUTION, "JOURNAL", journal)
    monkeypatch.setattr(sys, "argv", ["resoudre_sites.py", "--lot", "60"])

    sondages = []

    def sonder(agence_cherchee, delai):
        sondages.append(agence_cherchee)
        if len(sondages) == 10:
            return {"nom": agence_cherchee["nom"], "site": "https://trouve.fr",
                    "siret": agence_cherchee["siret"],
                    "commune": agence_cherchee["commune"],
                    "source": "registre+domaine"}
        if len(sondages) >= 30:
            raise KeyboardInterrupt("le couperet des 45 minutes")
        return None

    monkeypatch.setattr(RESOLUTION, "chercher_le_site", sonder)
    with pytest.raises(KeyboardInterrupt):
        RESOLUTION.main()

    inscrites = json.loads(recensement.read_text(encoding="utf-8"))
    assert any(a.get("site") == "https://trouve.fr" for a in inscrites), (
        "le site confirmé au dixième sondage est perdu avec le processus tué")


def preambule_du_commit() -> str:
    """Ce que l'étape de commit exécute AVANT de décider s'il y a de quoi
    committer. C'est là que le `git add` fautif sortait en 128."""
    plan = yaml.safe_load((RACINE / ".github" / "workflows" / "sites.yml")
                          .read_text(encoding="utf-8"))
    script = next(etape["run"] for travail in plan["jobs"].values()
                  for etape in travail["steps"]
                  if "run" in etape and "git push" in etape["run"])
    return script[:script.index('if [ -n "$(git diff --cached')]


def test_le_commit_indexe_ce_qui_existe_quand_le_journal_manque(tmp_path):
    """Un passage trop court pour publier son journal doit tout de même
    committer le recensement qu'il a complété.

    On exécute le préambule tel quel, dans un dépôt jetable où seul le
    recensement existe : avec l'ancienne commande, `git add` sortait en 128
    et n'indexait RIEN — l'étape mourait, le travail était jeté.
    """
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "agences_recensees.json").write_text("[]\n",
                                                              encoding="utf-8")
    for commande in (["git", "init", "-q", "."],
                     ["git", "config", "user.email", "t@t.fr"],
                     ["git", "config", "user.name", "test"]):
        subprocess.run(commande, cwd=tmp_path, check=True)

    fait = subprocess.run(["bash", "-e", "-c", preambule_du_commit()],
                          cwd=tmp_path, capture_output=True, text=True)
    assert fait.returncode == 0, (
        f"le préambule du commit échoue quand le journal manque : "
        f"{fait.stderr.strip()}")
    indexe = subprocess.run(["git", "diff", "--cached", "--name-only"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert "agences_recensees.json" in indexe.stdout, (
        "rien n'est indexé : l'étape ne committera pas, et le travail du "
        "passage est perdu comme il l'a été toutes les nuits")
