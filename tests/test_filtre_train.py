"""« Paris en moins d'une heure de train » se demandait dans un menu de gares.

Le critère existait déjà — en base (`train_max`) comme dans l'API — mais il
n'avait pas de contrôle à lui : il vivait dans la liste « Accès par le train »,
sous trois entrées (« moins d'1 h », « moins d'1 h 30 », « moins de 2 h »)
coincées au-dessus des noms de gares. Un seul menu portait donc deux questions
différentes : « une gare rapide » et « celle-là ».

Or le temps de route, lui, a son curseur depuis toujours. Les deux questions
sont pourtant la même — à quelle distance de Paris ? — posées pour deux modes
de transport, et le train est le plus structurant des deux pour un refuge : il
reste praticable sans voiture et sans carburant.

Le curseur rend donc la paire symétrique, et le menu des gares redevient ce
que son nom dit. Ces tests tiennent les deux bouts : le critère part bien de
l'interface, et il n'y part qu'une fois.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import db  # noqa: E402

INTERFACE = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")
SCRIPT = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_le_curseur_existe_a_cote_de_celui_de_la_route():
    """Les deux questions se posent ensemble ou ne se posent pas : un critère
    rangé ailleurs que son jumeau ne se trouve pas."""
    assert 'id="f-train"' in INTERFACE
    assert INTERFACE.index('id="f-temps"') < INTERFACE.index('id="f-train"')


def test_le_curseur_envoie_bien_le_critere():
    """Un contrôle qui n'envoie rien est un décor."""
    assert 'p.set("train_max"' in SCRIPT
    assert '$("#f-train").value' in SCRIPT


def test_le_curseur_au_maximum_ne_filtre_pas():
    """Même convention que le prix et la route : poussé à fond, il ne dit
    rien — sans quoi un curseur jamais touché écarterait en silence tous les
    biens sans gare connue."""
    assert 'if (train < +$("#f-train").max) p.set("train_max", train);' in SCRIPT


def test_le_critere_ne_part_plus_du_menu_des_gares():
    """Deux contrôles pour un même critère, c'est une contradiction en
    attente : l'un dit « moins d'1 h », l'autre « 2 h », et le dernier lu
    gagne. Le menu ne garde que la gare précise."""
    assert "max:" not in SCRIPT, "le menu porte encore un temps de trajet"
    assert 'if (gare) p.set("gare", gare);' in SCRIPT


def test_il_se_remet_a_zero_comme_les_autres():
    """« Réinitialiser » qui laisse un filtre actif est le pire des deux
    mondes : la liste ment et le contrôle a l'air neutre."""
    assert '$("#f-train").value = $("#f-train").max;' in SCRIPT


def test_il_se_rafraichit_en_glissant():
    assert '"#f-train"' in SCRIPT.split("addEventListener")[0].rsplit("for (const id of", 1)[-1] \
        or '"#f-prix", "#f-temps", "#f-train", "#f-score"' in SCRIPT


def test_l_affichage_dit_sans_limite_au_maximum():
    assert 'id="aff-train"' in INTERFACE
    assert '$("#aff-train").textContent' in SCRIPT


def test_l_aide_previent_que_les_biens_sans_gare_sortent():
    """Le SQL écarte les biens dont aucune gare n'est connue dès qu'une limite
    est posée (ils ne remplissent pas la condition). Ne pas le dire ferait
    passer une ignorance pour une absence de desserte."""
    debut = INTERFACE.index('id="f-train"') - 700
    bloc = INTERFACE[debut:INTERFACE.index('id="f-train"')]
    assert "aucune gare" in bloc.lower() or "sans gare" in bloc.lower()


# --- et le critère lui-même, côté base -------------------------------------

@pytest.fixture()
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "essai.db"))
    conn = db.connexion()
    for identifiant, gare, minutes in (("a", "Creil", 30), ("b", "Chartres", 65),
                                       ("c", "Troyes", 90), ("d", None, None)):
        db.upsert_annonce(conn, {
            "id": identifiant, "titre": f"Maison {identifiant}",
            "type_bien": "maison", "commune": "X", "prix": 200000,
            "train": {"nom": gare, "minutes_paris": minutes} if gare else {}})
    conn.commit()
    yield conn
    conn.close()


@pytest.mark.parametrize("minutes, attendus", [
    (30, {"a"}), (60, {"a"}), (90, {"a", "b", "c"}), (75, {"a", "b"}),
])
def test_le_curseur_coupe_ou_il_doit(base, minutes, attendus):
    _, items = db.chercher(base, {"train_max": minutes})
    assert {b["id"] for b in items} == attendus
