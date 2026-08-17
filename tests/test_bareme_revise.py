"""Deux corrections que la littérature de résilience impose au barème.

**La cave n'est un atout que si l'eau ne l'atteint pas.** Elle était bonifiée
sans condition — neuf points, l'atout signature du site. Or en zone inondable
elle cesse d'être un cellier pour devenir le point faible du bâti : la nappe en
charge pousse sur les parois enterrées, décolle les étanchéités, et peut
soulever la dalle. On récompensait une vulnérabilité, et précisément sur les
biens bon marché de fond de vallée.

**Le poêle de masse n'est pas un poêle à bois de plus.** Il restitue par
rayonnement pendant douze à vingt-quatre heures après une flambée d'une heure,
ne demande ni ventilateur ni carte électronique — donc fonctionne sans
électricité — et porte souvent un four. C'est le seul chauffage qui tienne une
panne de réseau en plein hiver. Il se nomme dans les annonces : il peut donc
être distingué.

Ces tests tiennent les deux sens : ne plus récompenser à l'aveugle, sans pour
autant effacer un atout réel sur la foi d'une donnée communale.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import scoring  # noqa: E402

CAVE = {"cave": True}


def test_une_cave_hors_zone_inondable_garde_tout_son_bonus():
    """L'excès inverse à éviter : la cave reste l'atout signature du site."""
    assert scoring._pilier_abri(CAVE, {}) == 9
    assert scoring._pilier_abri(CAVE, None) == 9


def test_une_cave_en_zone_inondable_ne_rapporte_plus_rien():
    """LE cas. Le bien est exposé : la cave est un risque, pas un atout."""
    assert scoring._pilier_abri(CAVE, {"inondation": True}) == 0


def test_une_commune_inondable_tempere_sans_trancher():
    """Notre donnée d'inondation vaut pour la COMMUNE, pas pour la parcelle.
    L'annuler sur cette base seule condamnerait des caves parfaitement sèches
    situées sur un point haut."""
    assert scoring._pilier_abri(CAVE, {"inondation_commune": True}) == 4


def test_le_poele_de_masse_se_reconnait_dans_une_annonce():
    for phrase in ("magnifique poêle de masse en stéatite",
                   "poêle à inertie de 900 kg",
                   "poêle à accumulation maçonné",
                   "chauffage principal : pierre ollaire"):
        assert scoring.extraire_criteres("", phrase)["poele_de_masse"], phrase


def test_un_poele_ordinaire_n_est_pas_pris_pour_un_poele_de_masse():
    """L'erreur coûteuse serait l'inverse : compter tout poêle comme un poêle
    de masse ferait croire à une autonomie hivernale qui n'existe pas."""
    criteres = scoring.extraire_criteres("", "poêle à bois et insert cheminée")
    assert criteres["bois"] and not criteres["poele_de_masse"]


def test_le_poele_de_masse_vaut_plus_qu_un_poele_ordinaire():
    masse = scoring._pilier_energie({"poele_de_masse": True, "bois": True}, None)
    ordinaire = scoring._pilier_energie({"bois": True}, None)
    assert masse > ordinaire
    # ...mais les points ne se cumulent pas : un poêle de masse EST un poêle à
    # bois, et le compter deux fois gonflerait le pilier sans raison.
    assert masse == scoring._pilier_energie({"poele_de_masse": True}, None)


def test_le_score_complet_tient_compte_des_deux():
    """Le bout de la chaîne : les risques doivent bien arriver jusqu'au pilier
    abri, sinon la correction ne sert à rien en production."""
    bien = {"features": CAVE, "risques": {"inondation": True}}
    sec = {"features": CAVE, "risques": {}}
    assert (scoring.calculer_score(bien)["piliers"]["abri"]["points"]
            < scoring.calculer_score(sec)["piliers"]["abri"]["points"])
