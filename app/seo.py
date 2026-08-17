"""Rendre le catalogue lisible par les moteurs — et par les IA.

L'état des lieux, avant d'écrire une ligne
------------------------------------------
Refuge Immo est une page unique rendue en JavaScript. Un robot qui la
demande reçoit une coquille : un `<title>`, deux `<link>`, et un `<div>`
vide que seul le navigateur remplit. Il n'existait donc :

    • aucune URL par annonce — tout se joue dans une fenêtre modale ;
    • aucune page par terroir, alors que c'est là qu'est la recherche
      (« maison à vendre en Normandie » se cherche, « res-immo » non) ;
    • ni robots.txt, ni sitemap.xml, ni description, ni canonique ;
    • aucune donnée structurée.

Google sait exécuter du JavaScript, au prix d'un second passage et d'un
délai. **Les robots d'IA, non.** GPTBot, ClaudeBot, PerplexityBot et
CCBot lisent le HTML tel qu'il arrive. Pour eux, le site est vide — et
c'est précisément l'indexation qui nous intéresse le plus, puisqu'un
acheteur qui demande « où acheter une maison résiliente près de Paris »
pose aujourd'hui la question à un assistant.

Ce module produit donc du HTML servi par le serveur, pour trois familles
de pages, plus les trois fichiers que réclament les robots.

Ce qu'on publie, et ce qu'on ne publie pas
------------------------------------------
Nos annonces viennent des sites d'agences. Recopier leur texte de vente
— trois mille caractères en moyenne — serait du contenu dupliqué : mauvais
pour le référencement, et discutable vis-à-vis des agences.

Les pages d'annonce ne reprennent donc que **des faits** (prix, surface,
pièces, terrain, commune, DPE), qui n'appartiennent à personne, et
**notre propre analyse** : score de résilience et son détail, risques
recensés par Géorisques, altitude, temps de trajet vers Paris, gare la
plus proche. C'est notre apport, et c'est ce qui justifie que la page
existe. Chaque page renvoie visiblement vers l'annonce d'origine.
"""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import date
from urllib.parse import quote

SITE = "https://res-immo.vercel.app"
NOM = "Refuge Immo"

# La marque, définie une seule fois et partagée par l'interface et les pages
# servies. L'emoji ⛰️ qui tenait ce rôle avait trois défauts : il appartient à
# tout le monde, son rendu change d'un système à l'autre — le petit drapeau
# bleu d'Apple n'est pas la montagne d'Android — et il ne dit rien du projet.
#
# Le dessin : un toit OUVERT, deux montants qui ne se referment pas — un abri,
# pas une boîte — et une feuille centrée là où serait la porte. L'abri protège
# quelque chose de vivant : c'est tout le propos, et cela se lit à seize
# pixels comme à quarante-huit.
def marque_svg(trait: str = "#f2efe6", feuille: str = "#8fb488") -> str:
    """Le pictogramme seul, sans dimension ni fond : à poser où l'on veut."""
    return (
        f'<path d="M7.5 25.5 L24 11 L40.5 25.5" fill="none" stroke="{trait}" '
        f'stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M11.5 28.5 L11.5 40 M36.5 28.5 L36.5 40" stroke="{trait}" '
        f'stroke-width="3.6" stroke-linecap="round"/>'
        f'<path d="M24 40.5 C 18 36 17 27 24 22 C 31 27 30 36 24 40.5 Z" '
        f'fill="{feuille}"/>'
        f'<path d="M24 40.5 L24 27" stroke="{trait}" stroke-width="1.7" '
        f'stroke-linecap="round" opacity=".45"/>')


def logo(taille: int = 30, trait: str = "#f2efe6",
         feuille: str = "#8fb488") -> str:
    return (f'<svg class="logo" width="{taille}" height="{taille}" '
            f'viewBox="0 0 48 48" role="img" aria-label="Refuge Immo" '
            f'focusable="false">{marque_svg(trait, feuille)}</svg>')


def favicon() -> str:
    """L'icône d'onglet, en URL de données.

    Sur un fond carré à la couleur de la marque, et non en tracé nu : un
    onglet peut être clair ou sombre, et un dessin sans fond disparaît dans
    l'un des deux cas.
    """
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
           '<rect width="48" height="48" rx="10" fill="#1b4332"/>'
           + marque_svg() + '</svg>')
    return "data:image/svg+xml," + quote(svg, safe="")


# Robots d'IA explicitement accueillis. Les nommer n'est pas cosmétique :
# plusieurs n'explorent que si une règle les vise, et un `Disallow` par
# défaut ailleurs les écarterait sans qu'on s'en aperçoive.
ROBOTS_IA = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
             "Claude-User", "Claude-SearchBot", "anthropic-ai",
             "PerplexityBot", "Perplexity-User", "Google-Extended",
             "Applebot-Extended", "CCBot", "cohere-ai", "Meta-ExternalAgent",
             "Bytespider", "Amazonbot", "DuckAssistBot", "MistralAI-User")

# Le nom que cherche un acheteur, terroir par terroir. Les intitulés
# administratifs ne sont pas toujours ceux qu'on tape : on garde la région
# comme clé, mais la page parle la langue de la recherche.
TERROIRS = {
    "Normandie": {
        "slug": "normandie",
        "cherche": "Normandie",
        "atouts": "pluviométrie régulière, nappes bien rechargées, "
                  "bâti en pierre et en colombage, littoral et bocage",
    },
    "Centre-Val de Loire": {
        "slug": "centre-val-de-loire",
        "cherche": "Val de Loire et Berry",
        "atouts": "vallées fraîches, forêts de Sologne, prix parmi les plus "
                  "bas à moins de deux heures de Paris",
    },
    "Grand Est": {
        "slug": "grand-est",
        "cherche": "Lorraine, Champagne et Ardennes",
        "atouts": "massifs boisés, altitude, ressource en eau abondante, "
                  "immobilier très accessible",
    },
    "Hauts-de-France": {
        "slug": "hauts-de-france",
        "cherche": "Picardie et Hauts-de-France",
        "atouts": "proximité immédiate de Paris, étés plus tempérés que "
                  "le Bassin parisien, bocage de l'Avesnois",
    },
    "Bourgogne-Franche-Comté": {
        "slug": "bourgogne-franche-comte",
        "cherche": "Bourgogne et Franche-Comté",
        "atouts": "relief et altitude, forêts du Morvan et du Jura, "
                  "villages viticoles",
    },
    "Pays de la Loire": {
        "slug": "pays-de-la-loire",
        "cherche": "Sarthe et Pays de la Loire",
        "atouts": "douceur océanique, bocage, accès direct par la ligne "
                  "à grande vitesse",
    },
}

_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")


def slug(texte: str) -> str:
    """« Saint-Bérain-sur-Dheune » → « saint-berain-sur-dheune »."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", (texte or "").lower())
        if unicodedata.category(c) != "Mn")
    return _NON_ALPHANUM.sub("-", sans_accents).strip("-")


def descriptif_annonce(bien: dict) -> str:
    """« maison-120m2-belleme-61130 » — la part lisible de l'adresse."""
    morceaux = [bien.get("type_bien") or "bien"]
    if bien.get("surface_m2"):
        morceaux.append(f"{round(bien['surface_m2'])}m2")
    if bien.get("commune"):
        morceaux.append(bien["commune"])
    if bien.get("code_postal"):
        morceaux.append(str(bien["code_postal"]))
    return slug("-".join(morceaux)) or "bien"


def url_annonce(bien: dict) -> str:
    """Une adresse qui dit ce qu'elle contient, comme le font les portails.

    `/annonce/maison-120m2-belleme-61130/immo-ray-abc123` plutôt que
    `/annonce/abc123` : l'adresse est le premier texte que lit un moteur, et
    le premier que voit un humain à qui on la partage.

    Deux SEGMENTS, et non un seul avec l'identifiant collé au bout. Nos
    identifiants contiennent eux-mêmes des tirets — « immo-ray-abc123 »,
    « iad-france-21-def456 » — et les découper au dernier tiret rendait
    « abc123 », un identifiant qui n'existe pas. Toutes les fiches
    répondaient 410.
    """
    return f"/annonce/{descriptif_annonce(bien)}/{bien['id']}"


def url_terroir(region: str) -> str:
    fiche = TERROIRS.get(region)
    return f"/terroir/{fiche['slug']}" if fiche else "/"


def region_du_slug(valeur: str) -> str | None:
    for region, fiche in TERROIRS.items():
        if fiche["slug"] == valeur:
            return region
    return None


# « Maison pas chère à la campagne » est l'une des requêtes les plus tapées
# du marché, et des comptes entiers vivent de l'exploiter — un prix incrusté
# sur une photo, une commune, rien d'autre. Ils vendent le prix.
#
# Nous pouvons vendre le CROISEMENT, que personne d'autre ne sait faire faute
# de données : bon marché ET bien noté. Le seuil est rond parce qu'il doit se
# retenir, pas parce qu'un calcul l'a trouvé.
SEUIL_PETITS_PRIX = 100_000
URL_PETITS_PRIX = "/petits-prix"

# Deuxième croisement, sur la même idée : une tranche de prix ET un état.
#
# « Maison sans travaux » est la requête de l'acheteur pressé — celui qui ne
# peut pas se loger ailleurs pendant un chantier, ou qui n'a pas le second
# budget. Les portails y répondent par une case à cocher que le vendeur remplit
# lui-même et que personne ne vérifie.
#
# Nous n'avons pas de case : nous avons le texte des annonces, et nous ne
# retenons que celles qui l'AFFIRMENT (voir app/etat_du_bien.py). Le silence
# n'est pas une bonne nouvelle — cent soixante-deux annonces de la tranche ne
# disent rien de leur état — et cette page ne le compte pas comme telle. C'est
# ce qui la distingue, et c'est ce qu'elle doit écrire noir sur blanc.
#
# La borne basse existe parce qu'en dessous « sans travaux » n'est presque
# jamais vrai ; la borne haute, parce qu'au-delà l'acheteur pressé n'est plus
# celui-là. Toutes deux sont rondes pour se retenir.
PLANCHER_SANS_TRAVAUX = 90_000
PLAFOND_SANS_TRAVAUX = 175_000
URL_SANS_TRAVAUX = "/sans-travaux"

URL_ALERTES = "/alertes"

# L'adresse à laquelle les demandes d'alerte arrivent. Tant qu'elle est vide,
# la page affiche les critères et dit clairement que les alertes ne sont pas
# encore ouvertes — plutôt qu'un formulaire qui recueille une adresse pour la
# perdre. C'est exactement ce que faisait la mise en relation retirée : son
# journal vivait dans /tmp sur l'hébergement, effacé à chaque redémarrage.
COURRIEL_ALERTES = ""

# Budgets proposés. Ronds, parce qu'ils doivent se choisir sans réfléchir.
PALIERS_ALERTE = (100_000, 150_000, 200_000, 300_000, 500_000, 700_000)


# --- Formulations ----------------------------------------------------------

def _euros(valeur) -> str:
    """Espace INSÉCABLE pour les milliers, comme dans l'interface."""
    return f"{round(valeur):,}".replace(",", " ") + " €" if valeur else ""


def titre_annonce(bien: dict) -> str:
    """« Maison 5 pièces 120 m² à Bellême (61130) — 250 000 € »

    L'ordre suit celui des portails immobiliers, parce que c'est l'ordre
    dans lequel la requête est tapée : type, taille, lieu, prix.
    """
    bouts = [(bien.get("type_bien") or "Bien").capitalize()]
    if bien.get("pieces"):
        bouts.append(f"{bien['pieces']} pièces")
    if bien.get("surface_m2"):
        bouts.append(f"{round(bien['surface_m2'])} m²")
    lieu = bien.get("commune") or ""
    if lieu and bien.get("code_postal"):
        lieu = f"{lieu} ({bien['code_postal']})"
    debut = " ".join(bouts) + (f" à {lieu}" if lieu else "")
    return f"{debut} — {_euros(bien.get('prix'))}" if bien.get("prix") else debut


def description_annonce(bien: dict) -> str:
    """Ce que Google affiche sous le lien, et ce qu'une IA cite.

    Des faits d'abord, puis notre apport. Environ 155 signes utiles : au-delà
    la fin est coupée, en deçà on gaspille la seule phrase qu'on nous donne.
    """
    faits = []
    if bien.get("surface_m2"):
        faits.append(f"{round(bien['surface_m2'])} m²")
    if bien.get("pieces"):
        faits.append(f"{bien['pieces']} pièces")
    if bien.get("terrain_m2"):
        faits.append(f"terrain {round(bien['terrain_m2']):,}".replace(",", " ") + " m²")
    phrase = (f"{(bien.get('type_bien') or 'Bien').capitalize()} de "
              f"{', '.join(faits)} à {bien.get('commune') or 'la campagne'}")
    if bien.get("prix"):
        phrase += f", {_euros(bien['prix'])}"
    phrase += ". "
    notre = []
    if bien.get("score_total"):
        notre.append(f"score de résilience {round(bien['score_total'])}/100")
    if bien.get("altitude") is not None:
        notre.append(f"altitude {round(bien['altitude'])} m")
    if bien.get("temps_voiture_min"):
        heures, minutes = divmod(round(bien["temps_voiture_min"]), 60)
        notre.append(f"{heures} h {minutes:02d} de Paris" if heures
                     else f"{minutes} min de Paris")
    if notre:
        phrase += "Analyse Refuge Immo : " + ", ".join(notre) + "."
    return phrase.strip()


def titre_terroir(region: str, nombre: int) -> str:
    fiche = TERROIRS.get(region, {"cherche": region})
    return (f"Maisons à vendre en {fiche['cherche']} — {nombre} biens "
            f"analysés face au climat")


def description_terroir(region: str, nombre: int, communes: int,
                        prix_median: int | None) -> str:
    fiche = TERROIRS.get(region, {"cherche": region})
    prix = f" Prix médian {_euros(prix_median)}." if prix_median else ""
    return (f"{nombre} maisons et propriétés à vendre en {fiche['cherche']}, "
            f"réparties sur {communes} communes, chacune notée sur l'eau, la "
            f"chaleur, les risques naturels et l'accès à Paris.{prix}")


def reponse_terroir(region: str, nombre: int, communes: int,
                    prix_median: int | None, altitude_mediane: int | None,
                    part_hors_inondation: int | None) -> str:
    """Le paragraphe qu'une IA peut citer telle quelle.

    Un assistant qui répond à « où acheter une maison résiliente en
    Normandie ? » ne recopie pas une page : il en extrait un passage
    autonome. Pour être citable, celui-ci doit répondre à la question dès
    la première phrase, tenir seul hors de son contexte, et porter des
    chiffres vérifiables. On vise cent quarante à cent soixante-dix mots.
    """
    fiche = TERROIRS.get(region, {"cherche": region, "atouts": ""})
    phrases = [
        f"En {fiche['cherche']}, Refuge Immo suit {nombre} maisons et "
        f"propriétés à vendre réparties sur {communes} communes, toutes à "
        f"moins de 350 km de Paris."
    ]
    if fiche.get("atouts"):
        phrases.append(f"Le terroir présente {fiche['atouts']}.")
    if prix_median:
        phrases.append(f"Le prix médian y est de {_euros(prix_median)}.")
    if altitude_mediane is not None:
        phrases.append(f"L'altitude médiane des biens suivis est de "
                       f"{altitude_mediane} m.")
    if part_hors_inondation is not None:
        phrases.append(f"{part_hors_inondation} % d'entre eux se situent sur "
                       f"une commune où aucun risque d'inondation n'est "
                       f"recensé par Géorisques.")
    phrases.append(
        "Chaque bien reçoit une note de résilience sur 100, construite à "
        "partir de quatre piliers : la ressource en eau, l'exposition à la "
        "chaleur et aux risques naturels, l'autonomie du logement "
        "(chauffage au bois, puits, dépendances, terrain cultivable) et "
        "l'accessibilité depuis Paris en voiture comme en train. Les "
        "données de risque proviennent de Géorisques, le service public de "
        "l'État ; les altitudes et les densités de population de l'IGN et "
        "de l'Insee.")
    return " ".join(phrases)


def titre_petits_prix(nombre: int) -> str:
    return (f"Maisons à moins de {_euros(SEUIL_PETITS_PRIX)} — {nombre} biens "
            f"notés face au climat")


def description_petits_prix(nombre: int, bien_notes: int,
                            prix_median: int | None) -> str:
    prix = f" Prix médian {_euros(prix_median)}." if prix_median else ""
    return (f"{nombre} maisons à vendre sous {_euros(SEUIL_PETITS_PRIX)} à "
            f"moins de 350 km de Paris, classées par note de résilience : "
            f"eau, chaleur, risques naturels, accès. {bien_notes} d'entre "
            f"elles dépassent 40 sur 100.{prix}")


def reponse_petits_prix(nombre: int, bien_notes: int, communes: int,
                        prix_median: int | None, mediane_generale: int | None,
                        moins_cher: int | None) -> str:
    """Le paragraphe citable de la page — le seul angle que nous ayons en
    propre sur cette requête.

    « Maison pas chère » se répond partout, et toujours de la même façon :
    une liste de prix. Ce qu'aucune de ces réponses ne dit, c'est si le bien
    sera encore habitable dans vingt ans. C'est ce que ce paragraphe apporte,
    et il ne vaut que par ses chiffres.
    """
    phrases = [
        f"Refuge Immo suit {nombre} maisons à vendre sous "
        f"{_euros(SEUIL_PETITS_PRIX)}, réparties sur {communes} communes à "
        f"moins de 350 km de Paris."
    ]
    if moins_cher:
        phrases.append(f"La moins chère est affichée à {_euros(moins_cher)}.")
    if prix_median:
        phrases.append(f"Le prix médian de cette sélection est de "
                       f"{_euros(prix_median)}.")
    phrases.append(
        f"Un petit prix ne dit rien de la solidité d'un lieu : ces biens sont "
        f"donc classés par note de résilience et non par prix croissant. "
        f"{bien_notes} d'entre eux atteignent 40 sur 100 ou davantage")
    if mediane_generale:
        phrases[-1] += (f", quand la médiane de tout le catalogue est de "
                        f"{mediane_generale}")
    phrases[-1] += "."
    phrases.append(
        "La note se construit sur quatre piliers : la ressource en eau, "
        "l'exposition à la chaleur et aux risques naturels, l'autonomie du "
        "logement (chauffage au bois, puits, dépendances, terrain "
        "cultivable) et l'accès à Paris en voiture comme en train. Les "
        "risques proviennent de Géorisques, service public de l'État.")
    phrases.append(
        "Ces prix sont ceux DEMANDÉS par les agences : à ce niveau, ils "
        "supposent presque toujours des travaux, que le catalogue ne chiffre "
        "pas.")
    return " ".join(phrases)


def _tranche_sans_travaux() -> str:
    return (f"{_euros(PLANCHER_SANS_TRAVAUX)} et "
            f"{_euros(PLAFOND_SANS_TRAVAUX)}")


def titre_sans_travaux(nombre: int) -> str:
    return (f"Maisons sans travaux entre {_tranche_sans_travaux()} — "
            f"{nombre} biens qui l'annoncent")


def description_sans_travaux(nombre: int, bien_notes: int,
                             prix_median: int | None) -> str:
    prix = f" Prix médian {_euros(prix_median)}." if prix_median else ""
    return (f"{nombre} maisons à vendre entre {_tranche_sans_travaux()} à "
            f"moins de 350 km de Paris dont l'annonce indique qu'il n'y a pas "
            f"de travaux à prévoir, classées par note de résilience. "
            f"{bien_notes} dépassent 40 sur 100.{prix}")


def reponse_sans_travaux(nombre: int, dans_la_tranche: int, muettes: int,
                         communes: int, prix_median: int | None,
                         bien_notes: int) -> str:
    """Le paragraphe citable — et l'aveu qui le rend crédible.

    Toutes les réponses à « maison sans travaux » reposent sur une case cochée
    par le vendeur. La nôtre repose sur ce que l'annonce écrit, ce qui est plus
    honnête mais incomplet : la plupart des annonces ne disent rien. Le dire
    dans le paragraphe même est le seul moyen que la page ne promette pas plus
    qu'elle ne tient.
    """
    phrases = [
        f"Refuge Immo suit {dans_la_tranche} maisons à vendre entre "
        f"{_tranche_sans_travaux()} à moins de 350 km de Paris. "
        f"{nombre} d'entre elles indiquent explicitement, dans leur annonce, "
        f"qu'aucun travaux n'est à prévoir — « habitable de suite », "
        f"« entièrement rénovée », « aucun travaux à prévoir » — et ce sont "
        f"celles que liste cette page, réparties sur {communes} communes."
    ]
    phrases.append(
        f"Les {muettes} autres ne sont pas écartées parce qu'elles auraient "
        f"des travaux : elles n'en parlent tout simplement pas. Une annonce "
        f"muette n'est pas une bonne nouvelle, et cette page ne la compte pas "
        f"comme telle.")
    if prix_median:
        phrases.append(f"Le prix médian de la sélection est de "
                       f"{_euros(prix_median)}.")
    phrases.append(
        f"Le classement se fait par note de résilience et non par prix : "
        f"{bien_notes} de ces biens atteignent 40 sur 100 ou davantage. La "
        f"note se construit sur quatre piliers — la ressource en eau, "
        f"l'exposition à la chaleur et aux risques naturels, l'autonomie du "
        f"logement et l'accès à Paris. Les risques proviennent de Géorisques, "
        f"service public de l'État.")
    phrases.append(
        "« Sans travaux » est ici la parole de l'agence, relevée dans son "
        "annonce, et non un constat que nous aurions fait sur place. Elle ne "
        "remplace ni une visite ni les diagnostics obligatoires.")
    return " ".join(phrases)


# --- Données structurées ---------------------------------------------------

def jsonld_annonce(bien: dict, base: str = SITE) -> dict:
    """schema.org/RealEstateListing — le vocabulaire que lisent les moteurs.

    On décrit l'OFFRE et le LIEU. Le prix va dans une `Offer` ; sans elle,
    le montant reste un nombre au milieu d'un texte.
    """
    adresse = {"@type": "PostalAddress", "addressCountry": "FR"}
    if bien.get("commune"):
        adresse["addressLocality"] = bien["commune"]
    if bien.get("code_postal"):
        adresse["postalCode"] = str(bien["code_postal"])
    if bien.get("region"):
        adresse["addressRegion"] = bien["region"]

    logement = {"@type": "SingleFamilyResidence", "address": adresse}
    if bien.get("surface_m2"):
        logement["floorSize"] = {"@type": "QuantitativeValue",
                                 "unitCode": "MTK", "value": bien["surface_m2"]}
    if bien.get("pieces"):
        logement["numberOfRooms"] = bien["pieces"]
    if bien.get("lat") is not None and bien.get("lon") is not None:
        logement["geo"] = {"@type": "GeoCoordinates",
                           "latitude": bien["lat"], "longitude": bien["lon"]}
    if bien.get("terrain_m2"):
        logement["lotSize"] = {"@type": "QuantitativeValue",
                               "unitCode": "MTK", "value": bien["terrain_m2"]}

    fiche = {
        "@context": "https://schema.org",
        "@type": "RealEstateListing",
        "@id": f"{base}{url_annonce(bien)}",
        "url": f"{base}{url_annonce(bien)}",
        "name": titre_annonce(bien),
        "description": description_annonce(bien),
        "datePosted": bien.get("vue_le") or bien.get("revue_le"),
        "about": logement,
    }
    if bien.get("photo"):
        fiche["image"] = bien["photo"]
    if bien.get("prix"):
        fiche["offers"] = {
            "@type": "Offer", "price": round(bien["prix"]),
            "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
            "url": bien.get("url") or f"{base}{url_annonce(bien)}",
        }
    if bien.get("agence"):
        # L'agence VEND ; nous ne faisons que référencer. Le dire dans les
        # données structurées évite de nous faire passer pour le mandataire.
        fiche["provider"] = {"@type": "RealEstateAgent", "name": bien["agence"]}
        if bien.get("agence_url"):
            fiche["provider"]["url"] = bien["agence_url"]
    return {k: v for k, v in fiche.items() if v not in (None, "", [], {})}


def jsonld_organisation(base: str = SITE) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{base}/#organisation",
        "name": NOM,
        "url": base,
        "description": (
            "Sélection de maisons à vendre à moins de 350 km de Paris, "
            "notées sur leur résilience au changement climatique : eau, "
            "chaleur, risques naturels, autonomie et accès à Paris."),
    }


def jsonld_fil(chemin: list[tuple[str, str]], base: str = SITE) -> dict:
    """Fil d'Ariane : dit au moteur où la page se situe dans le site."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": rang, "name": nom,
             "item": f"{base}{lien}"}
            for rang, (nom, lien) in enumerate(chemin, start=1)],
    }


def jsonld_liste(biens: list[dict], base: str = SITE) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "numberOfItems": len(biens),
        "itemListElement": [
            {"@type": "ListItem", "position": rang,
             "url": f"{base}{url_annonce(b)}", "name": titre_annonce(b)}
            for rang, b in enumerate(biens, start=1)],
    }


# --- Fichiers réclamés par les robots --------------------------------------

def robots_txt(base: str = SITE) -> str:
    lignes = [
        "# Refuge Immo — tout est public, rien n'est à cacher.",
        "#",
        "# Les robots d'IA sont nommés un par un, et non laissés au « User-agent: * ».",
        "# Plusieurs n'explorent en effet que si une règle les vise nommément, et",
        "# l'enjeu est précis : un acheteur qui demande « où acheter une maison",
        "# résiliente près de Paris » pose désormais la question à un assistant.",
        "",
        "User-agent: *",
        "Allow: /",
        "",
        "# L'API sert l'interface : elle n'a rien à indexer, et son exploration",
        "# consommerait le budget de crawl sans rien apporter.",
        "Disallow: /api/",
        "",
    ]
    for robot in ROBOTS_IA:
        lignes += [f"User-agent: {robot}", "Allow: /", "Disallow: /api/", ""]
    lignes += [f"Sitemap: {base}/sitemap.xml", ""]
    return "\n".join(lignes)


def sitemap(biens: list[dict], regions_servies: dict, base: str = SITE,
            jour: str | None = None) -> str:
    """Le plan du site : accueil, terroirs, puis chaque annonce."""
    jour = jour or date.today().isoformat()
    entrees = [(base + "/", "1.0", "daily"),
               (base + URL_PETITS_PRIX, "0.9", "daily"),
               (base + URL_SANS_TRAVAUX, "0.9", "daily"),
               (base + URL_ALERTES, "0.5", "monthly")]
    entrees += [(f"{base}{url_terroir(r)}", "0.9", "daily")
                for r in regions_servies if r in TERROIRS]
    entrees += [(f"{base}{url_annonce(b)}", "0.6", "weekly") for b in biens]
    corps = "\n".join(
        f"  <url><loc>{html.escape(lien)}</loc>"
        f"<lastmod>{jour}</lastmod>"
        f"<changefreq>{frequence}</changefreq>"
        f"<priority>{poids}</priority></url>"
        for lien, poids, frequence in entrees)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{corps}\n</urlset>\n")


def llms_txt(total: int, par_region: dict, base: str = SITE) -> str:
    """Le résumé destiné aux modèles de langage (convention llmstxt.org).

    Un fichier Markdown à la racine, qui dit en clair ce qu'est le site, d'où
    viennent ses données et ce qu'elles valent. Son intérêt n'est pas d'être
    « lu par l'IA » comme un mot de passe : c'est de donner, en un seul
    endroit, la version que NOUS jugeons exacte — méthode, sources, limites —
    plutôt que de laisser un modèle la reconstituer de travers.
    """
    lignes = [
        f"# {NOM}",
        "",
        "> Sélection de maisons à vendre à moins de 350 km de Paris, notées "
        "sur leur résilience au changement climatique. Chaque bien reçoit une "
        "note sur 100 fondée sur quatre piliers : ressource en eau, "
        "exposition à la chaleur et aux risques naturels, autonomie du "
        "logement, accessibilité depuis Paris.",
        "",
        f"Le catalogue compte {total} biens, collectés directement sur les "
        "sites des agences et des réseaux de mandataires, et reconstatés "
        "régulièrement. Refuge Immo n'est pas une agence : le site ne vend "
        "rien, ne prend aucun mandat, et renvoie vers l'annonce d'origine.",
        "",
        "## Méthode de notation",
        "",
        "- **Eau** : pluviométrie du secteur, risque de sécheresse et de "
        "retrait-gonflement des argiles, présence d'un puits ou d'une source.",
        "- **Chaleur et risques** : altitude, densité urbaine (effet d'îlot "
        "de chaleur), risques recensés par Géorisques — inondation, feux de "
        "forêt, mouvements de terrain, distance à la centrale nucléaire la "
        "plus proche.",
        "- **Autonomie** : chauffage au bois, dépendances, cave, terrain "
        "cultivable, panneaux solaires.",
        "- **Accès à Paris** : temps de route estimé et gare la plus proche "
        "avec son temps de trajet.",
        "",
        "## Sources des données",
        "",
        "- Risques naturels : Géorisques (ministère de la Transition "
        "écologique).",
        "- Communes, codes postaux, densités : API Découpage administratif et "
        "Base Adresse Nationale (data.gouv.fr), Insee.",
        "- Altitudes : Open-Meteo et OpenTopoData.",
        "- Annonces : sites des agences immobilières et réseaux de "
        "mandataires, avec lien vers la source sur chaque fiche.",
        "",
        "## Limites à connaître",
        "",
        "- Les prix sont des prix DEMANDÉS par les agences, non des prix de "
        "vente constatés.",
        "- La note de résilience est un indicateur de comparaison entre les "
        "biens du catalogue, pas une expertise. Les notes observées vont "
        "aujourd'hui de 14 à 62 sur 100.",
        "- Les risques recensés valent pour la COMMUNE, pas pour la parcelle : "
        "presque toute commune française est concernée par au moins un "
        "risque. L'état des risques reste obligatoire à la vente.",
        "- Un bien peut avoir été vendu depuis son dernier constat ; la date "
        "de dernière vérification figure sur chaque fiche.",
        "",
        "## Terroirs couverts",
        "",
    ]
    for region, nombre in sorted(par_region.items(), key=lambda kv: -kv[1]):
        if region in TERROIRS:
            lignes.append(f"- [{TERROIRS[region]['cherche']}]"
                          f"({base}{url_terroir(region)}) : {nombre} biens")
    lignes += ["", "## Pages", "",
               f"- [Accueil et recherche]({base}/) : carte, filtres et "
               f"classement des {total} biens.",
               f"- [Maisons sous {_euros(SEUIL_PETITS_PRIX)}]"
               f"({base}{URL_PETITS_PRIX}) : la sélection à petit prix, "
               f"classée par note de résilience et non par prix — un bien "
               f"bon marché n'est pas forcément un bien vivable.",
               f"- [Maisons sans travaux entre {_tranche_sans_travaux()}]"
               f"({base}{URL_SANS_TRAVAUX}) : les biens dont l'annonce indique "
               f"explicitement qu'aucun travaux n'est à prévoir. Les annonces "
               f"muettes sur ce point ne sont pas comptées comme sans travaux.",
               f"- [Soyez alerté]({base}{URL_ALERTES}) : choisir un budget et "
               f"des terroirs pour être prévenu des nouvelles maisons. Aucune "
               f"mise en relation, aucune commission, aucune adresse transmise "
               f"à une agence.",
               f"- [Plan du site]({base}/sitemap.xml) : toutes les annonces.",
               ""]
    return "\n".join(lignes)
