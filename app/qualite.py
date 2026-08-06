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
    # Offre de CONSTRUCTION, pas un bien existant : « Maison 3 chambres +
    # Terrain à Seurre ! — Bourgogne Bâtir », 46 488 €. Ce prix est celui
    # d'un chantier, pas d'une maison ; et le bien n'existe pas encore, ce
    # qui est l'exact contraire d'un refuge prêt à habiter. Sept de ces
    # offres se sont retrouvées listées, toutes géolocalisées au siège du
    # constructeur — d'où « 7 biens à Chalon-sur-Saône » qui n'y étaient pas.
    r"|maisons?[^|]{0,40}\+ *terrain|terrains? a batir|votre (future )?maison"
    # « maison contemporaine » décrit aussi bien un modèle de constructeur
    # qu'une vraie maison à vendre : la règle écartait « Magnifique maison
    # Contemporaine », une annonce parfaitement valide de Larçay. Les pages
    # de constructeur qu'elle visait sont déjà prises par « bâtir » et
    # « votre maison ». On ne garde que « personnalisée », qui n'a de sens
    # que pour un bien qui n'existe pas encore.
    r"|maison personnalisee|projet de construction"
    r"|\bbatir\b|primo[- ]accedants?"
)

# Types de biens sans intérêt pour un refuge (repérés dans le titre).
_TYPES_EXCLUS = re.compile(
    # « appt », « appart » : abréviations courantes dans les titres d'agences
    # (« A VENDRE APPT T2 »), qui passaient à travers « appartements? ».
    r"appartements?|\bapparts?\b|\bappts?\b|studios?|\bloft\b|parkings?|\bbox\b"
    r"|emplacement de parking"
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

# On cherche un bien à ACHETER. Beaucoup d'agences publient location et vente
# sur le même gabarit de page, et dix annonces de location s'étaient glissées
# dans le catalogue : « Maison à louer Savonnières », « F3 A louer a Fécamp »…
# Sans prix de vente, elles n'ont ni écart au marché ni prix au m² — et l'une
# affichait 199 800 €, un montant récupéré ailleurs sur la page, qui la
# faisait passer pour une vraie vente.
_LOCATION_TITRE = re.compile(r"\ba louer\b|\blocation\b|\blouer\b|\bloyer\b")
# Le chemin de l'URL est le signal le plus sûr : /location/, /louer/, ou le
# gabarit « maison-a-louer-Commune.htm ». On exige les séparateurs autour du
# mot pour ne pas attraper un domaine comme « avendrealouer.fr ».
_URL_LOCATION = re.compile(
    r"/locations?/|/louer/|[/-]a-louer[-/.]|[/-]locations?[-/.]",
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
    # Location : ce n'est pas un bien à acheter.
    if _LOCATION_TITRE.search(titre) or _URL_LOCATION.search(a.get("url") or ""):
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
