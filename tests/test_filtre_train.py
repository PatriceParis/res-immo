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


# --- L'autre moitié de l'accès sans voiture ---------------------------------
#
# Le temps de train disait à quelle distance de Paris on se trouve ; il ne
# disait pas à quelle distance de la GARE. « Paris en une heure » ne vaut rien
# si la gare est à vingt-cinq kilomètres : il faut une voiture pour l'atteindre,
# et c'est précisément ce dont le pilier « accès sans voiture » cherche à se
# passer. La donnée était là — affichée sur la fiche, « Migennes · à 8.5 km » —
# mais nulle part filtrable.
#
# Mesuré sur le catalogue du 15 novembre 2026 : 4 628 biens ont une gare
# connue, et leur distance médiane est de 13,2 km. La moitié d'entre eux sont
# donc plus loin de leur gare que ce qu'on parcourt à pied.

def test_le_curseur_de_distance_existe_sous_celui_du_train():
    """Les trois questions d'accès — route, train, gare — se posent ensemble."""
    assert 'id="f-gare-km"' in INTERFACE
    assert INTERFACE.index('id="f-train"') < INTERFACE.index('id="f-gare-km"')


def test_il_envoie_le_critere_et_se_tait_au_maximum():
    assert 'p.set("gare_km_max", gareKm)' in SCRIPT
    assert 'if (gareKm < +$("#f-gare-km").max) p.set("gare_km_max", gareKm);' in SCRIPT


def test_il_se_remet_a_zero_avec_les_autres():
    assert '$("#f-gare-km").value = $("#f-gare-km").max;' in SCRIPT


def test_l_aide_previent_que_les_biens_sans_gare_sortent():
    """Même exigence que pour le temps de train : ne pas faire passer une
    ignorance pour une absence de desserte. Elle pèse lourd ici — 27 % du
    catalogue seulement a une gare connue."""
    debut = INTERFACE.index('id="f-gare-km"') - 800
    bloc = INTERFACE[debut:INTERFACE.index('id="f-gare-km"')]
    assert "aucune gare" in bloc.lower()


@pytest.fixture()
def base_km(tmp_path, monkeypatch):
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "km.db"))
    conn = db.connexion()
    for identifiant, gare, km in (("pres", "Creil", 3.2), ("loin", "Chartres", 22.0),
                                  ("sans", None, None)):
        conn_bien = {"id": identifiant, "titre": "Maison", "type_bien": "maison",
                     "commune": "X", "prix": 200000}
        if gare:
            conn_bien["train"] = {"nom": gare, "km": km, "minutes_paris": 60}
        db.upsert_annonce(conn, conn_bien)
    conn.commit()
    yield conn
    conn.close()


@pytest.mark.parametrize("seuil, attendus", [
    (3, set()), (5, {"pres"}), (22, {"pres", "loin"}), (25, {"pres", "loin"}),
])
def test_le_curseur_coupe_ou_il_doit(base_km, seuil, attendus):
    _, items = db.chercher(base_km, {"gare_km_max": seuil})
    assert {b["id"] for b in items} == attendus


def test_un_bien_sans_gare_connue_est_ecarte(base_km):
    """Il ne remplit pas la condition : le garder reviendrait à promettre une
    gare à portée qu'on n'a pas constatée."""
    _, items = db.chercher(base_km, {"gare_km_max": 25})
    assert "sans" not in {b["id"] for b in items}
    total, _ = db.chercher(base_km, {})
    assert total == 3, "sans filtre, il reste au catalogue"


def test_la_distance_est_rangee_en_colonne(base_km):
    """Sans colonne, pas de filtre SQL : la distance resterait une note de bas
    de page sur la fiche, comme elle l'était."""
    ligne = base_km.execute(
        "SELECT gare_km FROM annonces WHERE id = 'pres'").fetchone()
    assert ligne["gare_km"] == pytest.approx(3.2)
