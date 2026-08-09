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

SITE = "https://res-immo.vercel.app"
NOM = "Refuge Immo"

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
    entrees = [(base + "/", "1.0", "daily")]
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
               f"- [Plan du site]({base}/sitemap.xml) : toutes les annonces.",
               ""]
    return "\n".join(lignes)
