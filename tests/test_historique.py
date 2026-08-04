"""Mémoire des annonces d'une collecte à l'autre.

Sans elle, impossible de dire ce qui est nouveau, de repérer une baisse de
prix, ni de savoir qu'une annonce a été retirée : c'est pourtant l'essentiel
de ce qu'on attend d'un outil de veille.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.historique import ABSENCES_TOLEREES, est_nouveau, fusionner  # noqa: E402

AGENCES = {"Agence A"}


def test_annonce_inedite_datee_du_jour():
    res = fusionner([], [{"id": "x", "agence": "Agence A", "prix": 200000}],
                    AGENCES, "2026-08-10")
    assert res[0]["vue_le"] == "2026-08-10"
    assert res[0]["revue_le"] == "2026-08-10"


def test_annonce_deja_connue_garde_sa_date_de_decouverte():
    avant = [{"id": "x", "agence": "Agence A", "prix": 200000, "vue_le": "2026-07-01"}]
    res = fusionner(avant, [{"id": "x", "agence": "Agence A", "prix": 200000}],
                    AGENCES, "2026-08-10")
    assert res[0]["vue_le"] == "2026-07-01"      # découverte, inchangée
    assert res[0]["revue_le"] == "2026-08-10"    # revue aujourd'hui


def test_baisse_de_prix_memorisee():
    avant = [{"id": "x", "agence": "Agence A", "prix": 250000, "vue_le": "2026-07-01"}]
    res = fusionner(avant, [{"id": "x", "agence": "Agence A", "prix": 225000}],
                    AGENCES, "2026-08-10")
    assert res[0]["prix_precedent"] == 250000
    assert res[0]["prix_baisse_le"] == "2026-08-10"

    # La baisse reste affichée à la collecte suivante, si le prix ne bouge plus.
    res2 = fusionner(res, [{"id": "x", "agence": "Agence A", "prix": 225000}],
                     AGENCES, "2026-08-17")
    assert res2[0]["prix_precedent"] == 250000


def test_une_hausse_de_prix_n_est_pas_une_baisse():
    avant = [{"id": "x", "agence": "Agence A", "prix": 200000, "vue_le": "2026-07-01"}]
    res = fusionner(avant, [{"id": "x", "agence": "Agence A", "prix": 210000}],
                    AGENCES, "2026-08-10")
    assert "prix_precedent" not in res[0]


def test_annonce_retiree_disparait_apres_tolerance():
    avant = [{"id": "x", "agence": "Agence A", "prix": 200000, "vue_le": "2026-07-01"}]
    # 1re absence : on tolère (page en erreur, site lent…)
    apres1 = fusionner(avant, [], AGENCES, "2026-08-10")
    assert len(apres1) == 1 and apres1[0]["absences"] == 1
    # 2e absence : l'agence l'a bien retirée
    apres2 = fusionner(apres1, [], AGENCES, "2026-08-17")
    assert apres2 == []


def test_agence_non_visitee_ne_fait_pas_disparaitre_ses_biens():
    """Une collecte écourtée (budget de temps) ne prouve rien sur les biens
    des agences qu'elle n'a pas atteintes."""
    avant = [{"id": "x", "agence": "Agence B", "prix": 200000, "vue_le": "2026-07-01"}]
    res = fusionner(avant, [], {"Agence A"}, "2026-08-10")   # B non visitée
    assert len(res) == 1
    assert res[0].get("absences") in (None, 0)               # pas pénalisée


def test_est_nouveau():
    assert est_nouveau({"vue_le": "2026-08-08"}, "2026-08-10")
    assert not est_nouveau({"vue_le": "2026-06-01"}, "2026-08-10")
    assert not est_nouveau({}, "2026-08-10")
