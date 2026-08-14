"""Pages rendues par le SERVEUR, lisibles sans JavaScript.

Pourquoi doubler l'interface
----------------------------
L'application est une page unique rendue en JavaScript : excellente à
l'usage, invisible aux robots qui n'exécutent pas de script — c'est-à-dire
la plupart des robots d'IA. Ces pages-ci sont le même catalogue, écrit en
HTML par le serveur.

Elles ne sont pas des pages « pour robots ». Un humain qui arrive de Google
sur une fiche doit y trouver de quoi décider : les faits du bien, notre
analyse, le lien vers l'agence, et la porte d'entrée vers la recherche
complète. Une page qui n'aurait de valeur que pour un moteur serait une
page satellite — mal vue des moteurs, et à juste titre.

Ce qu'elles ne contiennent pas : le texte de vente de l'agence. Voir
app/seo.py pour la raison.
"""

from __future__ import annotations

import html
import json

from . import redaction, seo

_ENTETE_STYLE = """
:root { color-scheme: light }
body { margin: 0; font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
       color: #23301f; background: #f7f6f1 }
.bande { background: #1b4332; color: #f4f1e8; padding: 14px 20px }
.bande a { color: #f4f1e8; text-decoration: none; font-weight: 700;
           display: inline-flex; align-items: center; gap: 9px }
main { max-width: 760px; margin: 0 auto; padding: 24px 20px 64px }
h1 { font-size: 26px; line-height: 1.25; margin: 0 0 6px }
h2 { font-size: 19px; margin: 32px 0 8px }
.chapeau { font-size: 17px; color: #46543f }
.prix { font-size: 26px; font-weight: 800; color: #1b4332 }
dl { display: grid; grid-template-columns: auto 1fr; gap: 6px 18px; margin: 12px 0 }
dt { color: #6b7663 } dd { margin: 0; font-weight: 600 }
ul { padding-left: 20px } li { margin: 3px 0 }
.jetons { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 6px }
.jetons li { background: #e6ece1; border-radius: 99px; padding: 3px 11px; font-size: 14px }
.bouton { display: inline-block; background: #1b4332; color: #fff; padding: 11px 20px;
          border-radius: 8px; text-decoration: none; font-weight: 700; margin: 6px 8px 6px 0 }
.bouton.clair { background: #fff; color: #1b4332; border: 1.5px solid #1b4332 }
.fil { font-size: 14px; color: #6b7663; margin-bottom: 14px }
.fil a { color: #46543f }
.note { font-size: 14px; color: #6b7663; border-top: 1px solid #ddd8cc;
        margin-top: 34px; padding-top: 14px }
table { border-collapse: collapse; width: 100%; margin: 10px 0 }
td, th { text-align: left; padding: 7px 10px; border-bottom: 1px solid #e4e0d5 }
img { max-width: 100%; height: auto; border-radius: 10px }
figure.aerienne { margin: 14px 0 } 
figure.aerienne img { width: 100%; border-radius: 10px }
figure.aerienne figcaption { font-size: 13px; color: #6b7663; margin-top: 5px }
"""


def _e(valeur) -> str:
    return html.escape(str(valeur if valeur is not None else ""), quote=True)


def _jsonld(*blocs) -> str:
    """Les données structurées, échappées pour vivre dans un <script>.

    `json.dumps` protège les guillemets, mais ni « < » ni « / » : une commune
    dont le nom contiendrait `</script>` refermerait la balise, et tout ce
    qui suit serait lu comme du HTML. C'est une faille d'injection ordinaire,
    et nos données viennent de sites tiers — c'est-à-dire de nulle part.

    On échappe donc les trois caractères qui comptent en séquences unicode :
    le JSON reste rigoureusement le même pour qui le relit, et plus rien ne
    peut sortir de la balise.
    """
    def _sur(texte: str) -> str:
        return (texte.replace("<", "\\u003c")
                     .replace(">", "\\u003e")
                     .replace("&", "\\u0026"))

    return "\n".join(
        '<script type="application/ld+json">'
        + _sur(json.dumps(bloc, ensure_ascii=False, separators=(",", ":")))
        + "</script>" for bloc in blocs if bloc)


def _document(titre: str, description: str, canonique: str, corps: str,
              structure: str, base: str, image: str = "") -> str:
    """Le squelette commun. Toutes les balises que réclame un partage."""
    og_image = (f'<meta property="og:image" content="{_e(image)}">'
                if image else "")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(titre)} | {seo.NOM}</title>
<meta name="description" content="{_e(description)}">
<link rel="canonical" href="{_e(canonique)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{seo.NOM}">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{_e(titre)}">
<meta property="og:description" content="{_e(description)}">
<meta property="og:url" content="{_e(canonique)}">
{og_image}
<meta name="twitter:card" content="{'summary_large_image' if image else 'summary'}">
<link rel="icon" href="{seo.favicon()}">
<style>{_ENTETE_STYLE}</style>
{structure}
</head>
<body>
<div class="bande"><a href="{_e(base)}/">{seo.logo(26)}<span>{seo.NOM}</span></a></div>
<main>
{corps}
<p class="note">{seo.NOM} n'est pas une agence immobilière : le site ne vend
rien et ne prend aucun mandat. Il recense des annonces publiées par des
agences et des réseaux de mandataires, et les note sur leur résilience au
changement climatique. Chaque fiche renvoie vers l'annonce d'origine.</p>
</main>
</body>
</html>
"""


def _carte_aerienne(bien: dict, largeur: int = 640, hauteur: int = 320) -> str:
    """La commune vue du ciel — orthophotos IGN, Licence Ouverte.

    C'est la seule image de la fiche qui nous appartienne de plein droit, et
    la seule qui illustre ce que la page analyse : le paysage, le bâti, la
    forêt, l'eau. Elle est CADRÉE SUR LA COMMUNE, pas sur le bien — notre
    géolocalisation vient de la BAN sur commune et code postal, l'adresse
    exacte n'étant presque jamais publiée. La légende le dit en toutes
    lettres : la montrer comme la parcelle serait inventer.
    """
    lat, lon = bien.get("lat"), bien.get("lon")
    if lat is None or lon is None:
        return ""
    dlat, dlon = 0.006, 0.012
    bbox = f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}"
    return ("https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0"
            "&REQUEST=GetMap&LAYERS=ORTHOIMAGERY.ORTHOPHOTOS&STYLES="
            f"&FORMAT=image/jpeg&CRS=CRS:84&BBOX={bbox}"
            f"&WIDTH={largeur}&HEIGHT={hauteur}")


def _temps(minutes) -> str:
    if not minutes:
        return ""
    heures, reste = divmod(round(minutes), 60)
    return f"{heures} h {reste:02d}" if heures else f"{reste} min"


def page_annonce(bien: dict, voisins: list[dict], base: str = seo.SITE,
                 contexte: dict | None = None) -> str:
    """La fiche d'un bien : notre lecture des données, les faits, la source.

    `contexte` porte les médianes départementales, qui permettent de SITUER
    le bien plutôt que de le décrire. Sans elles la fiche reste juste, mais
    elle perd ce qui la rend propre à ce bien-là — et c'est justement ce qui
    la distingue des neuf cent quatre-vingt-douze autres.
    """
    canonique = f"{base}{seo.url_annonce(bien)}"
    region = bien.get("region") or ""
    fil = [("Accueil", "/")]
    if region in seo.TERROIRS:
        fil.append((seo.TERROIRS[region]["cherche"], seo.url_terroir(region)))
    fil.append((seo.titre_annonce(bien), seo.url_annonce(bien)))

    faits = []
    for etiquette, valeur in (
            ("Type", (bien.get("type_bien") or "").capitalize()),
            ("Surface habitable", f"{round(bien['surface_m2'])} m²" if bien.get("surface_m2") else ""),
            ("Pièces", bien.get("pieces")),
            ("Terrain", f"{round(bien['terrain_m2']):,}".replace(",", " ") + " m²" if bien.get("terrain_m2") else ""),
            ("Commune", f"{bien.get('commune') or ''} {('(' + str(bien['code_postal']) + ')') if bien.get('code_postal') else ''}".strip()),
            ("DPE", bien.get("dpe")),
    ):
        if valeur:
            faits.append(f"<dt>{_e(etiquette)}</dt><dd>{_e(valeur)}</dd>")

    analyse = []
    for etiquette, valeur in (
            ("Score de résilience", f"{round(bien['score_total'])} / 100" if bien.get("score_total") else ""),
            ("Altitude", f"{round(bien['altitude'])} m" if bien.get("altitude") is not None else ""),
            ("Route depuis Paris", _temps(bien.get("temps_voiture_min"))),
            ("Gare la plus proche", (f"{bien['train']['nom']} à {bien['train']['km']} km, "
                                     f"{_temps(bien['train'].get('minutes_paris'))} de Paris")
             if isinstance(bien.get("train"), dict) and bien["train"].get("nom") else ""),
            ("Densité de la commune", f"{round(bien['densite_hab_km2'])} hab/km²" if bien.get("densite_hab_km2") else ""),
    ):
        if valeur:
            analyse.append(f"<dt>{_e(etiquette)}</dt><dd>{_e(valeur)}</dd>")

    badges = "".join(f"<li>{_e(b)}</li>" for b in (bien.get("badges") or []))
    ciel = _carte_aerienne(bien)
    aerienne = (
        f'<figure class="aerienne"><img src="{_e(ciel)}" '
        f'alt="Vue aérienne de {_e(bien.get("commune") or "la commune")}" '
        f'loading="lazy" onerror="this.parentNode.remove()">'
        f'<figcaption>La commune de {_e(bien.get("commune") or "")} vue du ciel '
        f'— orthophoto IGN. L’emplacement exact du bien n’est pas connu : '
        f'l’adresse ne figure pas dans l’annonce.</figcaption></figure>'
    ) if ciel else ""

    # Les paragraphes écrits depuis nos données : c'est le corps de la page,
    # et la seule chose qu'aucun autre site ne peut publier. Voir
    # app/redaction.py pour ce qu'on s'interdit d'y mettre.
    prose = "".join(f"<p>{_e(p)}</p>"
                    for p in redaction.description_longue(bien, contexte))

    suite = "".join(
        f'<li><a href="{_e(base + seo.url_annonce(v))}">{_e(seo.titre_annonce(v))}</a></li>'
        for v in voisins[:8])

    corps = f"""
<nav class="fil">{" › ".join(
    f'<a href="{_e(base + lien)}">{_e(nom)}</a>' if rang < len(fil) else _e(nom)
    for rang, (nom, lien) in enumerate(fil, start=1))}</nav>

<h1>{_e(seo.titre_annonce(bien))}</h1>
<p class="chapeau">{_e(seo.description_annonce(bien))}</p>
{f'<img src="{_e(bien["photo"])}" alt="{_e(seo.titre_annonce(bien))}" loading="lazy" onerror="this.remove()">' if bien.get("photo") else ""}
<p class="prix">{_e(seo._euros(bien.get("prix")) or "Prix sur demande")}</p>

<h2>Que disent les données sur ce bien ?</h2>
{prose}
{aerienne}

<h2>Caractéristiques et analyse en bref</h2>
<dl>{"".join(faits)}{"".join(analyse)}</dl>
{f'<ul class="jetons">{badges}</ul>' if badges else ""}

<h2>Comment visiter ce bien ?</h2>
<p>L'annonce est publiée par <strong>{_e(bien.get("agence") or "une agence partenaire")}</strong>.
Refuge Immo ne prend pas de mandat : la visite et la transaction se font
directement avec elle.</p>
<p>
{f'<a class="bouton" href="{_e(bien.get("url"))}" rel="nofollow noopener">Voir l’annonce chez {_e(bien.get("agence") or "l’agence")}</a>' if bien.get("url") else ""}
<a class="bouton clair" href="{_e(base)}/?bien={_e(bien.get("id"))}">Ouvrir la carte et les filtres</a>
</p>
{f'<p class="note">Annonce vérifiée en ligne le {_e(bien.get("revue_le"))}. Un bien peut avoir été vendu depuis.</p>' if bien.get("revue_le") else ""}

{f'<h2>Autres biens du même terroir</h2><ul>{suite}</ul>' if suite else ""}
"""
    structure = _jsonld(
        seo.jsonld_annonce(bien, base),
        seo.jsonld_fil(fil, base),
        seo.jsonld_organisation(base))
    return _document(seo.titre_annonce(bien), seo.description_annonce(bien),
                     canonique, corps, structure, base,
                     image=bien.get("photo") or "")


def page_terroir(region: str, biens: list[dict], stats: dict,
                 base: str = seo.SITE) -> str:
    """La page d'un terroir — celle que l'on cherche vraiment.

    Personne ne tape « res-immo ». On tape « maison à vendre en Normandie »,
    « où s'installer face au réchauffement », « maison avec puits et terrain
    près de Paris ». Ces six pages sont les seules qui puissent répondre à
    ces requêtes-là, parce qu'elles portent un sujet et non un bien.
    """
    fiche = seo.TERROIRS.get(region, {"cherche": region, "slug": seo.slug(region)})
    canonique = f"{base}{seo.url_terroir(region)}"
    titre = seo.titre_terroir(region, len(biens))
    description = seo.description_terroir(
        region, len(biens), stats.get("communes", 0), stats.get("prix_median"))
    reponse = seo.reponse_terroir(
        region, len(biens), stats.get("communes", 0), stats.get("prix_median"),
        stats.get("altitude_mediane"), stats.get("part_hors_inondation"))

    lignes = "".join(
        f'<tr><td><a href="{_e(base + seo.url_annonce(b))}">{_e(seo.titre_annonce(b))}</a></td>'
        f'<td>{_e(round(b["score_total"]) if b.get("score_total") else "—")}</td></tr>'
        for b in biens[:60])

    communes = "".join(
        f"<li>{_e(nom)} ({nombre})</li>"
        for nom, nombre in (stats.get("communes_frequentes") or [])[:18])

    autres = "".join(
        f'<li><a href="{_e(base + seo.url_terroir(r))}">{_e(seo.TERROIRS[r]["cherche"])}</a></li>'
        for r in seo.TERROIRS if r != region)

    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › {_e(fiche['cherche'])}</nav>

<h1>Acheter une maison résiliente en {_e(fiche['cherche'])}</h1>
<p class="chapeau">{_e(reponse)}</p>

<p>
<a class="bouton" href="{_e(base)}/?region={_e(region)}">Voir les {len(biens)} biens sur la carte</a>
</p>

<h2>Combien de biens et à quel prix ?</h2>
<table>
<tr><th>Biens suivis</th><td>{len(biens)}</td></tr>
<tr><th>Communes couvertes</th><td>{_e(stats.get("communes", 0))}</td></tr>
{f'<tr><th>Prix médian</th><td>{_e(seo._euros(stats["prix_median"]))}</td></tr>' if stats.get("prix_median") else ""}
{f'<tr><th>Surface médiane</th><td>{_e(round(stats["surface_mediane"]))} m²</td></tr>' if stats.get("surface_mediane") else ""}
{f'<tr><th>Altitude médiane</th><td>{_e(stats["altitude_mediane"])} m</td></tr>' if stats.get("altitude_mediane") is not None else ""}
</table>

{f'<h2>Dans quelles communes ?</h2><ul class="jetons">{communes}</ul>' if communes else ""}

<h2>Les biens suivis en {_e(fiche['cherche'])}</h2>
<table>
<tr><th>Bien</th><th>Résilience</th></tr>
{lignes}
</table>
{f'<p>… et {len(biens) - 60} autres biens, à parcourir sur <a href="{_e(base)}/?region={_e(region)}">la carte</a>.</p>' if len(biens) > 60 else ""}

<h2>Comment la note de résilience est-elle calculée ?</h2>
<p>Quatre piliers, pondérés puis ramenés sur 100 : la <strong>ressource en
eau</strong> (pluviométrie, sécheresse, retrait-gonflement des argiles,
présence d'un puits), l'<strong>exposition à la chaleur et aux risques
naturels</strong> (altitude, densité urbaine, inondation, feux de forêt,
mouvements de terrain), l'<strong>autonomie du logement</strong> (chauffage
au bois, dépendances, cave, terrain cultivable) et l'<strong>accès à
Paris</strong> (route et train). Les risques proviennent de Géorisques, le
service public de l'État ; les altitudes et densités de l'IGN et de l'Insee.</p>
<p>Cette note compare les biens du catalogue entre eux. Ce n'est pas une
expertise, et elle ne remplace pas l'état des risques, obligatoire à la
vente. Les notes observées vont aujourd'hui de 14 à 62 sur 100.</p>

<h2>Les autres terroirs</h2>
<ul>{autres}</ul>
"""
    structure = _jsonld(
        seo.jsonld_liste(biens[:60], base),
        seo.jsonld_fil([("Accueil", "/"), (fiche["cherche"], seo.url_terroir(region))], base),
        seo.jsonld_organisation(base))
    return _document(titre, description, canonique, corps, structure, base)


def page_petits_prix(biens: list[dict], stats: dict,
                     base: str = seo.SITE) -> str:
    """La sélection à petit prix, classée par RÉSILIENCE et non par prix.

    « Maison pas chère à la campagne » est l'une des requêtes les plus
    tapées du marché, et des comptes entiers en vivent : un prix incrusté sur
    une photo, une commune, rien d'autre. Ils répondent tous la même chose,
    une liste de prix croissants.

    Aucun ne peut dire si le lieu tiendra. C'est la seule chose que nous
    ayons en propre, alors le tri de cette page l'affirme dès la première
    ligne : le moins cher n'ouvre pas la liste, le mieux noté l'ouvre. Une
    page triée par prix croissant serait la millième de son espèce.
    """
    canonique = f"{base}{seo.URL_PETITS_PRIX}"
    titre = seo.titre_petits_prix(len(biens))
    description = seo.description_petits_prix(
        len(biens), stats.get("bien_notes", 0), stats.get("prix_median"))
    reponse = seo.reponse_petits_prix(
        len(biens), stats.get("bien_notes", 0), stats.get("communes", 0),
        stats.get("prix_median"), stats.get("mediane_generale"),
        stats.get("moins_cher"))

    lignes = "".join(
        f'<tr><td><a href="{_e(base + seo.url_annonce(b))}">'
        f'{_e(seo.titre_annonce(b))}</a></td>'
        f'<td>{_e(seo._euros(b.get("prix")))}</td>'
        f'<td>{_e(round(b["score_total"]) if b.get("score_total") else "—")}</td></tr>'
        for b in biens[:60])

    terroirs = "".join(
        f'<li><a href="{_e(base + seo.url_terroir(r))}">'
        f'{_e(seo.TERROIRS[r]["cherche"])}</a></li>' for r in seo.TERROIRS)

    seuil = seo._euros(seo.SEUIL_PETITS_PRIX)
    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Maisons sous {_e(seuil)}</nav>

<h1>Maisons à vendre sous {_e(seuil)}, classées par résilience</h1>
<p class="chapeau">{_e(reponse)}</p>

<p>
<a class="bouton" href="{_e(base)}/?prix_max={seo.SEUIL_PETITS_PRIX}">Voir ces {len(biens)} biens sur la carte</a>
</p>

<h2>Ce que contient cette sélection</h2>
<table>
<tr><th>Biens sous {_e(seuil)}</th><td>{len(biens)}</td></tr>
<tr><th>Communes couvertes</th><td>{_e(stats.get("communes", 0))}</td></tr>
{f'<tr><th>Le moins cher</th><td>{_e(seo._euros(stats["moins_cher"]))}</td></tr>' if stats.get("moins_cher") else ""}
{f'<tr><th>Prix médian de la sélection</th><td>{_e(seo._euros(stats["prix_median"]))}</td></tr>' if stats.get("prix_median") else ""}
{f'<tr><th>Surface médiane</th><td>{_e(round(stats["surface_mediane"]))} m²</td></tr>' if stats.get("surface_mediane") else ""}
<tr><th>Notés 40 sur 100 ou plus</th><td>{_e(stats.get("bien_notes", 0))}</td></tr>
</table>

<h2>Pourquoi ce classement n'est pas par prix croissant</h2>
<p>Un prix bas se lit en une seconde ; ce qu'il coûtera vraiment ne se lit
nulle part. Une maison à 30 000 € sur une commune exposée au retrait des
argiles, sans eau et loin de toute gare, n'est pas une affaire : c'est un
engagement long qu'on prend sans le savoir. Cette page place donc en tête les
biens les mieux notés de la tranche, et non les moins chers.</p>

<h2>Les biens, du mieux noté au moins bien noté</h2>
<table>
<tr><th>Bien</th><th>Prix</th><th>Résilience</th></tr>
{lignes}
</table>
{f'<p>… et {len(biens) - 60} autres, à parcourir sur <a href="{_e(base)}/?prix_max={seo.SEUIL_PETITS_PRIX}">la carte</a>.</p>' if len(biens) > 60 else ""}

<h2>Ce que ces prix ne disent pas</h2>
<p>Ce sont les prix <strong>demandés</strong> par les agences, relevés
automatiquement sur leurs sites. À ce niveau, ils supposent presque toujours
des travaux — toiture, assainissement, isolation — que ce catalogue ne chiffre
pas et ne prétend pas estimer. Les frais de notaire, la taxe foncière et le
coût du chauffage n'y figurent pas davantage.</p>
<p>La note de résilience compare les biens du catalogue entre eux : elle n'est
pas une expertise et ne remplace pas l'état des risques, obligatoire à la
vente. Les risques recensés valent pour la <strong>commune</strong>, pas pour
la parcelle.</p>

<h2>Chercher par terroir</h2>
<ul>{terroirs}</ul>
"""
    structure = _jsonld(
        seo.jsonld_liste(biens[:60], base),
        seo.jsonld_fil([("Accueil", "/"),
                        (f"Maisons sous {seuil}", seo.URL_PETITS_PRIX)], base),
        seo.jsonld_organisation(base))
    return _document(titre, description, canonique, corps, structure, base)
