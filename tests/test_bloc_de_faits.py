"""Les faits du bien, lisibles en deux secondes.

Les comptes qui diffusent des maisons bon marché ouvrent tous leurs
publications par le même bloc — lieu, prix, chambres, surface. Il tient
debout pour une raison simple : on veut d'abord savoir SI l'on continue à
lire. La prose vient après.

Deux différences avec le leur, et ce sont elles que ces tests protègent : le
prix porte son prix au mètre carré, et la dernière ligne est la note de
résilience — la seule chose qu'aucun de ces comptes ne peut afficher.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages  # noqa: E402
from app.redaction import _nombre, bloc_de_faits  # noqa: E402

COMPLET = {
    "id": "x", "titre": "Longère", "type_bien": "maison",
    "commune": "La Guerche-sur-l'Aubois", "code_postal": "18150",
    "departement": "18", "prix": 66000, "surface_m2": 89.0,
    "terrain_m2": 1713.0, "pieces": 3, "score_total": 52,
    "train": {"nom": "Nevers", "km": 15.0, "minutes_paris": 120},
}


def _texte(bien) -> str:
    return " | ".join(f"{p} {t}" for p, t in bloc_de_faits(bien))


def test_le_bloc_donne_les_faits_dans_l_ordre_ou_on_les_cherche():
    lignes = bloc_de_faits(COMPLET)
    assert [p for p, _ in lignes] == ["📍", "💶", "📐", "🛏", "🚉", "🛡"]


def test_le_prix_porte_son_prix_au_metre_carre():
    """66 000 € ne dit rien seul ; 742 €/m² dit si l'affaire mérite un
    détour. C'est la première des deux différences avec leur bloc."""
    assert "742 €/m²" in _texte(COMPLET)


def test_la_derniere_ligne_est_la_resilience():
    """La seconde différence, et la raison d'être du catalogue : elle ferme
    le bloc, elle ne se perd pas au milieu."""
    picto, texte = bloc_de_faits(COMPLET)[-1]
    assert picto == "🛡" and texte == "Résilience 52/100"


def test_une_ligne_sans_matiere_disparait_au_lieu_de_mentir():
    """Un tiret ou « n.c. » sur cinq lignes fait une fiche qui a l'air
    cassée. Mieux vaut trois lignes vraies que six dont la moitié vide."""
    maigre = {"prix": 50000, "surface_m2": 110.0, "score_total": 25}
    assert [p for p, _ in bloc_de_faits(maigre)] == ["💶", "📐", "🛡"]
    assert bloc_de_faits({}) == []


def test_la_voiture_prend_le_relais_quand_il_n_y_a_pas_de_gare():
    """Beaucoup de biens n'ont pas de gare rattachée : la ligne d'accès ne
    doit pas disparaître pour autant, elle change de moyen."""
    sans_gare = dict(COMPLET, train=None, temps_voiture_min=150)
    lignes = dict((p, t) for p, t in bloc_de_faits(sans_gare))
    assert "🚉" not in lignes
    assert lignes["🚗"] == "Paris en 2 h 30 de route"


def test_le_singulier_est_respecte():
    """« 1 pièces » se remarque à la première lecture."""
    assert "1 pièce" in _texte(dict(COMPLET, pieces=1))
    assert "1 pièces" not in _texte(dict(COMPLET, pieces=1))


def test_les_milliers_sont_separes():
    """Comme partout ailleurs sur le site : « 1 713 m² », pas « 1713 m² ».

    Le séparateur est une espace INSÉCABLE : on passe donc par le formateur
    du projet plutôt que de recopier le format à la main, sinon le test
    échoue sur un caractère invisible sans rien dire du bloc.
    """
    texte = _texte(COMPLET)
    assert f"{_nombre(1713)} m² de terrain" in texte
    assert f"{_nombre(66000)} €" in texte
    assert "1713" not in texte, "les milliers doivent être séparés"


def test_le_bloc_apparait_sur_la_fiche_avant_la_prose():
    """Sa place fait sa valeur : après le prix, avant les paragraphes."""
    page = pages.page_annonce(COMPLET, [], "https://exemple.fr")
    assert 'class="faits-courts"' in page
    assert page.index("faits-courts") < page.index("Que disent les données")
    assert "742 €/m²" in page
