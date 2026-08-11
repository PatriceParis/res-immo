"""Mémoire des annonces d'une collecte à l'autre.

Sans elle, impossible de dire ce qui est nouveau, de repérer une baisse de
prix, ni de savoir qu'une annonce a été retirée : c'est pourtant l'essentiel
de ce qu'on attend d'un outil de veille.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.historique import (  # noqa: E402
    ABSENCES_TOLEREES, cle_agence, est_nouveau, fusionner, identite)

# Une cible parcourue, telle que l'export la désigne : nom ET domaine (ici
# vide, ces annonces d'essai n'ayant pas d'adresse d'agence).
AGENCES = {("Agence A", "")}


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
    res = fusionner(avant, [], AGENCES, "2026-08-10")        # B non visitée
    assert len(res) == 1
    assert res[0].get("absences") in (None, 0)               # pas pénalisée


def test_un_reseau_partiellement_visite_ne_perd_pas_ses_autres_agences():
    """Le 10 août, cinquante et une annonces Century 21 ont disparu du
    catalogue alors que leurs pages étaient en ligne.

    Un même nom d'agence couvre douze sites — Caen, Troyes, Nancy, Honfleur…
    La rotation en avait visité cinq. Le nom « Century 21 » entrait donc dans
    l'ensemble des visitées, et les biens des sept autres sites étaient
    comptés absents « chez leur agence », puis retirés à la deuxième absence.
    """
    caen = {"id": "c1", "agence": "Century 21", "prix": 200000,
            "agence_url": "https://www.century21-bertin-caen.com", "vue_le": "2026-08-06"}
    troyes = {"id": "t1", "agence": "Century 21", "prix": 180000,
              "agence_url": "https://century21-martinot-troyes.com", "vue_le": "2026-08-06"}
    # La collecte n'a parcouru que Caen, et n'y a rien trouvé de nouveau.
    visites = {identite(caen)}

    res = fusionner([caen, troyes], [], visites, "2026-08-10")

    par_id = {b["id"]: b for b in res}
    assert par_id["t1"].get("absences") in (None, 0), "Troyes n'a pas été visitée"
    assert par_id["c1"]["absences"] == 1, "Caen, elle, a bien été parcourue"

    # Et la deuxième absence n'emporte que Caen.
    res2 = fusionner(res, [], visites, "2026-08-17")
    assert [b["id"] for b in res2] == ["t1"]


def test_un_reseau_de_mandataires_ne_perd_pas_ses_autres_departements():
    """La faute inverse de la précédente, commise en la corrigeant.

    Les mandataires IAD vivent tous sous `iadfrance.fr`, mais sont parcourus
    département par département — chacun devient « IAD France (37) », « IAD
    France (71) »… Indexer la visite sur le seul domaine marquait donc tout
    le réseau comme parcouru dès qu'un département l'était : deux cent six
    annonces ont disparu au passage mandataires du 11 août.
    """
    indre = {"id": "i37", "agence": "IAD France (37)", "prix": 200000,
             "agence_url": "https://www.iadfrance.fr", "vue_le": "2026-08-07"}
    saone = {"id": "i71", "agence": "IAD France (71)", "prix": 150000,
             "agence_url": "https://www.iadfrance.fr", "vue_le": "2026-08-07"}
    visites = {identite(indre)}          # seul le 37 a été parcouru

    res = fusionner([indre, saone], [], visites, "2026-08-11")

    par_id = {b["id"]: b for b in res}
    assert par_id["i71"].get("absences") in (None, 0), "la Saône-et-Loire n'a pas été vue"
    assert par_id["i37"]["absences"] == 1, "l'Indre-et-Loire, elle, a bien été parcourue"

    res2 = fusionner(res, [], visites, "2026-08-12")
    assert [b["id"] for b in res2] == ["i71"]


def test_le_www_ne_fait_pas_deux_sites():
    """Le collecteur enregistre `www.agence.fr`, l'annonce porte `agence.fr` :
    sans normalisation, le site paraîtrait n'avoir jamais été visité et ses
    biens retirés ne partiraient jamais."""
    assert cle_agence("https://www.agence.fr/nos-biens") == "agence.fr"
    assert cle_agence("https://AGENCE.fr") == "agence.fr"
    assert cle_agence(None) == ""


def test_l_identite_distingue_les_deux_facons_de_partager():
    """Un nom pour douze sites, un site pour douze noms : la paire sépare les
    deux, là où chaque moitié prise seule les confond."""
    c21 = {"agence": "Century 21", "agence_url": "https://www.century21-caen.com"}
    c21_bis = {"agence": "Century 21", "agence_url": "https://century21-troyes.com"}
    iad37 = {"agence": "IAD France (37)", "agence_url": "https://www.iadfrance.fr"}
    iad71 = {"agence": "IAD France (71)", "agence_url": "https://www.iadfrance.fr"}
    assert identite(c21) != identite(c21_bis), "même enseigne, deux sites"
    assert identite(iad37) != identite(iad71), "même site, deux cibles"
    assert identite({"agence": "Agence A"}) == ("Agence A", "")


def test_est_nouveau():
    assert est_nouveau({"vue_le": "2026-08-08"}, "2026-08-10")
    assert not est_nouveau({"vue_le": "2026-06-01"}, "2026-08-10")
    assert not est_nouveau({}, "2026-08-10")
