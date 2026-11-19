"""Le menu « Accès par le train » met les gares à grande vitesse en tête.

C'est la première question de qui cherche un repli sans quitter son travail :
non pas quelle gare est la plus proche, mais laquelle met Paris à portée
d'aller-retour. Le menu les range donc dans leur propre groupe, avant les
autres.

Elles ne se reconnaissent PAS à leur nom. Deux seulement portent « TGV »
— Vendôme–Villiers-sur-Loir et Le Creusot–Montceau–Montchanin — alors que
Le Mans, Laval, Montbard, Chalon-sur-Saône, Montceau-les-Mines et
Sablé-sur-Sarthe en sont tout autant. Les énumérer de mémoire serait exposé
à l'erreur et vieillirait mal.

C'est donc la vitesse moyenne vers Paris qui tranche, calculée à vol
d'oiseau : huit gares dépassent 150 km/h, la neuvième tombe à 121, et le saut
est franc. Aucun train classique ne tient 150 km/h de moyenne porte-à-porte,
sa pointe étant à 160.

Ce fichier tient aussi un défaut introduit la veille par l'import du
référentiel SNCF : le menu groupait sur la gare la plus PROCHE tout en
affichant le temps d'une AUTRE. Il annonçait « Pont-l'Évêque à 105 min »
quand ces 105 minutes sont celles de Lisieux — 17 % des biens concernés.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import db, gares  # noqa: E402

SCRIPT = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_les_huit_gares_rapides_sont_reconnues():
    assert gares.GARES_GRANDE_VITESSE == {
        "Vendôme–Villiers-sur-Loir TGV", "Le Creusot–Montceau–Montchanin TGV",
        "Le Mans", "Montbard", "Chalon-sur-Saône", "Laval",
        "Montceau-les-Mines", "Sablé-sur-Sarthe"}


def test_le_nom_ne_fait_pas_la_grande_vitesse():
    """LE test. Le Mans ne porte pas « TGV » et en est une ; s'y fier
    laisserait six gares sur huit dans le mauvais groupe."""
    assert "Le Mans" in gares.GARES_GRANDE_VITESSE
    assert "TGV" not in "Le Mans"


@pytest.mark.parametrize("gare", ["Chartres", "Creil", "Beauvais", "Troyes"])
def test_les_gares_classiques_restent_dehors(gare):
    """Creil est à trente minutes, et ce n'est pas une gare TGV : la
    proximité ne doit pas être confondue avec la vitesse."""
    assert gare not in gares.GARES_GRANDE_VITESSE


def test_le_seuil_tombe_dans_le_vide_entre_les_deux_groupes():
    """150 km/h n'est pas un chiffre rond posé au hasard : la huitième gare
    est à 152, la neuvième à 121. Un seuil choisi dans ce vide-là ne bascule
    aucune gare d'un côté ou de l'autre pour un kilomètre près."""
    vitesses = sorted(
        (gares.vitesse_vers_paris(lat, lon, mn)
         for _, lat, lon, mn, _ in gares.GARES), reverse=True)
    assert vitesses[7] > gares.VITESSE_GRANDE_VITESSE_KMH > vitesses[8]
    assert vitesses[7] - vitesses[8] > 20, "le saut doit rester franc"


@pytest.fixture()
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "gv.db"))
    conn = db.connexion()
    # Le cas réel : la gare la plus proche n'est pas celle qui porte le temps.
    for ident, proche, vers, minutes in (
            ("pontleveque", "Pont-l'Évêque", "Lisieux", 105),
            ("lemans", "Le Mans", "Le Mans", 55),
            ("chartres", "Chartres", "Chartres", 65)):
        db.upsert_annonce(conn, {
            "id": ident, "titre": "Maison", "type_bien": "maison",
            "commune": "X", "prix": 200000,
            "train": {"nom": proche, "km": 3.0, "minutes_paris": minutes,
                      "nom_vers_paris": vers}})
    conn.commit()
    yield conn
    conn.close()


def test_le_menu_nomme_la_gare_qui_porte_le_temps(base):
    """Le défaut de la veille : « Pont-l'Évêque — 1 h 45 » attribuait à une
    halte le trajet de Lisieux."""
    noms = {g["nom"] for g in db.gares(base)}
    assert "Lisieux" in noms
    assert "Pont-l'Évêque" not in noms


def test_le_menu_dit_lesquelles_vont_vite(base):
    par_nom = {g["nom"]: g["grande_vitesse"] for g in db.gares(base)}
    assert par_nom["Le Mans"] is True
    assert par_nom["Chartres"] is False


def test_choisir_une_gare_prend_les_biens_qu_elle_dessert(base):
    """Le filtre suit le menu : choisir Lisieux doit ramener le bien de
    Pont-l'Évêque, qui part de Lisieux pour aller à Paris."""
    _, items = db.chercher(base, {"gare": "Lisieux"})
    assert [b["id"] for b in items] == ["pontleveque"]


def test_l_interface_met_le_groupe_rapide_en_premier():
    assert '"Grande vitesse"' in SCRIPT
    assert SCRIPT.index('bloc("Grande vitesse"') < SCRIPT.index('bloc("Autres gares"')


def _fiche_train(**train):
    base = {"nom": "Le Mans", "km": 0.7, "segment": "A", "minutes_paris": 55,
            "nom_vers_paris": "Le Mans", "km_vers_paris": 0.6,
            "grande_vitesse": True}
    from app import pages
    return pages._gare_vers_paris({"train": {**base, **train}})


def test_la_fiche_dit_que_c_est_un_tgv():
    assert _fiche_train() == "55 min en TGV depuis cette gare"


def test_la_fiche_se_tait_quand_le_train_est_classique():
    """Le silence est la valeur par défaut : sans mesure, pas de mention."""
    assert _fiche_train(nom="Chartres", nom_vers_paris="Chartres",
                        minutes_paris=65, grande_vitesse=False) \
        == "1 h 05 depuis cette gare"


def test_la_fiche_ne_dit_pas_deux_fois_tgv():
    """« en TGV depuis Vendôme–Villiers-sur-Loir TGV » dirait deux fois la
    même chose. Deux des huit gares portent le mot dans leur nom officiel et
    pèsent un quart des biens concernés : le cas n'est pas théorique."""
    phrase = _fiche_train(nom="Saint-Amand-Longpré", segment="C",
                          nom_vers_paris="Vendôme–Villiers-sur-Loir TGV",
                          minutes_paris=42, km_vers_paris=12.3)
    assert phrase.count("TGV") == 1
    assert phrase == "42 min en TGV depuis Vendôme–Villiers-sur-Loir (à 12,3 km)"


def test_le_nom_de_la_gare_reste_entier_pour_un_train_classique():
    """On ne rogne le suffixe que parce que la phrase vient de dire « TGV ».
    Sans la mention, le nom officiel doit rester intact."""
    assert "Vendôme–Villiers-sur-Loir TGV" in _fiche_train(
        nom="Ailleurs", nom_vers_paris="Vendôme–Villiers-sur-Loir TGV",
        grande_vitesse=False)


def test_la_fiche_de_l_application_porte_le_badge():
    assert 'class="tgv"' in SCRIPT
    assert "sansSuffixeTgv" in SCRIPT
    style = (RACINE / "app" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".tgv {" in style, "un badge sans style est invisible"


# --- Le temps de train n'est prêté qu'à la gare qui le porte -----------------
#
# Corrigé dans le menu puis sur les tuiles, le défaut restait à trois endroits
# de la fiche : le badge d'atout, la ligne de faits et la phrase rédigée. Tous
# trois disaient d'une halte qu'on y rejoignait Paris en 55 minutes, quand ce
# temps part du Mans, à vingt-trois kilomètres de là.

_HALTE = {"nom": "Écommoy", "km": 14.7, "segment": "C", "minutes_paris": 55,
          "nom_vers_paris": "Le Mans", "km_vers_paris": 23.6, "grande_vitesse": True}


def test_la_phrase_redigee_nomme_la_gare_du_temps():
    from app import redaction
    bien = {"train": dict(_HALTE), "commune": "Le Grand-Lucé", "prix": 265000}
    texte = " ".join(redaction.description_longue(bien, None))
    assert "d'où Paris se rejoint" not in texte, (
        "la halte se voit prêter le trajet d'une autre gare")
    assert "depuis Le Mans" in texte


def test_la_phrase_reste_simple_quand_c_est_la_meme_gare():
    from app import redaction
    bien = {"train": dict(_HALTE, nom="Le Mans", km=0.7), "commune": "Le Mans",
            "prix": 265000}
    texte = " ".join(redaction.description_longue(bien, None))
    assert "d'où Paris se rejoint en 55 min" in texte


def test_la_ligne_de_faits_nomme_la_gare_du_temps():
    from app import redaction
    lignes = dict(redaction.bloc_de_faits(
        {"train": dict(_HALTE), "prix": 265000, "score_total": 59}))
    assert lignes["🚉"].endswith("Paris en 55 min depuis Le Mans")


def test_le_badge_d_atout_mesure_la_gare_du_temps():
    """« Gare à 14,7 km · Paris en 55 min » : la distance était celle de la
    halte, le temps celui du Mans. Le badge prend désormais la distance de la
    gare qui porte le temps — et à 23,6 km, il ne s'affiche plus."""
    from app import scoring
    base = {"titre": "Maison", "description": "", "features": {}, "risques": {}}
    proche = dict(base, train=dict(_HALTE, km_vers_paris=8.4))
    loin = dict(base, train=dict(_HALTE))
    def badge(annonce):
        detail = scoring.calculer_score(annonce)
        return [b for b in detail["badges"] if b.startswith("Gare à")]
    assert badge(proche) == ["Gare à 8,4 km · Paris en 55 min"]
    assert badge(loin) == []
