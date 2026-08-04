"""Situer un prix par rapport à son secteur.

150 000 € est cher dans la Nièvre et donné dans l'Oise : seul l'écart au
marché local est parlant — et c'est ce qu'aucun portail n'affiche.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.marche import (  # noqa: E402
    ECHANTILLON_MINI, libelle_ecart, medianes_par_secteur, prix_m2, situer,
)


def _bien(dept, prix, surface):
    return {"departement": dept, "prix": prix, "surface_m2": surface}


def test_prix_m2():
    assert prix_m2(_bien("60", 200000, 100)) == 2000
    assert prix_m2(_bien("60", None, 100)) is None
    assert prix_m2(_bien("60", 200000, 0)) is None


def test_mediane_ignore_les_secteurs_trop_maigres():
    biens = [_bien("60", 200000, 100) for _ in range(ECHANTILLON_MINI)]
    biens += [_bien("61", 300000, 100)]          # un seul bien : non mesurable
    med = medianes_par_secteur(biens)
    assert med["60"] == 2000
    assert "61" not in med


def test_la_mediane_resiste_a_un_bien_hors_norme():
    """Une propriété à 9 000 €/m² ne doit pas déplacer la référence."""
    biens = [_bien("60", 200000, 100) for _ in range(4)] + [_bien("60", 900000, 100)]
    assert medianes_par_secteur(biens)["60"] == 2000     # médiane, pas moyenne


def test_situer_un_bien_sous_le_marche():
    med = {"60": 2000}
    b = situer(_bien("60", 150000, 100), med)            # 1 500 €/m²
    assert b["prix_m2"] == 1500
    assert b["prix_m2_secteur"] == 2000
    assert b["ecart_marche_pct"] == -25
    assert "25 % sous le prix du secteur" == libelle_ecart(b)


def test_un_ecart_faible_n_est_pas_annonce():
    """« 3 % sous le secteur » donnerait une fausse impression de précision."""
    b = situer(_bien("60", 194000, 100), {"60": 2000})   # −3 %
    assert libelle_ecart(b) == ""


def test_sans_reference_pas_de_comparaison():
    b = situer(_bien("99", 150000, 100), {"60": 2000})
    assert "ecart_marche_pct" not in b
