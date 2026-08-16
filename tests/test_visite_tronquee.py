"""Une visite tronquée ne prouve rien sur ce qu'on n'a pas atteint.

Troisième forme de la même faute, après Century 21 et IAD : conclure à
l'absence là où l'on n'a pas cherché. Ici la visite a bien eu lieu, mais elle
s'est arrêtée avant la fin de la liste du site — plafond de biens, plafond de
pages, budget de temps, ou réserve d'adresses elle-même coupée. Les annonces
au-delà du point d'arrêt prenaient pourtant une absence à chaque passage et
finissaient supprimées alors qu'elles étaient toujours en ligne : deux cent
quarante et une étaient dans ce cas, et le catalogue perdait une vingtaine de
biens par jour.

Ces tests tiennent les DEUX sens, parce que l'excès inverse est tout aussi
grave : si plus rien n'expirait, les biens vendus s'accumuleraient et le
catalogue mentirait dans l'autre direction.
"""

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import historique  # noqa: E402
from app.historique import fusionner, identite  # noqa: E402

VISITEE = {"id": "v", "agence": "Agence A", "agence_url": "https://a.fr",
           "vue_le": "2026-08-01"}
AUTRE = {"id": "w", "agence": "Agence B", "agence_url": "https://b.fr",
         "vue_le": "2026-08-01"}


def test_une_cible_tronquee_ne_fait_pas_expirer_ses_annonces():
    """LE cas. La visite a eu lieu, mais s'est arrêtée au plafond : l'annonce
    « v » n'a jamais été cherchée."""
    complet = fusionner([VISITEE], [], {identite(VISITEE)}, "2026-08-17")
    assert complet[0]["absences"] == 1, "visite complète : l'absence compte"

    # La même chose, la cible étant retirée de l'ensemble des visitées.
    tronque = fusionner([VISITEE], [], set(), "2026-08-17")
    assert tronque[0].get("absences") in (None, 0), "visite tronquée : on s'abstient"


def test_les_biens_vendus_expirent_toujours_quand_on_a_tout_vu():
    """Le garde-fou de l'excès inverse. Si plus rien ne disparaissait, le
    catalogue se remplirait de biens déjà vendus."""
    un = fusionner([VISITEE], [], {identite(VISITEE)}, "2026-08-17")
    deux = fusionner(un, [], {identite(VISITEE)}, "2026-08-18")
    assert deux == [], "deux absences constatées doivent supprimer l'annonce"


def test_le_journal_ne_decrit_que_le_passage_en_cours(tmp_path, monkeypatch):
    """Il est REÉCRIT à chaque fois. S'il traînait d'un passage à l'autre, on
    s'abstiendrait sur des cibles qu'on vient de parcourir en entier — et les
    biens vendus ne partiraient plus jamais."""
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "j.json")
    historique.noter_visite_tronquee({("Agence A", "a.fr"), ("Agence B", "b.fr")})
    assert historique.visites_tronquees() == {("Agence A", "a.fr"), ("Agence B", "b.fr")}
    historique.noter_visite_tronquee({("Agence C", "c.fr")})
    assert historique.visites_tronquees() == {("Agence C", "c.fr")}, "le journal doit être remplacé"


def test_un_journal_absent_ne_change_rien(tmp_path, monkeypatch):
    """Repli conservateur : sans preuve de troncature, on garde le
    comportement d'avant. Jamais pire, même si le fichier manque."""
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "absent.json")
    assert historique.visites_tronquees() == set()
    (tmp_path / "casse.json").write_text("{ pas du json", encoding="utf-8")
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "casse.json")
    assert historique.visites_tronquees() == set()


def test_l_abstention_ne_deborde_pas_sur_les_autres_cibles():
    """S'abstenir sur une cible tronquée ne doit rien changer aux autres :
    l'agence B, parcourue en entier, garde sa règle de sortie."""
    visites = {identite(AUTRE)}          # A tronquée, donc absente de l'ensemble
    res = fusionner([VISITEE, AUTRE], [], visites, "2026-08-17")
    par_id = {b["id"]: b for b in res}
    assert par_id["v"].get("absences") in (None, 0)
    assert par_id["w"]["absences"] == 1


def test_le_journal_est_relu_tel_qu_il_est_ecrit(tmp_path, monkeypatch):
    """Les identités sont des couples ; le JSON ne connaît que les listes. Un
    aller-retour qui rendrait des listes ferait échouer toutes les
    comparaisons d'ensembles, silencieusement."""
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "j.json")
    cible = identite({"agence": "Century 21", "agence_url": "https://www.c21-caen.com"})
    historique.noter_visite_tronquee({cible})
    relu = historique.visites_tronquees()
    assert cible in relu and all(isinstance(c, tuple) for c in relu)
    assert json.loads((tmp_path / "j.json").read_text(encoding="utf-8")) == [
        ["Century 21", "c21-caen.com"]]
