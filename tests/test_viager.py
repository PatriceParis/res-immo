"""Un prix de viager n'est pas un prix, et rien ne le disait.

Le viager est écarté à la collecte — mesuré le 15 novembre 2026, aucune des
17 224 annonces du catalogue n'en est un. Mais ce filtre-là ne lit que le
TITRE et l'URL, et c'est à peu près tout ce qu'on garde : 81 annonces sur
17 224 — un demi pour cent — conservent une description, le texte des pages
ayant été retiré du fichier public en octobre.

Un viager dont le titre dit seulement « Maison 4 pièces à Brienon » passerait
donc sans que rien ne l'arrête, et il coûterait cher : le prix d'un viager est
un BOUQUET, la part payée comptant. Affiché nu, avec un prix au m² calculé
dessus et un écart au marché qui s'en déduit, il désigne une affaire qui
n'existe pas — et il fausse la comparaison avec toutes les autres annonces.

Ce filet ne retire rien et ne note rien : il fait dire à la fiche ce qu'elle
est. Il ne trouve aujourd'hui aucun bien, et c'est l'état normal — un filet
se juge au jour où quelque chose tombe dedans, pas à son rendement courant.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import pages, qualite  # noqa: E402


def test_le_mot_suffit_ou_qu_il_soit():
    """Titre, description et URL : le viager se nomme à l'un ou l'autre, et
    le chemin de l'URL le dit souvent quand le titre le tait."""
    for annonce in ({"titre": "Maison en VIAGER occupé à Autun"},
                    {"titre": "Maison", "url": "https://x.fr/vente/viager/autun/12"},
                    {"titre": "Maison", "description": "Vente en viager libre."},
                    {"titre": "Maison", "texte": "Bien vendu en viager."}):
        assert qualite.est_viager(annonce), annonce


def test_le_viager_qui_ne_se_nomme_pas():
    """Les deux moitiés du prix le trahissent : un bouquet ET une rente.
    C'est le cas qui justifie ce filet — le titre ne dit rien, la page si."""
    assert qualite.est_viager({
        "titre": "Maison 4 pièces à Brienon",
        "description": "Bouquet de 50 000 € et rente mensuelle de 600 €."})
    assert qualite.est_viager({"titre": "Maison",
                               "description": "Libre au décès du crédirentier."})


def test_ce_qui_ne_doit_PAS_déclencher():
    """Un filet qui attrape des ventes ordinaires est pire que pas de filet :
    il collerait un avertissement faux sur un prix juste.

    « rente » vit dans « rentabilité » et « rentrée », « bouquet » dans un
    jardin. Séparés, ils ne prouvent rien — c'est pourquoi les deux sont
    exigés ensemble."""
    for annonce in ({"titre": "Maison 4 pièces à Brienon"},
                    {"titre": "Maison", "description": "Excellente rentabilité locative."},
                    {"titre": "Maison", "description": "Un bouquet de roses au jardin."},
                    {"titre": "Propriété de caractère, belle rentrée de garage"},
                    {"titre": "Maison", "description": "Rente foncière du terrain voisin."}):
        assert not qualite.est_viager(annonce), annonce


def _bien(**extra):
    return dict({
        "id": "x", "titre": "Maison 4 pièces", "type_bien": "maison",
        "commune": "Autun", "code_postal": "71400", "prix": 69900,
        "surface_m2": 80, "lat": 46.95, "lon": 4.3, "score_total": 55,
        "score_detail": {}, "badges": [], "alertes": [], "risques": {},
        "features": {},
    }, **extra)


def test_la_fiche_prévient_que_le_prix_est_un_bouquet():
    """LE test : ce que l'utilisateur lit. Sans cette phrase, 69 900 € pour
    80 m² se lit comme une affaire, et c'est un quart du prix réel."""
    page = pages.page_annonce(_bien(viager=1), [])
    assert "bouquet" in page
    assert "viager" in page.lower()


def test_une_vente_ordinaire_ne_porte_aucun_avertissement():
    assert "bouquet" not in pages.page_annonce(_bien(viager=0), [])


def test_le_drapeau_traverse_l_export():
    """Le constat est fait quand la page entière est encore lisible ; après
    l'export, plus personne ne pourra le refaire. S'il ne voyage pas, la
    fiche servie n'aura rien à dire."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "exporter_reel", RACINE / "scripts" / "exporter_reel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert "viager" in module.CHAMPS, "le champ serait perdu à l'export"
    allege = module.alleger({"id": "x", "titre": "Maison",
                             "texte": "Vente en viager, bouquet de 40 000 €."})
    assert allege["viager"] == 1
    assert "texte" not in allege, "le texte de la page ne doit pas voyager"


def test_la_colonne_existe_en_base(tmp_path, monkeypatch):
    """Sans colonne, le drapeau ne survivrait pas au rechargement : le
    catalogue servi est reconstruit depuis les seules colonnes."""
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "essai.db"))
    from app import db
    conn = db.connexion()
    db.upsert_annonce(conn, _bien(viager=1))
    conn.commit()
    ligne = conn.execute("SELECT viager FROM annonces WHERE id = 'x'").fetchone()
    assert ligne["viager"] == 1
    _, items = db.chercher(conn, {})
    assert items[0]["viager"] == 1, "l'API doit l'exposer, sinon l'interface est aveugle"
    conn.close()
