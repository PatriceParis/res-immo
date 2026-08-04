"""Accès à la base SQLite.

La base est créée automatiquement au premier lancement (fichier data/refuge.db).
Aucune installation de serveur de base de données n'est nécessaire.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS annonces (
    id                TEXT PRIMARY KEY,
    source            TEXT NOT NULL,
    url               TEXT DEFAULT '',
    titre             TEXT NOT NULL,
    description       TEXT DEFAULT '',
    type_bien         TEXT DEFAULT 'maison',
    prix              INTEGER,
    surface_m2        REAL,
    terrain_m2        REAL,
    pieces            INTEGER,
    commune           TEXT,
    code_postal       TEXT,
    departement       TEXT,
    region            TEXT,
    agence            TEXT,
    agence_url        TEXT DEFAULT '',
    photo             TEXT DEFAULT '',
    texte             TEXT DEFAULT '',
    lat               REAL,
    lon               REAL,
    altitude          REAL,
    densite_hab_km2   REAL,
    dpe               TEXT,
    distance_km       REAL,
    temps_voiture_min REAL,
    features_json     TEXT DEFAULT '{}',
    risques_json      TEXT DEFAULT '{}',
    train_json        TEXT DEFAULT '{}',
    score_total       REAL DEFAULT 0,
    score_detail_json TEXT DEFAULT '{}',
    badges_json       TEXT DEFAULT '[]',
    alertes_json      TEXT DEFAULT '[]',
    has_cave          INTEGER DEFAULT 0,
    has_puits         INTEGER DEFAULT 0,
    has_bois          INTEGER DEFAULT 0,
    has_solaire       INTEGER DEFAULT 0,
    has_dependances   INTEGER DEFAULT 0,
    has_potager       INTEGER DEFAULT 0,
    has_troglodyte    INTEGER DEFAULT 0,
    hors_inondation   INTEGER DEFAULT 1,
    date_maj          TEXT
);
CREATE INDEX IF NOT EXISTS idx_annonces_prix  ON annonces (prix);
CREATE INDEX IF NOT EXISTS idx_annonces_score ON annonces (score_total);
CREATE INDEX IF NOT EXISTS idx_annonces_temps ON annonces (temps_voiture_min);
"""

# Ordre de tri accepté par l'API (protection contre l'injection SQL).
TRIS = {
    "score":   "score_total DESC",
    "prix":    "prix ASC",
    "prix_m2": "(prix * 1.0 / NULLIF(surface_m2, 0)) ASC",
    "temps":   "temps_voiture_min ASC",
    "terrain": "terrain_m2 DESC",
}

CHAMPS_JSON = {
    "features_json": "features",
    "risques_json": "risques",
    "train_json": "train",
    "score_detail_json": "score_detail",
    "badges_json": "badges",
    "alertes_json": "alertes",
}


def chemin_db() -> Path:
    """Chemin du fichier SQLite (surchargeable via la variable REFUGE_DB)."""
    if "REFUGE_DB" in os.environ:
        return Path(os.environ["REFUGE_DB"])
    if os.environ.get("VERCEL"):
        # Hébergement serverless : seul /tmp est accessible en écriture.
        return Path("/tmp/refuge.db")
    return RACINE / "data" / "refuge.db"


def connexion() -> sqlite3.Connection:
    chemin = chemin_db()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(chemin)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrer(conn)
    return conn


def _migrer(conn: sqlite3.Connection) -> None:
    """Ajoute les colonnes récentes à une base créée par une version antérieure."""
    existantes = {r[1] for r in conn.execute("PRAGMA table_info(annonces)").fetchall()}
    for colonne, definition in (("agence", "TEXT"), ("agence_url", "TEXT DEFAULT ''"),
                                ("photo", "TEXT DEFAULT ''"), ("texte", "TEXT DEFAULT ''"),
                                ("train_json", "TEXT DEFAULT '{}'"),
                                ("has_troglodyte", "INTEGER DEFAULT 0")):
        if colonne not in existantes:
            conn.execute(f"ALTER TABLE annonces ADD COLUMN {colonne} {definition}")


def nb_annonces(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM annonces").fetchone()[0]


def upsert_annonce(conn: sqlite3.Connection, a: dict) -> None:
    """Insère ou met à jour une annonce (identifiée par son id)."""
    ligne = {
        "id": a["id"],
        "source": a.get("source", "inconnue"),
        "url": a.get("url", ""),
        "titre": a.get("titre", "Sans titre"),
        "description": a.get("description", ""),
        "type_bien": a.get("type_bien", "maison"),
        "prix": a.get("prix"),
        "surface_m2": a.get("surface_m2"),
        "terrain_m2": a.get("terrain_m2"),
        "pieces": a.get("pieces"),
        "commune": a.get("commune"),
        "code_postal": a.get("code_postal"),
        "departement": a.get("departement"),
        "region": a.get("region"),
        "agence": a.get("agence"),
        "agence_url": a.get("agence_url", ""),
        "photo": a.get("photo", ""),
        "texte": a.get("texte", ""),
        "lat": a.get("lat"),
        "lon": a.get("lon"),
        "altitude": a.get("altitude"),
        "densite_hab_km2": a.get("densite_hab_km2"),
        "dpe": a.get("dpe"),
        "distance_km": a.get("distance_km"),
        "temps_voiture_min": a.get("temps_voiture_min"),
        "features_json": json.dumps(a.get("features", {}), ensure_ascii=False),
        "risques_json": json.dumps(a.get("risques", {}), ensure_ascii=False),
        "train_json": json.dumps(a.get("train") or {}, ensure_ascii=False),
        "score_total": a.get("score_total", 0),
        "score_detail_json": json.dumps(a.get("score_detail", {}), ensure_ascii=False),
        "badges_json": json.dumps(a.get("badges", []), ensure_ascii=False),
        "alertes_json": json.dumps(a.get("alertes", []), ensure_ascii=False),
        "has_cave": a.get("has_cave", 0),
        "has_puits": a.get("has_puits", 0),
        "has_bois": a.get("has_bois", 0),
        "has_solaire": a.get("has_solaire", 0),
        "has_dependances": a.get("has_dependances", 0),
        "has_potager": a.get("has_potager", 0),
        "has_troglodyte": a.get("has_troglodyte", 0),
        "hors_inondation": a.get("hors_inondation", 1),
        "date_maj": a.get("date_maj", date.today().isoformat()),
    }
    colonnes = ", ".join(ligne)
    jokers = ", ".join("?" for _ in ligne)
    conn.execute(
        f"INSERT OR REPLACE INTO annonces ({colonnes}) VALUES ({jokers})",
        list(ligne.values()),
    )


def _row_vers_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d.pop("texte", None)  # texte de détection interne, non exposé par l'API
    for colonne, cle in CHAMPS_JSON.items():
        try:
            d[cle] = json.loads(d.pop(colonne) or "null")
        except (json.JSONDecodeError, KeyError):
            d[cle] = None
    return d


def chercher(conn: sqlite3.Connection, filtres: dict) -> tuple[int, list[dict]]:
    """Recherche filtrée. Renvoie (nombre total, page de résultats)."""
    clauses, params = ["1=1"], []

    numeriques = {
        "prix_min": "prix >= ?",
        "prix_max": "prix <= ?",
        "temps_max": "temps_voiture_min <= ?",
        "surface_min": "surface_m2 >= ?",
        "terrain_min": "terrain_m2 >= ?",
        "score_min": "score_total >= ?",
    }
    for cle, sql in numeriques.items():
        valeur = filtres.get(cle)
        if valeur is not None:
            clauses.append(sql)
            params.append(valeur)

    drapeaux = {
        "cave": "has_cave = 1",
        "puits": "has_puits = 1",
        "bois": "has_bois = 1",
        "solaire": "has_solaire = 1",
        "dependances": "has_dependances = 1",
        "potager": "has_potager = 1",
        "troglodyte": "has_troglodyte = 1",
        "hors_inondation": "hors_inondation = 1",
    }
    for cle, sql in drapeaux.items():
        if filtres.get(cle):
            clauses.append(sql)

    if filtres.get("type_bien"):
        clauses.append("type_bien = ?")
        params.append(filtres["type_bien"])

    if filtres.get("region"):
        clauses.append("region = ?")
        params.append(filtres["region"])

    if filtres.get("agence"):
        clauses.append("agence = ?")
        params.append(filtres["agence"])

    if filtres.get("q"):
        clauses.append("(titre LIKE ? OR description LIKE ? OR commune LIKE ?)")
        motif = f"%{filtres['q']}%"
        params.extend([motif, motif, motif])

    ou = " AND ".join(clauses)
    tri = TRIS.get(filtres.get("tri", "score"), TRIS["score"])
    limite = min(int(filtres.get("limit", 200)), 500)
    decalage = max(int(filtres.get("offset", 0)), 0)

    total = conn.execute(f"SELECT COUNT(*) FROM annonces WHERE {ou}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM annonces WHERE {ou} ORDER BY {tri}, score_total DESC LIMIT ? OFFSET ?",
        params + [limite, decalage],
    ).fetchall()
    return total, [_row_vers_dict(r) for r in rows]


def meta(conn: sqlite3.Connection) -> dict:
    """Bornes et compteurs utilisés pour initialiser les filtres de l'interface."""
    row = conn.execute(
        """
        SELECT COUNT(*)                AS nb,
               MIN(prix)               AS prix_min,
               MAX(prix)               AS prix_max,
               MIN(temps_voiture_min)  AS temps_min,
               MAX(temps_voiture_min)  AS temps_max,
               SUM(has_cave)           AS nb_cave,
               SUM(has_puits)          AS nb_puits,
               SUM(has_bois)           AS nb_bois,
               SUM(has_solaire)        AS nb_solaire,
               SUM(has_dependances)    AS nb_dependances,
               SUM(has_potager)        AS nb_potager
        FROM annonces
        """
    ).fetchone()
    types = [r[0] for r in conn.execute(
        "SELECT DISTINCT type_bien FROM annonces ORDER BY type_bien").fetchall()]
    sources = [r[0] for r in conn.execute(
        "SELECT DISTINCT source FROM annonces ORDER BY source").fetchall()]
    return {**dict(row), "types": types, "sources": sources}


def agences(conn: sqlite3.Connection) -> list[dict]:
    """Liste des agences présentes en base, avec le nombre de biens et le score moyen."""
    rows = conn.execute(
        """
        SELECT agence,
               MAX(agence_url)     AS agence_url,
               COUNT(*)            AS nb,
               ROUND(AVG(score_total)) AS score_moyen
        FROM annonces
        WHERE agence IS NOT NULL AND agence <> ''
        GROUP BY agence
        ORDER BY nb DESC, agence
        """
    ).fetchall()
    return [dict(r) for r in rows]
