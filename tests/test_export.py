"""Tests de l'export vers data/annonces_reel.json.

Deux régressions, en sens inverse, encadrent ce que l'export doit publier.

En août 2026, l'export est passé par `_row_vers_dict`, qui retire `texte` :
le fichier ne contenait plus le texte des pages, et au rechargement la
détection des critères (cave, poêle, dépendances…) ne voyait plus qu'une
description de quelques lignes — les scores s'effondraient sans erreur
visible. Le remède d'alors fut de republier le texte entier.

Le 1er octobre, la mesure a donné le prix de ce remède : vingt-six méga-octets
de pages de tiers dans un dépôt public, dont quatre mille deux cents annonces
avec le numéro de mobile d'un mandataire et quatre mille sept cents avec un
courriel nominatif. Le fichier publie désormais ce qu'on a LU — critères, état
déclaré, bien vendu, page catalogue — et plus jamais la page. Ces tests
tiennent les deux bouts : le texte ne sort pas, et la détection lui survit.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement, db  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exporter_reel", RACINE / "scripts" / "exporter_reel.py")
exporter_reel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exporter_reel)

PAGE = ("Belle longère avec cave voûtée, puits et poêle à bois. Aucun travaux "
        "à prévoir. Contact : 06 12 34 56 78 — agent@agence-test.fr. Réf. 1234")


def test_export_publie_la_detection_et_jamais_le_texte(tmp_path, monkeypatch):
    """La ligne est préparée comme les trois collecteurs la préparent — par
    `preparer_annonce`, qui lit la page entière — puis exportée."""
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "test.db"))
    conn = db.connexion()
    db.upsert_annonce(conn, chargement.preparer_annonce({
        "id": "x1", "source": "agence-test", "titre": "Longère avec cave",
        "url": "https://agence.fr/vente/1-belleme/maison/1-longere",
        "texte": PAGE, "surface_m2": 140, "prix": 250000, "lat": 48.3, "lon": 0.5,
    }))
    conn.commit()

    row = conn.execute("SELECT * FROM annonces WHERE id = 'x1'").fetchone()
    bien = exporter_reel._bien(row)
    conn.close()

    assert "texte" not in bien, "le texte de la page ne doit plus sortir"
    assert bien["features"]["cave"] and bien["features"]["puits"] and bien["features"]["bois"], (
        "la détection doit survivre à l'export sans le texte")
    assert bien["etat_declare"] == "sans_travaux"
    assert bien["vendu"] is False and bien["plusieurs_biens"] is False
    assert bien["titre"] == "Longère avec cave"


def test_un_bien_deja_publie_perd_son_texte_sans_perdre_sa_detection():
    """Les biens du fichier précédent portent encore leur texte et aucun
    constat : on constate une dernière fois, puis on retire."""
    allege = exporter_reel.alleger({"id": "x", "titre": "Longère", "texte": PAGE,
                                    "prix": 250000, "lat": 48.3, "lon": 0.5})
    assert "texte" not in allege
    assert allege["features"]["cave"] and allege["features"]["puits"]
    assert allege["etat_declare"] == "sans_travaux"
    assert allege["vendu"] is False and allege["plusieurs_biens"] is False


def test_un_bien_vendu_ou_une_page_catalogue_le_restent_une_fois_alleges():
    vendu = exporter_reel.alleger({"id": "v", "titre": "Maison",
                                   "texte": "Vendu — sous compromis signé."})
    assert vendu["vendu"] is True
    catalogue = exporter_reel.alleger({"id": "c", "titre": "Nos maisons",
                                       "texte": "Réf. 101 … Réf. 202 … Réf. 303"})
    assert catalogue["plusieurs_biens"] is True


def test_un_bien_deja_allege_n_est_que_projete():
    """Sans texte, rien à constater : les constats existants sont gardés tels
    quels, et seuls les champs publiés sortent."""
    bien = exporter_reel.alleger({"id": "y", "titre": "Maison", "features": {"cave": True},
                                  "etat_declare": "travaux", "vendu": False,
                                  "plusieurs_biens": False, "champ_inconnu": 1})
    assert bien["features"] == {"cave": True} and bien["etat_declare"] == "travaux"
    assert "champ_inconnu" not in bien and "texte" not in bien


def test_deux_annonces_vers_la_meme_page_sont_fusionnees():
    """Cas réel : neuf biens en double parce que l'identifiant est fabriqué à
    partir du nom de l'agence, et qu'une collecte ciblée l'avait renommée
    d'après son domaine (`ajc-immobilier-com-…` au lieu de `ajc-immobilier-…`).

    L'URL, elle, n'a pas changé : c'est le seul repère fiable.
    """
    url = "https://www.ajc-immobilier.com/maison-a-vendre-Cheille.htm"
    fusion = exporter_reel.sans_doublon_d_url([
        {"id": "ajc-immobilier-com-a80e", "url": url,
         "vue_le": "2026-08-04", "revue_le": "2026-08-05"},
        {"id": "ajc-immobilier-a80e", "url": url,
         "vue_le": "2026-08-06", "revue_le": "2026-08-06"},
    ])

    assert len(fusion) == 1
    assert fusion[0]["id"] == "ajc-immobilier-a80e", "on garde la version la plus fraîche"
    assert fusion[0]["vue_le"] == "2026-08-04", (
        "le bien est connu depuis la première fois qu'on l'a vu, pas depuis "
        "le changement de nom de l'agence")


def test_des_biens_distincts_sont_tous_conserves():
    biens = [{"id": "a", "url": "https://agence.fr/1"},
             {"id": "b", "url": "https://agence.fr/2"},
             {"id": "c", "url": None}, {"id": "d", "url": None}]
    assert len(exporter_reel.sans_doublon_d_url(biens)) == 4
