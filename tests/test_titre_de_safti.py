"""Une règle anti-catalogue refusait toutes les annonces d'un réseau entier.

Safti est branché depuis des semaines et n'a jamais versé UNE seule ligne au
catalogue, quand IAD en compte plus de mille deux cents. Cinq mesures
successives ont été nécessaires pour le comprendre, chacune répondant à la
question posée par la précédente :

1. le passage mandataires ne rapportait rien → il mourait avant le premier
   réseau (déroulé consigné à chaque étape) ;
2. il allait jusqu'au bout → Safti visitait 212 pages et n'en gardait aucune ;
3. `illisible: 0` → les pages se lisaient, c'était le filtre qui refusait ;
4. `titre_hors_cible` → l'une des neuf règles, mais laquelle des soixante
   alternatives ?
5. `titre_hors_cible:vente de` + un exemple de titre → celle-ci, et à tort.

Le titre en cause :

    « Vente de maison 7 pièces à Abreschviller 57560 : 150m², prix 144 000 €.
      Réf : 1650646 »

C'est une annonce parfaitement individuelle — une maison, une commune, un
prix, une référence. La règle visait « Vente de maisonS et villas | Agence du
Centre », une page catalogue ; écrite sans exiger le pluriel, elle emportait
le gabarit de titre de Safti, c'est-à-dire toutes ses annonces.

La leçon tient en une phrase : une règle de rejet écrite trop large ne
produit pas d'erreur visible, elle produit un SILENCE — et un silence
ressemble à une absence.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import qualite  # noqa: E402


def annonce(titre: str, **champs) -> dict:
    base = {"titre": titre, "surface_m2": 150, "pieces": 7, "prix": 144000,
            "url": "https://www.safti.fr/annonces/achat/maison-abreschviller/1"}
    base.update(champs)
    return base


TITRES_SAFTI = [
    "Vente de maison 7 pièces à Abreschviller 57560 : 150m², prix 144 000 €. Réf : 1650646",
    "Vente de maison 1 pièce à Alligny-Cosne 58200 : 60m², prix 74 000 €. Réf : 1675787",
    "Vente de maison 8 pièces à Abancourt 59268 : 221m², prix 408 000 €. Réf : 1695843",
    "Vente de maison 6 pièces à Ablain-Saint-Nazaire 62153 : 109m², prix 214 000 €. Réf : 1679632",
]


def test_les_annonces_de_safti_sont_acceptees():
    """LE test. Ces quatre titres sont relevés tels quels dans le déroulé du
    passage du 22 août — ce ne sont pas des exemples que j'ai inventés."""
    for titre in TITRES_SAFTI:
        motif = qualite.motif_de_rejet(annonce(titre))
        assert motif is None, (
            f"toujours refusée par « {motif} » : {titre[:60]}…")


def test_les_pages_catalogue_restent_refusees():
    """La raison d'être de la règle ne doit pas disparaître avec le correctif :
    ces gabarits-là faisaient passer la première vignette pour un bien."""
    for titre in ("Vente de maisons et villas | Agence du Centre",
                  "Vente d'appartements neufs | Immo Plus",
                  "Vente de biens immobiliers à Tours",
                  "Vente de terrains à bâtir | Foncier 41",
                  "Biens immobiliers à vendre | Berry Immobilier",
                  "177 Maisons à vendre"):
        assert qualite.motif_de_rejet(annonce(titre)) is not None, (
            f"page catalogue désormais acceptée : {titre!r}")


def test_le_pluriel_est_ce_qui_tranche():
    """Singulier et pluriel, tout le reste égal : c'est la seule différence
    qui doit compter, et c'est celle que la règle ignorait."""
    assert qualite.motif_de_rejet(annonce("Vente de maison à Autun")) is None
    assert qualite.motif_de_rejet(annonce("Vente de maisons à Autun")) is not None


def test_une_page_qui_enumere_des_references_reste_prise():
    """Le garde-fou qui subsiste si un catalogue se titrait au singulier :
    une page qui énumère plusieurs références décrit plusieurs biens."""
    catalogue = annonce("Vente de maison à Autun",
                        texte=" ".join(f"Réf : {n}" for n in range(1000, 1020)))
    assert qualite.motif_de_rejet(catalogue) == "page_catalogue"
