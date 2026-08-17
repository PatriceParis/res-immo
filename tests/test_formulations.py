"""Ce que le site affirme doit être ce que les données permettent de dire.

Quatre formulations promettaient plus que le catalogue ne sait :

- « Excellent potentiel refuge » se lisait comme un constat sur la maison,
  alors que c'est le libellé d'une note. Nous ne visitons rien, nos risques
  valent pour la commune, et la note ne fait que classer les biens de ce
  catalogue entre eux ;
- « les terroirs les plus résilients à moins de 350 km de Paris » affirmait
  une propriété des territoires, au superlatif, sans que rien ne l'établisse ;
- « Maisons résilientes à vendre » affirmait que les maisons LE SONT.

La nuance n'est pas rhétorique : une présentation susceptible d'induire en
erreur sur les résultats attendus d'un bien engage celui qui la publie, et
ici, elle pourrait décider un achat.

Ces tests tiennent les deux sens. Le site doit cesser d'affirmer — mais il ne
doit pas cesser de dire ce qu'il fait, sans quoi il ne resterait qu'une liste
d'annonces de plus.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import scoring  # noqa: E402

import re  # noqa: E402

_BRUT = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")

# Le contenu SEUL, commentaires HTML retirés. Ils citent les formules
# supprimées pour expliquer pourquoi elles l'ont été — c'est ce qu'on veut
# garder, et un test qui les lirait accuserait la documentation à la place de
# la page. La même méprise s'était déjà produite sur app.js.
INDEX = re.sub(r"<!--.*?-->", "", _BRUT, flags=re.S)


def test_les_raisons_du_changement_restent_ecrites():
    """L'inverse : sans elles, quelqu'un remettra « plan B au vert » de bonne
    foi dans six mois."""
    assert "Hors zone inondable" in _BRUT, "le commentaire qui l'explique doit rester"


def test_les_libelles_de_note_parlent_de_la_note_et_non_du_bien():
    """« Très bien noté » renvoie à la note ; « excellent potentiel » renvoyait
    à la maison."""
    assert scoring.classe_score(85) == "Très bien noté"
    assert scoring.classe_score(60) == "Bien noté"
    assert scoring.classe_score(45) == "Moyennement noté"
    assert scoring.classe_score(20) == "Faiblement noté"


def test_aucun_libelle_ne_qualifie_plus_le_bien_lui_meme():
    for total in (0, 39, 40, 54, 55, 69, 70, 100):
        libelle = scoring.classe_score(total)
        assert "potentiel" not in libelle.lower(), libelle
        assert "refuge" not in libelle.lower(), libelle
        assert "noté" in libelle.lower(), libelle


def test_le_slogan_n_affirme_plus_une_propriete_des_lieux():
    """« les terroirs les plus résilients » était un superlatif sur des
    territoires, que rien n'établit."""
    assert "les plus résilients" not in INDEX
    assert "plan B au vert" not in INDEX
    assert "notées sur six critères" in INDEX


def test_le_titre_ne_dit_plus_que_les_maisons_sont_resilientes():
    assert "Maisons résilientes à vendre" not in INDEX
    assert "notées face au climat" in INDEX


def test_le_site_dit_toujours_ce_qu_il_fait():
    """L'excès inverse : à force de retirer, il ne resterait qu'une liste
    d'annonces de plus. Le propos doit rester lisible."""
    assert "350 km de Paris" in INDEX
    assert "climat" in INDEX


def test_la_legende_de_la_note_porte_sa_limite_et_son_renvoi():
    """La limite doit être là où la note se lit, pas seulement sur une page
    que personne n'ouvre."""
    assert "compare les biens de ce catalogue entre" in INDEX
    assert "pas pour la parcelle" in INDEX
    assert 'href="/methode"' in INDEX


def test_le_filtre_d_inondation_dit_deja_sa_portee():
    """Celui-ci était déjà correct : il nomme la commune et le recensement.
    Le test le fige, pour qu'un raccourci ne le ramène pas à « hors zone
    inondable »."""
    assert "Commune sans inondation recensée" in INDEX
    assert "Hors zone inondable" not in INDEX
