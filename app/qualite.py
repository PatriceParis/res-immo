"""Filtre de qualité des annonces — pour une base fiable.

On ne garde que de **vrais logements de type « refuge »** (maisons, longères,
fermes, moulins, propriétés…) et on écarte tout le bruit qui polluait le score :

- ce qui n'est **pas une annonce** : articles de blog (« vendre sa maison,
  quel mandat choisir ? »), pages catalogue (« nos biens à vendre »), pages
  d'agence (contact, estimation, mentions légales) ;
- ce qui n'a **aucun intérêt refuge** : appartements, studios, parkings,
  terrains nus, locaux commerciaux, programmes neufs, viager ;
- ce qui n'est **plus achetable** : biens vendus ou sous compromis, dont
  l'annonce reste souvent en ligne des mois après la vente.

Un appartement n'a ni terrain, ni cave, ni autonomie possible : par
construction il ne peut pas être un refuge résilient.
"""

from __future__ import annotations

import re

from .scoring import normaliser

# Titres qui trahissent une page qui n'est PAS une annonce individuelle.
_NON_ANNONCE = re.compile(
    r"nos biens|biens a vendre|\bannonces\b|resultats?|\brecherche\b|\bsearch\b"
    r"|\bblog\b|actualit|\bconseils?\b|\bguides?\b|quel mandat|estimation"
    r"|qui sommes|contactez|mentions legales|notre agence|vendre (sa|votre|ma|leur) "
    r"|comment (vendre|acheter|choisir|estimer)|pourquoi (vendre|choisir|faire)"
    r"|^a vendre\s*\|"          # titre-gabarit « A vendre | Agence » (pas un bien)
    # Page d'accueil d'agence : « Untel Immobilier - Achat & Vente Immobilier »
    r"|achat (&|et) vente|vente (&|et) location|gestion locative"
    # Vitrine de constructeur : « Maisons France Confort : 7 Modèles et Prix »
    r"|modeles? et prix|nos modeles|faire construire|maisons? neuves?"
    r"|constructeur"
)

# Types de biens sans intérêt pour un refuge (repérés dans le titre).
_TYPES_EXCLUS = re.compile(
    r"appartements?|studios?|\bloft\b|parkings?|\bbox\b|emplacement de parking"
    r"|local (commercial|professionnel|d'activite)|locaux (commerciaux|professionnels)"
    r"|\bbureaux\b|entrepots?|fonds de commerce|murs commerciaux"
    r"|immeuble de rapport|terrains? (a batir|constructibles?|nus?)"
    r"|^terrains?\b|vente de terrains?|batiment d'activite|hangar agricole"
    r"|programme neuf|investissement locatif|viager"
)

# Le chemin de l'URL porte souvent le VRAI type du bien (…/vente/ville/terrain/…)
# — signal bien plus fiable que le titre, souvent tronqué ou commercial.
_URL_TYPE_EXCLU = re.compile(
    r"/(terrains?|appartements?|studios?|parkings?|garages?|box|locaux|local"
    r"|commerces?|bureaux|immeubles?|autres?|viagers?|neuf)/",
    re.IGNORECASE,
)

# Types de biens acceptés (habitables, avec potentiel refuge).
TYPES_REFUGE = {
    "longère", "corps de ferme", "fermette", "moulin", "château", "manoir",
    "propriété", "pavillon", "maison", "maison de campagne", "maison de bourg",
}

# Un titre exploitable contient un minimum de lettres (écarte « 389 », « 9 »…).
_LETTRES = re.compile(r"[a-z]")
# En-deçà, un « prix » trahit une extraction ratée (référence, n° de téléphone).
PRIX_MINI = 15000

# Bien déjà vendu / sous compromis : l'annonce reste en ligne mais n'est plus
# achetable. Le pastille « Vendu » du site est au SINGULIER ; le menu de
# navigation, lui, dit « Biens vendus » au PLURIEL — que \b...\b ne capture pas.
# On écarte aussi les tournures « vendu avec / séparément / meublé » (descriptif).
_VENDU = re.compile(
    r"\bvendue?\b(?!\s+(?:avec|separement|separe|meuble|loue|libre|sur plan))"
    r"|sous (?:compromis|offre|promesse)|compromis (?:de vente )?signe"
    r"|n'est plus disponible|bien indisponible|affaire (?:conclue|realisee)"
)


def est_vendu(a: dict) -> bool:
    """True si l'annonce signale un bien vendu ou sous compromis."""
    if a.get("vendu"):                     # disponibilité schema.org (fiable)
        return True
    texte = normaliser(f"{a.get('texte') or ''} {a.get('description') or ''}")
    return bool(_VENDU.search(texte))


def est_bien_valide(a: dict) -> bool:
    """True uniquement pour l'annonce d'un vrai logement de type refuge."""
    titre = normaliser(a.get("titre") or "")
    # Titre vide ou indigent (numéro de référence seul, « 389 ») : inexploitable.
    if len(_LETTRES.findall(titre)) < 5:
        return False
    # Déjà vendu : l'annonce traîne en ligne, mais on ne la propose pas.
    if est_vendu(a):
        return False
    if _NON_ANNONCE.search(titre) or _TYPES_EXCLUS.search(titre):
        return False
    # Type porté par l'URL (…/terrain/…, …/autre/…) : il prime sur le titre.
    if _URL_TYPE_EXCLU.search(a.get("url") or ""):
        return False
    if (a.get("type_bien") or "maison") not in TYPES_REFUGE:
        return False
    # Un vrai logement a une surface habitable, ou au minimum un prix crédible
    # (≥ 15 000 €) ET un nombre de pièces. Les pages de blog / catalogue n'ont
    # pas de surface, et un « prix » de 3 480 € trahit une extraction ratée.
    prix = a.get("prix")
    if not a.get("surface_m2") and not (prix and prix >= PRIX_MINI and a.get("pieces")):
        return False
    return True
