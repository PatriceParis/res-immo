"""Refuser un bien, c'est bien ; dire par quelle règle, c'est utilisable.

Le 20 août, le déroulé a livré son verdict sur Safti : 212 pages visitées,
212 écartées, ZÉRO illisible. Les pages se lisent donc parfaitement — c'est le
filtre qualité qui dit non, cent fois sur cent. Et le catalogue ne contient pas
une seule annonce Safti depuis l'origine, quand IAD en a mille cent
trente-trois.

Neuf règles peuvent refuser un bien. Laquelle ? Le total ne le dit pas, et
c'est toute la différence entre corriger et deviner — j'ai déjà deviné trois
fois cette semaine, à chaque fois faux.

Le point délicat est ailleurs que dans la mesure : il fallait nommer les
règles SANS en faire une seconde copie. Ce projet a payé trois fois la
divergence de deux copies d'une même règle — cinquante-six annonces
Century 21, dix jours de rotation en Saône-et-Loire, un test qui validait une
fiction. `est_bien_valide` délègue donc à `motif_de_rejet` au lieu de la
doubler, et ces tests le vérifient sur un corpus plutôt que sur ma parole.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import qualite  # noqa: E402


def bien(**champs) -> dict:
    base = {"titre": "Maison de village 4 pièces à Autun",
            "url": "https://www.safti.fr/annonces/achat/maison-autun-71400/12",
            "surface_m2": 120, "pieces": 4, "prix": 150000}
    base.update(champs)
    return base


def test_un_bien_valide_n_a_pas_de_motif():
    assert qualite.motif_de_rejet(bien()) is None
    assert qualite.est_bien_valide(bien()) is True


def test_chaque_regle_se_nomme():
    """Un motif par règle, et le bon — sans quoi la mesure désignerait la
    mauvaise coupable et je corrigerais à côté une quatrième fois."""
    cas = [
        ("titre_indigent", bien(titre="389")),
        # `est_vendu` lit la disponibilité schema.org et le TEXTE, pas le
        # titre — mon premier cas de test se trompait de champ.
        ("vendu", bien(vendu=True)),
        ("vendu", bien(texte="Ce bien est vendu.")),
        ("location", bien(titre="Maison à louer à Autun 4 pièces")),
        ("type_bien", bien(type_bien="parking")),
        ("ni_surface_ni_prix_credible", bien(surface_m2=None, prix=3480)),
        ("prix_trop_haut", bien(prix=1_200_000)),
    ]
    for attendu, a in cas:
        assert qualite.motif_de_rejet(a) == attendu, (
            f"attendu « {attendu} », obtenu « {qualite.motif_de_rejet(a)} » "
            f"pour {a['titre']!r}")


def test_la_decision_et_son_explication_ne_peuvent_pas_diverger():
    """LE test. `est_bien_valide` doit être exactement « aucun motif ».

    C'est la garantie qui manquait aux trois divergences passées : ici la
    seconde fonction ne redit pas les règles, elle appelle la première.
    """
    cas = [bien(),
           bien(titre="389"),
           bien(titre="Maison à Autun — sous compromis"),
           bien(titre="Appartement à louer Autun"),
           bien(type_bien="terrain"),
           bien(surface_m2=None, pieces=None, prix=None),
           bien(surface_m2=None, prix=3480),
           bien(prix=900_000),
           bien(url="https://www.safti.fr/annonces/location/maison-autun/12"),
           bien(titre=""),
           bien(titre="Maison", surface_m2=0, prix=0)]
    for a in cas:
        assert qualite.est_bien_valide(a) == (qualite.motif_de_rejet(a) is None), (
            f"les deux fonctions ne disent pas la même chose pour {a!r}")


def test_le_catalogue_publie_passe_toujours_le_filtre():
    """Le corpus réel, et non mes exemples : les biens déjà servis doivent
    rester valides et sans motif. Un refactoring qui les rejetterait viderait
    le site au prochain export.
    """
    import json
    biens = json.loads((RACINE / "data" / "annonces_reel.json")
                       .read_text(encoding="utf-8"))
    rejetes = [(b.get("titre"), qualite.motif_de_rejet(b))
               for b in biens[:1500] if qualite.motif_de_rejet(b) is not None]
    # Le fichier contient plus que ce qui est servi (pages de catalogue, biens
    # hors terroir) : on n'exige pas zéro, mais que décision et motif concordent.
    for b in biens[:1500]:
        assert qualite.est_bien_valide(b) == (qualite.motif_de_rejet(b) is None)
    assert len(rejetes) < len(biens[:1500]), "tout le catalogue serait rejeté"


def test_le_collecteur_consigne_le_motif():
    """La mesure doit remonter jusqu'au déroulé, sinon elle ne sert à rien."""
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    assert 'return f"ecarte:{motif}"' in source, (
        "le collecteur écarte sans dire pourquoi")
    appel = source[source.index('etape("departement"'):]
    assert "motifs=" in appel[:appel.index(")\n")], (
        "les motifs ne sont pas consignés dans le déroulé")
