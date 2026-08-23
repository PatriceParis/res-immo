"""Tomber sur une annonce d'un département n'est pas l'avoir visité.

Le 23 août à 15 h 49, le passage mandataires a retiré 504 annonces du
catalogue, dont **461 de la seule « IAD France (71) »** — la Saône-et-Loire,
le département que l'on cherchait précisément à couvrir. Or ce passage n'a
visité que les départements 54, 37, 02 et 08, tous marqués tronqués.

L'enchaînement : le code postal lu SUR LA PAGE fait foi sur le département
deviné depuis l'adresse — une correction nécessaire, sans laquelle le site
affichait « IAD France (71) » sous une maison de Bordeaux. Il suffit donc
qu'une annonce parcourue au titre du 08 porte un code postal de Saône-et-Loire
pour qu'elle soit reclassée « IAD France (71) ».

À partir de là, cette cible EXISTE dans la récolte, avec une seule annonce. La
règle de sortie la croit donc visitée en entier, constate l'absence des 460
autres, et les retire.

C'est la faute des cent soixante-quinze annonces sous une forme nouvelle : la
cible n'était pas tronquée, elle était FORTUITE. Une cible atteinte par
ricochet n'a jamais été énumérée ; elle doit donc rejoindre les tronquées, où
la règle de sortie s'abstient.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import historique, mandataires  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecter_mandataires", RACINE / "scripts" / "collecter_mandataires.py")
COLLECTEUR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(COLLECTEUR)

SOURCE = (RACINE / "scripts" / "collecter_mandataires.py").read_text(encoding="utf-8")


def test_une_cible_atteinte_par_ricochet_est_notee():
    """LE test. La réaffectation par code postal doit alimenter l'ensemble des
    cibles fortuites, dans le même geste qui change l'étiquette d'agence."""
    corps = SOURCE[SOURCE.index("def enregistrer_une"):]
    corps = corps[:corps.index("\ndef ")]
    reaffectation = corps.index('brut["agence"] = mandataires.nom_d_agence(reseau, vrai)')
    marque = corps.find("reaffectees.add", reaffectation)
    assert marque > reaffectation, (
        "l'étiquette d'agence est changée sans que la cible soit signalée "
        "comme fortuite : la règle de sortie la croira visitée")


def test_les_cibles_fortuites_rejoignent_les_tronquees():
    """Être signalée ne suffit pas : la marque doit atteindre le journal des
    visites tronquées, seul endroit où la règle de sortie s'abstient."""
    corps = SOURCE[SOURCE.index("def collecter_un_reseau"):]
    fusion = corps.index("tronquees |= reaffectees")
    ecriture = corps.index("historique.noter_visite_tronquee(tronquees)")
    assert fusion < ecriture, (
        "les cibles fortuites sont fusionnées APRÈS l'écriture du journal : "
        "elles n'y figureront qu'au département suivant, trop tard")


def test_l_identite_fortuite_est_celle_que_la_regle_de_sortie_regarde():
    """La marque ne sert à rien si elle ne porte pas la MÊME identité que
    celle sous laquelle le bien est publié. C'est la paire (nom, domaine)."""
    bien = {"agence": mandataires.nom_d_agence(mandataires.RESEAUX["iad"], "71"),
            "agence_url": mandataires.RESEAUX["iad"]["site"]}
    marque = historique.identite(
        {"agence": mandataires.nom_d_agence(mandataires.RESEAUX["iad"], "71"),
         "agence_url": mandataires.RESEAUX["iad"]["site"]})
    assert historique.identite(bien) == marque
    # Et surtout : l'identité du département VISITÉ ne couvre pas celle du
    # département reclassé — c'est tout le problème.
    visite = historique.identite(
        {"agence": mandataires.nom_d_agence(mandataires.RESEAUX["iad"], "08"),
         "agence_url": mandataires.RESEAUX["iad"]["site"]})
    assert visite != marque, (
        "si les deux identités se confondaient, marquer le département visité "
        "aurait suffi et l'incident n'aurait pas eu lieu")


def test_la_reaffectation_hors_perimetre_n_est_pas_notee():
    """Une annonce dont le code postal la place hors de nos départements est
    écartée, pas reclassée : rien à marquer, et surtout rien à publier."""
    corps = SOURCE[SOURCE.index("def enregistrer_une"):]
    corps = corps[:corps.index("\ndef ")]
    hors = corps.index('return "ecarte:hors_perimetre"')
    marque = corps.index("reaffectees.add")
    assert hors < marque, (
        "une annonce hors périmètre ne doit pas créer de cible fortuite")
