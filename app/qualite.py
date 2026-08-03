"""Filtre de qualité des annonces — pour une base fiable.

On ne garde que de **vrais logements de type « refuge »** (maisons, longères,
fermes, moulins, propriétés…) et on écarte tout le bruit qui polluait le score :

- ce qui n'est **pas une annonce** : articles de blog (« vendre sa maison,
  quel mandat choisir ? »), pages catalogue (« nos biens à vendre »), pages
  d'agence (contact, estimation, mentions légales) ;
- ce qui n'a **aucun intérêt refuge** : appartements, studios, parkings,
  terrains nus, locaux commerciaux, programmes neufs, viager.

Un appartement n'a ni terrain, ni cave, ni autonomie possible : par
construction il ne peut pas être un refuge résilient.
"""

from __future__ import annotations

import re

from .scoring import normaliser

# Titres qui trahissent une page qui n'est PAS une annonce individuelle.
_NON_ANNONCE = re.compile(
    r"nos biens|biens a vendre|\bannonces\b|resultats?|\brecherche\b|\bblog\b"
    r"|actualit|\bconseils?\b|\bguides?\b|quel mandat|estimation|qui sommes"
    r"|contactez|mentions legales|notre agence|vendre (sa|votre|ma|leur) "
    r"|comment (vendre|acheter|choisir|estimer)|pourquoi (vendre|choisir|faire)"
)

# Types de biens sans intérêt pour un refuge (repérés dans le titre).
_TYPES_EXCLUS = re.compile(
    r"appartements?|studios?|\bloft\b|parkings?|\bbox\b|emplacement de parking"
    r"|local commercial|locaux commerciaux|fonds de commerce|murs commerciaux"
    r"|immeuble de rapport|terrains? (a batir|constructibles?|nus?)"
    r"|programme neuf|investissement locatif|viager"
)

# Types de biens acceptés (habitables, avec potentiel refuge).
TYPES_REFUGE = {
    "longère", "corps de ferme", "fermette", "moulin", "château", "manoir",
    "propriété", "pavillon", "maison", "maison de campagne", "maison de bourg",
}


def est_bien_valide(a: dict) -> bool:
    """True uniquement pour l'annonce d'un vrai logement de type refuge."""
    titre = normaliser(a.get("titre") or "")
    if not titre:
        return False
    if _NON_ANNONCE.search(titre) or _TYPES_EXCLUS.search(titre):
        return False
    if (a.get("type_bien") or "maison") not in TYPES_REFUGE:
        return False
    # Un vrai logement a une surface habitable (ou au moins un prix ET des pièces) :
    # les pages de blog / catalogue n'en ont pas.
    if not a.get("surface_m2") and not (a.get("prix") and a.get("pieces")):
        return False
    return True
