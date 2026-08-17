"""« Sans travaux » ne se devine pas : il se déclare.

Chaque cas de ce fichier est tiré du vocabulaire réel des annonces du
catalogue, relevé sur la tranche 90 000–175 000 € avant d'écrire le moindre
motif. Les pièges ne sont pas imaginés : ils sont comptés.

Le garde-fou le plus important est celui du silence. Cent cinquante-six
annonces de la tranche ne disent rien de l'état du bien ; les compter comme
« sans travaux » ferait passer la page de cinquante-trois à deux cent neuf
entrées dont les trois quarts seraient une invention.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.etat_du_bien import etat_declare, sans_travaux  # noqa: E402


def bien(texte: str) -> dict:
    return {"titre": "Maison de bourg", "description": "", "texte": texte}


# --- ce que la page doit retenir -------------------------------------------

def test_une_declaration_explicite_est_retenue():
    for phrase in ("aucun travaux à prévoir, habitable immédiatement",
                   "pas de travaux à prévoir, les charges sont faibles",
                   "maison entièrement rénovée avec soin",
                   "cette maison de ville habitable de suite avec terrasse",
                   "maison en bon état général, belle luminosité",
                   "état intérieur : en bon état, cuisine aménagée"):
        assert sans_travaux(bien(phrase)), phrase


def test_une_annonce_de_travaux_est_ecartee():
    for phrase in ("maison de ville de 57 m² à rénover avec courette",
                   "travaux à prévoir, idéal investisseur",
                   "prévoir travaux de rafraîchissement",
                   "beau projet de rénovation au cœur du Perche",
                   "des travaux de rafraîchissement et de mise aux normes"):
        assert etat_declare(bien(phrase)) == "travaux", phrase


# --- les quatre pièges relevés dans les vraies annonces ---------------------

def test_la_denegation_ne_declenche_pas_les_travaux():
    """LE piège. « pas de travaux à prévoir » contient mot pour mot le motif
    qui annonce des travaux, et dit l'inverse."""
    for phrase in ("les fenêtres sont en double vitrage. pas de travaux à prévoir",
                   "maison en bon état général, aucun gros travaux à prévoir",
                   "aucun travaux à prévoir. côté stationnement, un garage"):
        assert etat_declare(bien(phrase)) == "sans_travaux", phrase


def test_le_passe_partout_d_agence_ne_compte_pour_rien():
    """« avec ou sans travaux à prévoir » est un texte de présentation : il ne
    parle d'aucun bien en particulier, et ne doit rien affirmer."""
    assert etat_declare(bien(
        "des biens plus anciens, avec ou sans travaux à prévoir. que vous "
        "rêviez d'une maison de campagne ou d'un appartement")) == "inconnu"


def test_une_partie_en_bon_etat_ne_dit_rien_du_tout():
    """« On ne vante le gros œuvre que lorsque le second œuvre est à refaire. »"""
    for phrase in ("cave. toiture en bon état. murs et combles isolés",
                   "à l'étage 2 chambres. toiture et fenêtres en bon état",
                   "maison avec toiture en bon état"):
        assert not sans_travaux(bien(phrase)), phrase


def test_une_declaration_sur_le_tout_survit_a_une_mention_de_partie():
    """L'excès inverse : refuser dès qu'une partie est nommée écarterait des
    annonces qui décrivent aussi l'ensemble."""
    assert sans_travaux(bien(
        "toiture en bon état. l'ensemble est en bon état général : "
        "toiture récente et huisseries changées"))


def test_le_mot_etat_dans_une_adresse_ne_compte_pas():
    """« 8 rue de l'État major » — relevé trois fois dans le catalogue."""
    assert etat_declare(bien(
        "contactez-nous : les agences 8 rue de l'état major 02100 "
        "saint-quentin")) == "inconnu"


def test_le_vocabulaire_du_fonds_de_commerce_ne_compte_pas():
    """« clé en main » et « immédiatement exploitable » ne sont apparus que
    sur des commerces : ils ne disent rien de l'état d'une maison."""
    for phrase in ("reprendre une affaire saine et immédiatement exploitable",
                   "investissement locatif clé en main situé au cœur de Saône",
                   "affaire clé en main, normes PMR"):
        assert etat_declare(bien(phrase)) == "inconnu", phrase


def test_la_prime_renov_n_est_pas_un_etat():
    """Une aide publique cotoie le mot « rénov » sans rien dire du bien."""
    assert etat_declare(bien(
        "investir dans l'ancien la prime rénov' gestion des déchets")) == "inconnu"


# --- le garde-fou du silence ------------------------------------------------

def test_le_silence_reste_le_silence():
    """Cent cinquante-six annonces de la tranche ne disent rien. Les compter
    comme « sans travaux » serait inventer les trois quarts de la page."""
    assert etat_declare(bien(
        "maison de 90 m² avec 3 chambres, cuisine, séjour et jardin clos. "
        "chauffage au gaz. proche commerces.")) == "inconnu"
    assert not sans_travaux(bien(""))
    assert not sans_travaux({})


def test_l_annonce_qui_dit_les_deux_penche_du_cote_des_travaux():
    """Une salle d'eau rénovée dans une maison à rénover reste une maison à
    rénover. Dans le doute, la page ne promet rien."""
    assert etat_declare(bien(
        "salle d'eau entièrement rénovée. maison à rénover.")) == "travaux"
