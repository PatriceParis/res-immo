"""Tests de l'export vers data/annonces_reel.json.

Régression importante : l'export est passé par `_row_vers_dict`, qui **retire**
le champ `texte` (interne à l'API). Résultat, le fichier exporté ne contenait
plus le texte des pages : au rechargement, la détection des critères (cave,
poêle, dépendances…) ne voyait plus qu'une description de quelques lignes et
les scores s'effondraient — sans aucune erreur visible.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import db  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exporter_reel", RACINE / "scripts" / "exporter_reel.py")
exporter_reel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exporter_reel)


def test_export_conserve_le_texte_de_detection(tmp_path, monkeypatch):
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "test.db"))
    conn = db.connexion()
    db.upsert_annonce(conn, {
        "id": "x1", "source": "agence-test", "titre": "Longère avec cave",
        "url": "https://agence.fr/vente/1-belleme/maison/1-longere",
        "texte": "Belle longère avec cave voûtée, puits et poêle à bois.",
        "surface_m2": 140, "prix": 250000, "lat": 48.3, "lon": 0.5,
    })
    conn.commit()

    row = conn.execute("SELECT * FROM annonces WHERE id = 'x1'").fetchone()
    bien = exporter_reel._bien(row)
    conn.close()

    assert "cave" in bien["texte"], "le texte de détection doit survivre à l'export"
    assert bien["titre"] == "Longère avec cave"
