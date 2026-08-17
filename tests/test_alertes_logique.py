"""La logique des alertes, jugée hors ligne — jetons, critères, courriels.

Ce que ces tests protègent avant tout : la frontière juridique posée sur
/alertes. Le visiteur choisit, le site filtre, personne n'est mis en relation.
Et la frontière RGPD : rien ne part sans activation, tout s'efface d'un lien.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import alertes  # noqa: E402

SECRET = "un-secret-de-test-suffisamment-long"


# --- validation ------------------------------------------------------------

def test_une_demande_propre_est_normalisee():
    email, prix, terroirs = alertes.valider(
        "  Patrice@Exemple.FR ", "150000", ["Normandie", "Normandie"])
    assert email == "patrice@exemple.fr"
    assert prix == 150_000
    assert terroirs == ["Normandie"], "les doublons ne comptent qu'une fois"


def test_les_demandes_impossibles_sont_refusees_avec_la_raison():
    for email, prix, terroirs in (
            ("pas-une-adresse", 150_000, ["Normandie"]),
            ("a@b.fr", 150_000, []),
            ("a@b.fr", 150_000, ["Bretagne"]),      # hors périmètre
            ("a@b.fr", 10_000, ["Normandie"]),      # sous le plancher
            ("a@b.fr", 9_999_999, ["Normandie"]),   # au-delà du catalogue
            ("a@b.fr", "cher", ["Normandie"])):
        with pytest.raises(ValueError):
            alertes.valider(email, prix, terroirs)


def test_le_budget_est_facultatif():
    _, prix, _ = alertes.valider("a@b.fr", None, ["Normandie"])
    assert prix is None


# --- jetons ----------------------------------------------------------------

def test_le_jeton_depend_de_l_adresse_et_du_secret():
    a = alertes.jeton("a@b.fr", SECRET)
    assert a == alertes.jeton("A@B.FR ", SECRET), "la casse ne change pas le jeton"
    assert a != alertes.jeton("autre@b.fr", SECRET)
    assert a != alertes.jeton("a@b.fr", "autre-secret")
    assert alertes.jeton_valide("a@b.fr", SECRET, a)
    assert not alertes.jeton_valide("a@b.fr", SECRET, a[:-1] + "0")


def test_un_secret_vide_ne_signe_rien():
    """Un HMAC au secret vide serait un jeton que tout le monde peut forger :
    mieux vaut échouer que signer pour rien."""
    with pytest.raises(ValueError):
        alertes.jeton("a@b.fr", "")
    assert not alertes.jeton_valide("a@b.fr", "", "n-importe-quoi")


# --- critères --------------------------------------------------------------

BIEN = {"region": "Normandie", "prix": 140_000, "vue_le": "2026-08-17"}


def test_le_bien_correspond_aux_criteres_du_visiteur():
    assert alertes.correspond(BIEN, 150_000, ["Normandie"])
    assert not alertes.correspond(BIEN, 150_000, ["Grand Est"])
    assert not alertes.correspond(BIEN, 100_000, ["Normandie"])


def test_un_bien_sans_prix_ne_correspond_jamais_a_un_budget():
    """Promettre « sous 150 000 € » sur une annonce muette serait inventer.
    Sans critère de budget, en revanche, il passe."""
    muet = dict(BIEN, prix=None)
    assert not alertes.correspond(muet, 150_000, ["Normandie"])
    assert alertes.correspond(muet, None, ["Normandie"])


def test_seules_les_nouveautes_partent():
    """`vue_le` fait foi — la première apparition — et STRICTEMENT après le
    dernier envoi : la même annonce ne doit jamais partir deux fois."""
    biens = [dict(BIEN, vue_le="2026-08-15"), dict(BIEN, vue_le="2026-08-17")]
    assert len(alertes.nouveaux_depuis(biens, "2026-08-15")) == 1
    assert len(alertes.nouveaux_depuis(biens, "2026-08-17")) == 0


# --- courriels -------------------------------------------------------------

def test_le_courriel_d_alerte_porte_les_liens_et_la_porte_de_sortie():
    sujet, texte = alertes.corps_alerte(
        "a@b.fr", 150_000, ["Normandie"],
        [{"region": "Normandie", "prix": 140_000, "commune": "Bellême",
          "code_postal": "61130", "type_bien": "maison", "surface_m2": 100,
          "id": "x-1"}],
        SECRET, base="https://exemple.fr")
    assert "1 nouvelle maison" in sujet
    assert "https://exemple.fr/annonce/" in texte
    assert "desinscrire" in texte and alertes.jeton("a@b.fr", SECRET) in texte
    assert "effacement immédiat" in texte
    assert "<" not in texte.replace("</", "").split("http")[0], "texte brut, pas de HTML"


def test_le_courriel_d_alerte_ne_deborde_pas():
    """Cent biens d'un coup : on en liste trente et on compte le reste. Un
    courriel-fleuve finit en indésirable et ne se lit pas."""
    biens = [{"region": "Normandie", "prix": 100_000 + i, "commune": "Ici",
              "type_bien": "maison", "id": f"b-{i}"} for i in range(100)]
    _, texte = alertes.corps_alerte("a@b.fr", None, ["Normandie"], biens, SECRET)
    assert texte.count("/annonce/") == alertes.BIENS_PAR_COURRIEL
    assert "et 70 autre(s)" in texte


def test_le_courriel_d_activation_dit_ce_qui_se_passe_sans_clic():
    sujet, texte = alertes.corps_confirmation(
        "a@b.fr", None, ["Normandie"], SECRET, base="https://exemple.fr")
    assert "Activez" in sujet
    assert "confirmer" in texte and alertes.jeton("a@b.fr", SECRET) in texte
    assert "ignorez simplement ce message" in texte


def test_aucun_courriel_ne_porte_de_pixel_ni_d_image():
    """Le site ne trace pas ses visiteurs ; ses courriels ne tracent pas
    leurs lecteurs. Le texte est la seule forme qui le garantisse."""
    for corps in (alertes.corps_alerte("a@b.fr", None, ["Normandie"],
                                       [dict(BIEN, id="i")], SECRET)[1],
                  alertes.corps_confirmation("a@b.fr", None, ["Normandie"], SECRET)[1]):
        assert "<img" not in corps and "<html" not in corps
        assert "ni image ni suivi d'ouverture" in corps
