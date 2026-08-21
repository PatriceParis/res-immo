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
    # Page catalogue titrée par son compte : « 177 Maisons à vendre ». Le
    # pluriel et le nombre en tête la distinguent d'une vraie annonce, qui dit
    # « Maison à vendre à Barentin » — au singulier, sans décompte.
    r"|^\d+ (?:maisons|biens|annonces|proprietes|appartements|logements)\b"
    r"|\bmaisons a vendre\b"
    # Autres gabarits de page catalogue rencontrés : « Vente de maisons et
    # villas | Agence du Centre », « Biens immobiliers à vendre | Berry
    # Immobilier ». L'extraction y prend le prix et la surface de la première
    # vignette, ce qui les faisait passer pour un bien à part entière.
    r"|^vente (?:de|d')|^biens immobiliers\b|\bbiens immobiliers a vendre\b"
    r"|\bvillas et maisons\b|\bmaisons et villas\b"
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
    r"|commerces?|bureaux|immeubles?|autres?|viagers?|neuf"
    # Page de glossaire : /lexique/biens-immobiliers/ décrivait le mot, pas
    # un bien — et repartait avec le prix lu ailleurs sur la page.
    r"|lexique|glossaire|definitions?)/",
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

# Au-delà, ce n'est plus le projet. L'application cherche un refuge habitable
# et résilient, pas un patrimoine : cent treize biens du catalogue dépassaient
# ce seuil — jusqu'à 4 494 000 € — et tenaient des places que personne ne vient
# chercher ici.
#
# Le plafond est posé ICI, et nulle part ailleurs : c'est le seul point que
# traversent les DEUX chemins, la collecte qui cesse d'en ramener et le
# chargement qui écarte ceux déjà en base. Une copie posée d'un seul côté
# laisserait le fichier et l'écran se contredire — c'est arrivé aux photos.
PRIX_MAXI = 700000

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


# Une annonce porte UNE référence. Une page qui en énumère plusieurs décrit
# plusieurs biens : c'est un catalogue, quoi qu'en dise son titre.
#
# Les gabarits de page catalogue se reconnaissaient jusqu'ici à leur titre
# (« 177 Maisons à vendre », « Nos biens »). Ceux qui empruntent le titre de
# leur premier bien passaient au travers, et le résultat est une annonce
# FANTÔME : la page « /vente/maison » de l'Agence Saint-Joseph était publiée
# comme une maison à 93 000 €, avec le titre et le prix de la première carte
# mais une surface de 140 m² qui n'appartient à aucune — la première en fait
# 105. Les autres biens de la page, dont un à 108 000 €, n'existaient nulle
# part ailleurs : un utilisateur les a cherchés en vain sur le site.
#
# Le seuil est à TROIS et non à deux, et c'est mesuré : à deux, on écarterait
# aussi trois vraies fiches d'Antony Vesque, dont chaque page porte la
# référence de l'agence en plus de celle du bien. À trois, les sept pages
# retenues sur le catalogue entier sont toutes d'authentiques listes.
_REFERENCE = re.compile(r"r[ée]f[ée]?r?e?n?c?e?\.?\s*:?\s*(\d{3,6})", re.IGNORECASE)
REFERENCES_MAXI = 2


def enumere_plusieurs_biens(a: dict) -> bool:
    """Vrai si le texte de la page cite plus de références qu'un bien n'en a."""
    return len(set(_REFERENCE.findall(a.get("texte") or ""))) > REFERENCES_MAXI


def motif_de_rejet(a: dict) -> str | None:
    """Le nom de la première règle qui refuse ce bien, ou None s'il passe.

    Une seule fabrique pour la décision ET pour son explication.
    `est_bien_valide` délègue ici : écrire à côté une seconde fonction qui
    « refait les mêmes tests pour dire lesquels » serait la faute que ce projet
    a déjà payée trois fois — deux copies d'une règle finissent toujours par
    diverger, et cela a coûté cinquante-six annonces Century 21, dix jours de
    rotation en Saône-et-Loire, et un test qui validait une fiction.

    L'utilité immédiate : le 20 août, Safti a visité 212 pages, toutes
    écartées, zéro illisible. Les pages se lisent donc parfaitement et c'est ce
    filtre qui dit non, cent fois sur cent — le catalogue ne contient pas une
    seule annonce Safti depuis l'origine. Savoir LAQUELLE des neuf règles
    refuse fait toute la différence entre corriger et deviner.
    """
    titre = normaliser(a.get("titre") or "")
    # Titre vide ou indigent (numéro de référence seul, « 389 ») : inexploitable.
    if len(_LETTRES.findall(titre)) < 5:
        return "titre_indigent"
    # Déjà vendu : l'annonce traîne en ligne, mais on ne la propose pas.
    if est_vendu(a):
        return "vendu"
    # On nomme le FRAGMENT qui a déclenché le refus, et pas seulement la règle.
    # Ces deux expressions comptent une soixantaine d'alternatives : savoir que
    # « le titre est hors cible » ne dit rien d'exploitable quand 217 pages
    # Safti sur 257 tombent ici et aucune page IAD. Le fragment, lui, désigne
    # la coupable — et la liste des alternatives étant fixe, la cardinalité du
    # compteur reste bornée.
    hors_cible = _NON_ANNONCE.search(titre) or _TYPES_EXCLUS.search(titre)
    if hors_cible:
        return f"titre_hors_cible:{hors_cible.group(0)}"
    # Page catalogue qui a pris le titre de son premier bien : le titre ne la
    # trahit pas, l'énumération de ses références, si.
    if enumere_plusieurs_biens(a):
        return "page_catalogue"
    # Location : ce n'est pas un bien à acheter.
    if _LOCATION_TITRE.search(titre) or _URL_LOCATION.search(a.get("url") or ""):
        return "location"
    # Type porté par l'URL (…/terrain/…, …/autre/…) : il prime sur le titre.
    if _URL_TYPE_EXCLU.search(a.get("url") or ""):
        return "url_type_exclu"
    if (a.get("type_bien") or "maison") not in TYPES_REFUGE:
        return "type_bien"
    # Un vrai logement a une surface habitable, ou au minimum un prix crédible
    # (≥ 15 000 €) ET un nombre de pièces. Les pages de blog / catalogue n'ont
    # pas de surface, et un « prix » de 3 480 € trahit une extraction ratée.
    prix = a.get("prix")
    if not a.get("surface_m2") and not (prix and prix >= PRIX_MINI and a.get("pieces")):
        return "ni_surface_ni_prix_credible"
    # Hors projet par le haut. Le `prix and` n'est pas une précaution de style :
    # cent dix-huit biens servis n'ont pas de prix lisible, et les comparer à un
    # plafond les effacerait tous d'un coup.
    if prix and prix > PRIX_MAXI:
        return "prix_trop_haut"
    return None


def est_bien_valide(a: dict) -> bool:
    """True uniquement pour l'annonce d'un vrai logement de type refuge."""
    return motif_de_rejet(a) is None
