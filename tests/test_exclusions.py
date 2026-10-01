"""La promesse des mentions légales : retrait sans délai, et la collecte n'y
revient pas.

« Le retrait est effectué sans discussion et sans délai, et le site est ajouté
à une liste d'exclusion pour que la collecte n'y revienne pas. » Jusqu'au
1er octobre, cette liste n'existait pas : la promesse aurait été tenue à la
main, une fois, et la découverte mensuelle aurait rebranché le site au passage
suivant.

Ces tests couvrent les six endroits où une agence peut entrer ou rester : les
trois collecteurs, la découverte, l'export et le chargement.
"""

import importlib.util
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement, decouverte, exclusions, mandataires  # noqa: E402


def liste(tmp_path: Path, *domaines: str) -> Path:
    chemin = tmp_path / "agences_exclues.json"
    chemin.write_text(json.dumps([{"domaine": d, "depuis": "2026-10-01",
                                   "motif": "demande de l'agence"} for d in domaines]),
                      encoding="utf-8")
    return chemin


def bien(identifiant: str, site: str) -> dict:
    """Un bien que le site servirait sans la liste d'exclusion."""
    return {"id": identifiant, "titre": "Maison 5 pièces à Bellême", "type_bien": "maison",
            "agence": f"Agence {identifiant}", "agence_url": site, "url": f"{site}/bien/{identifiant}",
            "prix": 185000, "surface_m2": 120, "terrain_m2": 900, "pieces": 5,
            "commune": "Bellême", "code_postal": "61130", "departement": "61",
            "lat": 48.373, "lon": 0.561, "photo": f"{site}/photo-{identifiant}.jpg"}


def test_le_site_est_reconnu_sous_toutes_ses_formes(tmp_path):
    exclus = exclusions.domaines_exclus(liste(tmp_path, "https://www.Agence-Exemple.fr/"))
    for forme in ("agence-exemple.fr", "www.agence-exemple.fr",
                  "https://agence-exemple.fr/bien/12", "http://www.agence-exemple.fr"):
        assert exclusions.est_exclu(forme, exclus), forme
    assert not exclusions.est_exclu("https://agence-exemple.com", exclus)
    assert not exclusions.est_exclu("https://autre-agence.fr", exclus)
    assert not exclusions.est_exclu("", exclus)


def test_exclure_un_reseau_exclut_ses_agences_mais_pas_l_inverse(tmp_path):
    exclus = exclusions.domaines_exclus(liste(tmp_path, "reseau.fr"))
    assert exclusions.est_exclu("https://agence-x.reseau.fr/", exclus)
    exclus = exclusions.domaines_exclus(liste(tmp_path, "agence-x.reseau.fr"))
    assert not exclusions.est_exclu("https://www.reseau.fr/", exclus), (
        "une agence qui part n'emporte pas son réseau")


def test_sans_liste_rien_n_est_exclu_et_rien_ne_casse(tmp_path):
    assert exclusions.domaines_exclus(tmp_path / "absent.json") == set()
    illisible = tmp_path / "illisible.json"
    illisible.write_text("{pas du json", encoding="utf-8")
    assert exclusions.domaines_exclus(illisible) == set()
    biens = [bien("a", "https://agence.fr")]
    assert exclusions.sans_exclues(biens, set()) == (biens, 0)


def test_les_biens_d_une_agence_exclue_sortent_du_fichier_et_du_site(tmp_path, monkeypatch):
    """L'export et le chargement passent par la même règle : le fichier et
    l'écran ne peuvent pas se contredire."""
    monkeypatch.setattr(exclusions, "FICHIER", liste(tmp_path, "agence-exclue.fr"))
    biens = [bien("garde", "https://agence-gardee.fr"),
             bien("exclu", "https://www.agence-exclue.fr")]
    gardes, retires = exclusions.sans_exclues(biens)
    assert [b["id"] for b in gardes] == ["garde"] and retires == 1
    assert [b["id"] for b in chargement.biens_servis(biens)] == ["garde"]


def test_sans_exclusion_le_bien_temoin_est_bien_servi(tmp_path, monkeypatch):
    """L'autre sens : le test précédent ne prouve rien si le bien témoin
    tombait de toute façon sous un autre filtre."""
    monkeypatch.setattr(exclusions, "FICHIER", tmp_path / "absent.json")
    biens = [bien("garde", "https://agence-gardee.fr"),
             bien("exclu", "https://www.agence-exclue.fr")]
    assert sorted(b["id"] for b in chargement.biens_servis(biens)) == ["exclu", "garde"]


def test_la_decouverte_ne_rebranche_jamais_une_agence_exclue():
    candidates = [{"nom": "Agence Exclue", "site": "https://www.agence-exclue.fr", "note": 90},
                  {"nom": "Agence Neuve", "site": "https://agence-neuve.fr", "note": 90}]
    _, ajoutees = decouverte.fusionner([], candidates, note_mini=25,
                                       exclus={"agence-exclue.fr"})
    assert [a["nom"] for a in ajoutees] == ["Agence Neuve"]
    _, ajoutees = decouverte.fusionner([], candidates, note_mini=25, exclus=set())
    assert [a["nom"] for a in ajoutees] == ["Agence Exclue", "Agence Neuve"]


def test_un_reseau_exclu_sort_du_passage_des_mandataires():
    autorises = mandataires.reseaux_autorises(mandataires.RESEAUX, {"iadfrance.fr"})
    assert "iad" not in autorises and "safti" in autorises
    assert mandataires.reseaux_autorises(mandataires.RESEAUX, set()) == mandataires.RESEAUX


def test_le_collecteur_des_agences_ne_visite_plus_un_site_exclu(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "collecteur_exclusion", RACINE / "scripts" / "collecter_navigateur.py")
    collecteur = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collecteur)
    config = tmp_path / "agences_sites.json"
    config.write_text(json.dumps({"agences": [
        {"nom": "Agence Gardée", "site": "https://agence-gardee.fr"},
        {"nom": "Agence Exclue", "site": "https://www.agence-exclue.fr", "actif": True},
    ]}), encoding="utf-8")
    monkeypatch.setattr(collecteur, "CONFIG", config)
    monkeypatch.setattr(exclusions, "FICHIER", liste(tmp_path, "agence-exclue.fr"))
    assert [a["nom"] for a in collecteur._configurees()] == ["Agence Gardée"]
    assert [a["nom"] for a in collecteur._configurees(toutes=True)] == ["Agence Gardée"], (
        "« toutes » ne doit pas réveiller une agence qui a demandé son retrait")


def test_exclure_ajoute_une_fois_et_retire_du_catalogue_tout_de_suite(tmp_path):
    chemin = tmp_path / "exclues.json"
    assert exclusions.exclure("https://www.Agence-Exclue.fr/contact",
                              "courriel du 1er octobre", chemin, "2026-10-01") is True
    assert exclusions.exclure("agence-exclue.fr", chemin=chemin) is False, "déjà là"
    assert exclusions.lire(chemin) == [{"domaine": "agence-exclue.fr", "depuis": "2026-10-01",
                                        "motif": "courriel du 1er octobre"}]
    catalogue = tmp_path / "annonces.json"
    catalogue.write_text(json.dumps([{"id": "a", "agence_url": "https://agence-exclue.fr"},
                                     {"id": "b", "agence_url": "https://autre.fr"}]),
                         encoding="utf-8")
    assert exclusions.retirer_du_catalogue(catalogue, exclusions.domaines_exclus(chemin)) == 1
    assert [b["id"] for b in json.loads(catalogue.read_text(encoding="utf-8"))] == ["b"]
