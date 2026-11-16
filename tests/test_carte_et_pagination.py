"""Seize mille biens tenaient sur une page, et personne ne pouvait les voir.

Deux défauts jumeaux, trouvés en mesurant la page plutôt qu'en la regardant :

- la LISTE servait 250 biens d'un bloc. Sur téléphone, la page mesurait
  109 189 pixels de haut — cent trente écrans — et les biens au-delà du 250e
  n'étaient atteignables QUE par les filtres, ce que personne ne devine.
- la CARTE ne portait que ces mêmes 250, en un amas de marqueurs illisible.
  Elle montrait donc à la fois trop (un tas) et trop peu (une page).

La liste se pagine, la carte ne se pagine PAS : on cherche une maison en
regardant où elles sont, et une carte qui ne montrerait que la page courante
dirait de la région quelque chose de faux. Elle porte tous les biens trouvés,
regroupés par le serveur.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import db  # noqa: E402

SCRIPT = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")
INTERFACE = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")


@pytest.fixture()
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "carte.db"))
    conn = db.connexion()
    # Trois paquets bien séparés : Caen, Le Mans, Troyes.
    paquets = [("caen", 49.18, -0.37, 30), ("mans", 47.99, 0.19, 12),
               ("troyes", 48.29, 4.07, 6)]
    for prefixe, lat, lon, combien in paquets:
        for i in range(combien):
            db.upsert_annonce(conn, {
                "id": f"{prefixe}-{i}", "titre": "Maison", "type_bien": "maison",
                "commune": prefixe, "prix": 200000, "surface_m2": 100,
                # étalés sur ~2 km : ils se séparent au zoom fin, pas au large
                "lat": lat + i * 0.004, "lon": lon + i * 0.004,
                "score_total": 20 + i * 2})
    # Un bien sans coordonnées : il compte dans la liste, pas sur la carte.
    db.upsert_annonce(conn, {"id": "sans-gps", "titre": "Maison",
                             "type_bien": "maison", "commune": "X", "prix": 1})
    conn.commit()
    yield conn
    conn.close()


def test_la_carte_regroupe_au_large_et_separe_au_zoom(base):
    large = db.points(base, {}, 6)
    fin = db.points(base, {}, 13)
    assert len(large["amas"]) < len(fin["amas"]), (
        "la maille doit s'affiner quand on zoome")
    assert len(large["amas"]) <= 6, "au large, trois paquets font peu de cercles"


def test_aucun_bien_ne_se_perd_dans_le_regroupement(base):
    """48 biens posés, 48 retrouvés — le bien sans coordonnées excepté."""
    for zoom in (5, 8, 11, 14):
        r = db.points(base, {}, zoom)
        assert sum(a["n"] for a in r["amas"]) == 48, f"au zoom {zoom}"
        assert r["total"] == 48


def test_un_amas_d_un_seul_bien_porte_son_identifiant(base):
    """À ce moment-là ce n'est plus un amas, c'est l'annonce : elle s'ouvre."""
    fin = db.points(base, {}, 15)["amas"]
    seuls = [a for a in fin if a["n"] == 1]
    assert seuls, "au zoom maximal, les biens doivent se détacher"
    assert all(a["id"] for a in seuls)
    assert all(a["id"] is None for a in fin if a["n"] > 1)


def test_l_amas_dit_l_etendue_des_scores_et_non_leur_moyenne():
    """LE test de cette fonctionnalité, et une erreur que j'ai commise avant
    de la corriger : le premier jet colorait chaque amas par le score MOYEN
    de son groupe. Moyenner un ensemble hétérogène ramène tout vers le
    milieu — chaque cercle de la carte sortait de la même couleur pâle, et
    laissait croire que toute la région était médiocre. L'étendue, elle, dit
    ce que le coin a de mieux et de pire."""
    assert '"score"' not in SCRIPT.split("function marqueurAmas")[1][:900]
    bloc = SCRIPT.split("function marqueurAmas")[1][:900]
    assert "a.bas" in bloc and "a.haut" in bloc


def test_la_carte_applique_les_memes_filtres_que_la_liste(base):
    """Sinon les deux décrivent deux recherches différentes sur un même écran."""
    filtres = {"score_min": 40}
    total_liste, _ = db.chercher(base, dict(filtres, limit=1))
    carte = db.points(base, filtres, 8)
    # la carte compte les mêmes biens, moins ceux sans coordonnées
    sans_gps = base.execute(
        "SELECT COUNT(*) FROM annonces WHERE score_total >= 40 AND lat IS NULL").fetchone()[0]
    assert carte["total"] == total_liste - sans_gps


def test_la_zone_visible_borne_le_regroupement(base):
    """Sans elle, un zoom de quartier redemanderait la France entière à la
    maille du quartier, c'est-à-dire chaque bien un par un."""
    autour_de_caen = db.points(base, {}, 11, (49.0, -1.0, 49.5, 0.0))
    assert autour_de_caen["total"] == 30
    assert all(48.9 < a["lat"] < 49.6 for a in autour_de_caen["amas"])


def test_le_cadre_ignore_la_zone_visible(base):
    """Il sert à EMMENER la carte sur la recherche : le calculer sur ce qu'on
    voit déjà serait circulaire, et choisir « Normandie » ne bougerait rien."""
    r = db.points(base, {}, 11, (49.0, -1.0, 49.5, 0.0), avec_cadre=True)
    sud, ouest, nord, est = r["cadre"]
    assert est > 4.0, "le cadre doit atteindre Troyes, hors de la zone visible"


def test_le_total_vient_d_un_comptage_et_non_d_une_somme(base, monkeypatch):
    """Si la limite coupe, additionner les cellules rendues annoncerait moins
    de biens qu'il n'y en a. Ce dépôt a déjà payé ce travers une fois."""
    monkeypatch.setattr(db, "_AMAS_MAX", 2)
    r = db.points(base, {}, 15)
    assert len(r["amas"]) == 2
    assert r["tronque"] is True
    assert r["total"] == 48, "le total ne doit pas suivre la troncature"


def test_la_liste_se_pagine_sans_trou_ni_doublon(base):
    vus, page = [], 0
    while True:
        _, items = db.chercher(base, {"limit": 10, "offset": page * 10})
        if not items:
            break
        vus += [b["id"] for b in items]
        page += 1
    assert len(vus) == 49, "48 géolocalisés + celui sans coordonnées"
    assert len(set(vus)) == len(vus), "aucun bien ne doit apparaître deux fois"


def test_l_interface_pagine_par_vingt_quatre():
    assert "const BIENS_PAR_PAGE = 24;" in SCRIPT
    assert 'id="pagination"' in INTERFACE


def test_changer_un_filtre_ramene_a_la_premiere_page():
    """Rester page 7 d'une recherche qui n'en compte plus que deux afficherait
    un vide inexplicable."""
    bloc = SCRIPT.split("async function rafraichir()")[1][:400]
    assert "etat.page = 0" in bloc


def test_la_carte_ne_suit_pas_la_pagination():
    """rendreCarte ne doit rien savoir de etat.page ni de l'offset."""
    bloc = SCRIPT[SCRIPT.index("async function rendreCarte()"):]
    bloc = bloc[:bloc.index("// Un bien seul")]
    assert "etat.page" not in bloc and "offset" not in bloc
