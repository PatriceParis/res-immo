"""Le filtre par gare, qui remplace le filtre par agence.

Personne ne cherche une maison en choisissant d'abord son agence. La gare,
si : c'est elle qui décide si un repli reste compatible avec un travail à
Paris, et si le lieu reste atteignable sans voiture — deux questions au cœur
du projet, là où le nom de l'agence n'en était aucune.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import db  # noqa: E402


def _bien(identifiant, gare=None, minutes=None, prix=200000, **extra):
    return dict({
        "id": identifiant, "titre": f"Maison {identifiant}", "type_bien": "maison",
        "commune": "Bellême", "departement": "61", "region": "Normandie",
        "prix": prix, "surface_m2": 120.0,
        "train": ({"nom": gare, "km": 8.0, "minutes_paris": minutes}
                  if gare else {}),
    }, **extra)


@pytest.fixture()
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "essai.db"))
    conn = db.connexion()
    for annonce in (
        _bien("a", "Creil", 30),
        _bien("b", "Creil", 30, prix=310000),
        _bien("c", "Chartres", 65),
        _bien("d", "Mayenne", 145),
        _bien("e"),                       # aucune gare connue
    ):
        db.upsert_annonce(conn, annonce)
    conn.commit()
    yield conn
    conn.close()


def test_le_filtre_par_agence_n_existe_plus():
    """Il ne doit pas subsister à l'état de paramètre orphelin : une clause
    morte finit toujours par être réactivée par mégarde."""
    source = (RACINE / "app" / "db.py").read_text(encoding="utf-8")
    assert 'filtres.get("agence")' not in source
    interface = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="f-agence"' not in interface


def test_choisir_une_gare_ne_garde_que_les_biens_qu_elle_dessert(base):
    total, items = db.chercher(base, {"gare": "Creil"})
    assert total == 2
    assert {b["id"] for b in items} == {"a", "b"}


def test_paris_en_moins_d_une_heure(base):
    total, items = db.chercher(base, {"train_max": 60})
    assert {b["id"] for b in items} == {"a", "b"}, "Chartres est à 65 min"


def test_un_bien_sans_gare_connue_est_ecarte_du_filtre_train(base):
    """Il ne remplit pas la condition : le montrer reviendrait à promettre un
    accès ferroviaire qu'on n'a pas constaté."""
    _, items = db.chercher(base, {"train_max": 240})
    assert "e" not in {b["id"] for b in items}


def test_sans_filtre_tous_les_biens_restent(base):
    total, _ = db.chercher(base, {})
    assert total == 5


# --- L'inventaire qui peuple le menu ---------------------------------------

def test_les_gares_sont_classees_par_temps_de_trajet(base):
    """Ce que cherche celui qui demande « une gare TGV », c'est d'abord une
    gare RAPIDE. Creil à trente minutes doit se lire avant Mayenne à deux
    heures vingt-cinq — l'ordre alphabétique ferait l'inverse."""
    gares = db.gares(base, {})
    assert [g["nom"] for g in gares] == ["Creil", "Chartres", "Mayenne"]
    assert gares[0]["nb"] == 2


def test_une_gare_sans_bien_n_apparait_pas(base):
    """Le menu ne propose que des choix qui donnent un résultat."""
    noms = {g["nom"] for g in db.gares(base, {})}
    assert "Vendôme–Villiers-sur-Loir TGV" not in noms


def test_les_comptes_du_menu_suivent_les_autres_filtres(base):
    """Annoncer « Creil (2) » quand le budget n'en laisse qu'un serait le même
    mensonge que les pastilles de terroir comptant sans les filtres."""
    gares = db.gares(base, {"prix_max": 250000})
    creil = next(g for g in gares if g["nom"] == "Creil")
    assert creil["nb"] == 1


def test_le_menu_ne_se_filtre_pas_lui_meme(base):
    """Le piège : choisir « Paris en moins d'1 h » aurait fait disparaître du
    menu toutes les gares plus lointaines. L'utilisateur n'aurait pas pu
    revenir en arrière, et le menu aurait prétendu qu'elles n'existent pas."""
    for filtres in ({"train_max": 60}, {"gare": "Creil"}):
        noms = [g["nom"] for g in db.gares(base, filtres)]
        assert noms == ["Creil", "Chartres", "Mayenne"], filtres


def test_la_gare_est_rangee_en_colonne_et_pas_seulement_en_json(base):
    """Sans colonne dédiée, on ne pourrait ni filtrer, ni grouper, ni trier :
    la gare est un critère de recherche, pas une note de bas de page."""
    ligne = base.execute(
        "SELECT gare_nom, gare_minutes FROM annonces WHERE id = 'a'").fetchone()
    assert ligne["gare_nom"] == "Creil"
    assert ligne["gare_minutes"] == 30
