"""Rotation des agences visitées par la collecte.

La collecte s'arrête sur un budget de temps. En parcourant toujours la liste
des agences dans le même ordre, elle revisitait sans cesse les mêmes
premières et **jamais** les dernières : 51 agences configurées, 4 réellement
revues lors d'une collecte réelle.

Deux conséquences, invisibles depuis le site :

  - les biens des agences de fin de liste étaient figés pour toujours — un
    bien vendu chez elles n'expirait jamais, faute d'être jamais constaté
    absent ;
  - une amélioration de l'extraction ne les atteignait pas.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

collecteur = pytest.importorskip(
    "scripts.collecter_navigateur",
    reason="Playwright absent : le module de collecte ne s'importe pas")


@pytest.fixture()
def depot(tmp_path, monkeypatch):
    """Un faux dépôt : configuration d'agences, export, journal de visites."""
    (tmp_path / "data").mkdir()
    (tmp_path / "scraper" / "refuge_scraper").mkdir(parents=True)
    monkeypatch.setattr(collecteur, "RACINE", tmp_path)
    monkeypatch.setattr(collecteur, "CONFIG",
                        tmp_path / "scraper" / "refuge_scraper" / "agences_sites.json")
    monkeypatch.setattr(collecteur, "JOURNAL_VISITES",
                        tmp_path / "data" / "agences_visitees.json")
    return tmp_path


def _configurer(depot, noms):
    depot.joinpath("scraper/refuge_scraper/agences_sites.json").write_text(
        json.dumps({"agences": [{"nom": n, "site": f"https://{n}.fr"} for n in noms]}),
        encoding="utf-8")


def test_les_agences_jamais_visitees_passent_en_premier(depot):
    _configurer(depot, ["Déjà vue", "Jamais vue"])
    depot.joinpath("data/annonces_reel.json").write_text(json.dumps([
        {"id": "a", "agence": "Déjà vue", "agence_url": "https://Déjà vue.fr",
         "revue_le": "2026-08-04"},
    ]), encoding="utf-8")

    ordre = [c["nom"] for c in collecteur._cibles("", "", "")]
    assert ordre[0] == "Jamais vue"


def test_l_agence_vue_il_y_a_le_plus_longtemps_repasse_la_premiere(depot):
    _configurer(depot, ["Récente", "Ancienne", "Intermédiaire"])
    depot.joinpath("data/annonces_reel.json").write_text(json.dumps([
        {"id": "a", "agence": "Récente", "agence_url": "https://Récente.fr",
         "revue_le": "2026-08-04"},
        {"id": "b", "agence": "Ancienne", "agence_url": "https://Ancienne.fr",
         "revue_le": "2026-06-01"},
        {"id": "c", "agence": "Intermédiaire",
         "agence_url": "https://Intermédiaire.fr", "revue_le": "2026-07-15"},
    ]), encoding="utf-8")

    assert [c["nom"] for c in collecteur._cibles("", "", "")] == [
        "Ancienne", "Intermédiaire", "Récente"]


def test_une_agence_sans_aucun_bien_ne_bloque_pas_la_rotation(depot):
    """Le piège de la première version : se fonder sur `revue_le`, qui n'existe
    que si l'agence a livré des biens. Un site cassé ne recevait jamais de
    date, restait éternellement en tête et prenait le budget des autres à
    chaque collecte."""
    _configurer(depot, ["Site cassé", "Site sain"])
    depot.joinpath("data/annonces_reel.json").write_text(json.dumps([
        {"id": "a", "agence": "Site sain", "agence_url": "https://Site sain.fr",
         "revue_le": "2026-08-01"},
    ]), encoding="utf-8")

    # On vient de passer chez « Site cassé » : il n'a rien rapporté, donc
    # aucun bien ne portera de `revue_le` à son nom. Le passage est consigné.
    collecteur._noter_visite("https://Site cassé.fr", "2026-08-04")

    # La collecte suivante doit aller chez « Site sain », vue il y a plus
    # longtemps — et non retourner buter sur le site cassé.
    assert [c["nom"] for c in collecteur._cibles("", "", "")] == [
        "Site sain", "Site cassé"]


def test_le_journal_de_visites_survit_aux_collectes_successives(depot):
    collecteur._noter_visite("https://a.fr", "2026-08-01")
    collecteur._noter_visite("https://b.fr", "2026-08-02")
    collecteur._noter_visite("https://a.fr", "2026-08-04")   # revue plus tard

    journal = json.loads(
        depot.joinpath("data/agences_visitees.json").read_text(encoding="utf-8"))
    assert journal == {"a.fr": "2026-08-04", "b.fr": "2026-08-02"}


def test_deux_agences_de_la_meme_enseigne_tournent_separement(depot):
    """« Century 21 » désigne cinq agences distinctes dans la configuration.

    La rotation s'indexait sur le NOM : passer chez celle de Compiègne
    marquait aussi celle de Chalon comme visitée, qui filait en fin de file
    et n'était jamais atteinte. C'est le domaine qui identifie une agence.
    """
    depot.joinpath("scraper/refuge_scraper/agences_sites.json").write_text(
        json.dumps({"agences": [
            {"nom": "Century 21", "site": "https://c21-compiegne.fr"},
            {"nom": "Century 21", "site": "https://c21-chalon.fr"},
        ]}), encoding="utf-8")
    depot.joinpath("data/annonces_reel.json").write_text("[]", encoding="utf-8")

    collecteur._noter_visite("https://c21-compiegne.fr", "2026-08-04")

    ordre = [c["site"] for c in collecteur._cibles("", "", "")]
    assert ordre[0] == "https://c21-chalon.fr", (
        "celle de Chalon n'a jamais été visitée : elle doit passer en premier")


def test_un_site_designe_a_la_main_reste_prioritaire(depot):
    """`--site` sert à cibler une agence précise : la rotation ne doit pas
    s'en mêler."""
    _configurer(depot, ["Une autre"])
    cibles = collecteur._cibles("https://choisie.fr", "Choisie", "")
    assert [c["nom"] for c in cibles] == ["Choisie"]
