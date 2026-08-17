"""Le département deviné depuis l'adresse mentait une fois sur deux.

Mesuré sur le catalogue : 572 annonces IAD sur 1 023 portaient une étiquette
de département fausse. Sur les 474 dites « IAD France (71) », 283 étaient en
réalité en Gironde, en Loire-Atlantique ou en Seine-Saint-Denis — le site
affichait « IAD France (71) » sous une maison de Bordeaux.

Deux causes distinctes, deux corrections distinctes :

- **la sous-chaîne.** Le nom de commune était cherché sans frontière :
  « plai*sance*-du-touch » devenait Sancé (71), « pont*chateau* » devenait
  Château (71). Corrigé avant toute visite, ce qui économise aussi les pages
  téléchargées pour rien ;
- **l'homonyme.** Péronne est en Saône-et-Loire ET dans la Somme ;
  Sainte-Hélène en Saône-et-Loire ET en Gironde. Aucune frontière ne peut les
  départager : seul le code postal de la PAGE tranche, donc après lecture.

Ces tests tiennent les deux sens. Resserrer devait supprimer les faux
rattachements sans perdre les vrais — une commune légitime doit continuer de
passer.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import mandataires  # noqa: E402

INDEX = mandataires.index_des_communes(
    {"71": ["Sancé", "Château", "Péronne", "Sainte-Hélène", "Givry", "Cluny",
            "Saint-Bérain-sur-Dheune"]})


def adresse(fin: str) -> str:
    return f"https://www.iadfrance.fr/annonce/maison-vente-4-pieces-{fin}/r1"


def test_un_nom_de_commune_noye_dans_un_mot_plus_long_ne_compte_plus():
    """LE cas. « plaisance » contient « sance », « pontchateau » contient
    « chateau » — et rien ne le signalait."""
    assert mandataires.commune_de_l_adresse(adresse("plaisance-du-touch-80m2"), INDEX) is None
    assert mandataires.commune_de_l_adresse(adresse("pontchateau-118m2"), INDEX) is None


def test_une_vraie_commune_passe_toujours():
    """L'excès inverse : resserrer ne doit pas fermer la porte aux bonnes."""
    assert mandataires.commune_de_l_adresse(adresse("givry-90m2"), INDEX) == ("Givry", "71")
    assert mandataires.commune_de_l_adresse(
        adresse("saint-berain-sur-dheune-245m2"), INDEX) == ("Saint-Bérain-sur-Dheune", "71")


def test_une_commune_en_bord_d_adresse_est_reconnue():
    """Les bords comptent comme des frontières, sinon on perdrait les
    adresses qui commencent ou finissent par la commune."""
    index = mandataires.index_des_communes({"71": ["Cluny"]})
    assert mandataires.commune_de_l_adresse("https://x.fr/annonce/cluny", index)
    assert mandataires.commune_de_l_adresse("https://x.fr/annonce/cluny-maison", index)


def test_le_code_postal_donne_le_departement():
    assert mandataires.departement_du_code_postal("33480") == "33"
    assert mandataires.departement_du_code_postal(" 71100 ") == "71"


def test_un_code_postal_douteux_ne_produit_pas_de_departement():
    """Tronquer une valeur douteuse fabriquerait un département inventé, ce
    qui est pire qu'un département inconnu : l'étiquette resterait fausse mais
    aurait l'air vérifiée."""
    for douteux in (None, "", "710", "7110", "711000", "71 10", "abcde", 71100):
        if douteux == 71100:
            continue
        assert mandataires.departement_du_code_postal(douteux) is None, douteux


def test_un_code_postal_numerique_est_accepte():
    """Il arrive que l'extraction rende un entier plutôt qu'une chaîne."""
    assert mandataires.departement_du_code_postal(71100) == "71"
