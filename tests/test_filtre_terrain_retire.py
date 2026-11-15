"""Le filtre « Terrain minimum » a été retiré, et doit le rester partout.

Ce dépôt a déjà écrit la raison, pour le filtre « Agence » puis pour le tri
« Meilleur prix / secteur » : un critère retiré de l'interface mais laissé
dans l'API, le SQL ou le contrat de cohérence devient une clause morte — et
une clause morte finit par être réactivée par mégarde, ou par faire vérifier
une promesse qui n'est plus faite.

Le TRI par terrain, lui, reste proposé : classer du plus grand terrain au
plus petit répond à la même envie sans rien cacher, là où un seuil écartait
en silence les annonces dont le terrain n'est pas renseigné.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import coherence, db  # noqa: E402

INTERFACE = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")
SCRIPT = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_le_controle_n_est_plus_dans_l_interface():
    assert 'id="f-terrain"' not in INTERFACE
    assert "Terrain minimum" not in INTERFACE.replace(
        "Le filtre « Terrain minimum » a été retiré", "")


def test_le_script_ne_l_envoie_plus():
    assert "f-terrain" not in SCRIPT
    assert "terrain_min" not in SCRIPT


def test_le_sql_n_a_plus_de_clause_morte():
    source = (RACINE / "app" / "db.py").read_text(encoding="utf-8")
    assert '"terrain_min":' not in source


def test_l_api_n_a_plus_de_parametre_orphelin():
    source = (RACINE / "app" / "main.py").read_text(encoding="utf-8")
    assert "terrain_min" not in source


def test_le_contrat_ne_promet_plus_ce_seuil():
    """Le contrat ne décrit que ce qui est RÉELLEMENT proposé — même règle
    que pour le tri « affaire », retiré de TRIS_ANNONCES le 9 août."""
    source = (RACINE / "app" / "coherence.py").read_text(encoding="utf-8")
    assert '"terrain_min"' not in source


def test_le_tri_par_terrain_reste(tmp_path, monkeypatch):
    """Ce qui est retiré est le SEUIL, pas la possibilité de classer."""
    assert "terrain" in coherence.TRIS_ANNONCES
    assert "terrain" in db.TRIS
    assert '<option value="terrain"' in INTERFACE or ">terrain<" in INTERFACE.lower()


def test_un_seuil_de_terrain_envoye_a_la_main_ne_filtre_plus(tmp_path, monkeypatch):
    """Une URL ancienne, un marque-page : le paramètre doit être ignoré, pas
    appliqué en douce — sans quoi deux visiteurs verraient deux catalogues."""
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "t.db"))
    conn = db.connexion()
    for identifiant, terrain in (("petit", 200.0), ("grand", 9000.0)):
        db.upsert_annonce(conn, {"id": identifiant, "titre": "Maison",
                                 "type_bien": "maison", "commune": "X",
                                 "prix": 200000, "terrain_m2": terrain})
    conn.commit()
    total, _ = db.chercher(conn, {"terrain_min": 5000})
    assert total == 2, "le seuil s'applique encore"
    conn.close()
