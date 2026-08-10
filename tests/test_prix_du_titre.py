"""Le prix écrit dans le titre ne doit pas attendre la prochaine collecte.

L'utilisateur a signalé des fiches « Prix sur demande » dont le titre
annonçait pourtant le montant : « MAISON - ECUISSES - 79.000,00 EUROS ».
La cause — le point français lu comme une décimale — a été corrigée dans
l'extraction. Mais un correctif d'extraction ne vaut que pour ce qui est
recollecté, et les six annonces fautives dataient de cinq jours : elles
seraient restées sans prix jusqu'au prochain passage de leur agence.

D'où une relecture au CHARGEMENT, qui répare le catalogue déjà publié. Ces
tests protègent les deux faces de cette relecture : ce qu'elle doit
retrouver, et surtout ce qu'elle ne doit pas ressusciter.
"""

from app.chargement import preparer_annonce
from app.extraction import prix_dans, prix_m2_credible


def test_le_montant_a_la_francaise_est_lu_dans_un_texte_libre():
    """Les trois écritures rencontrées chez NC Immo, dont deux sans le « € »."""
    assert prix_dans("MAISON - ECUISSES - 79.000,00 EUROS -REF 107") == 79000
    assert prix_dans("MAISON - MONTCHANIN - 175.000 EUROS - REF 119") == 175000
    assert prix_dans("MAISON - ST SYMPHORIEN - 40.000,00 € Référence 58") == 40000


def test_un_numero_de_reference_n_est_pas_un_prix():
    """Sous le plancher, un montant suivi d'un « € » n'achète pas de maison."""
    assert prix_dans("Box fermé, charges 6 000 € — Réf 58") is None
    assert prix_dans("Erreur de saisie : 9 000 000 000 €") is None


def test_une_annonce_sans_prix_le_retrouve_dans_son_titre():
    """LE cas signalé. Avant la relecture au chargement, ce bien restait
    « Prix sur demande » alors que son titre portait le montant."""
    prepare = preparer_annonce({
        "titre": "MAISON - ECUISSES - 79.000,00 EUROS -REF 107 - NC immo",
        "prix": None, "surface_m2": 105, "code_postal": "71210",
    })
    assert prepare["prix"] == 79000


def test_la_relecture_ne_touche_pas_a_un_prix_deja_connu():
    """Le titre d'une annonce contient souvent un AUTRE montant que le sien
    (honoraires, prix d'un bien voisin mis en avant). La relecture ne se
    déclenche que sur l'absence de prix, jamais pour corriger."""
    prepare = preparer_annonce({
        "titre": "Longère 250.000,00 € — honoraires 12.000 €",
        "prix": 245000, "surface_m2": 140, "code_postal": "61130",
    })
    assert prepare["prix"] == 245000


def test_la_relecture_ne_ressuscite_pas_ce_que_l_extraction_a_ecarte():
    """Le piège de cette réparation.

    Quand le prix au m² est absurde et que la surface vient du titre,
    l'extraction efface le PRIX — délibérément. Rien ne distingue ensuite,
    dans les données, « prix jamais trouvé » de « prix rejeté ». Relire le
    titre sans refaire le même contrôle rendrait donc à l'affichage les
    valeurs que l'extraction venait de condamner : ici 40 000 € pour 220 m²,
    soit 181 €/m², sous le plancher de vraisemblance.
    """
    prepare = preparer_annonce({
        "titre": "Maison de maître 220 m² - 40.000,00 €",
        "prix": None, "surface_m2": 220, "code_postal": "61130",
    })
    assert prepare["prix"] is None


def test_sans_surface_le_prix_du_titre_est_accepte():
    """Le contrôle du prix au m² ne peut pas trancher sans surface : il
    s'abstient plutôt que de rejeter par principe."""
    assert prix_m2_credible(79000, None) is True
    prepare = preparer_annonce({
        "titre": "MAISON - MONTCHANIN - 175.000 EUROS - REF 119",
        "prix": None, "pieces": 4, "code_postal": "71210",
    })
    assert prepare["prix"] == 175000
