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
import math
import re

from . import climat, redaction, seo

_ENTETE_STYLE = """
/* Mêmes polices et mêmes échelles que l'application (docs/CHARTE.md). */
@font-face { font-family: "Figtree"; src: url("/vendor/fonts/figtree.woff2") format("woff2");
  font-weight: 300 900; font-style: normal; font-display: swap }
@font-face { font-family: "Bricolage Grotesque"; src: url("/vendor/fonts/bricolage-grotesque.woff2") format("woff2");
  font-weight: 200 800; font-style: normal; font-display: swap }
:root { color-scheme: light; --focus: #1b4332; --focus-clair: #f4f1e8;
  --f-titre: "Bricolage Grotesque", "Figtree", system-ui, sans-serif;
  --f-texte: "Figtree", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --t-12: 12px; --t-14: 14px; --t-16: 16px; --t-18: 18px; --t-20: 20px; --t-24: 24px; --t-32: 32px;
  --e-4: 4px; --e-8: 8px; --e-12: 12px; --e-16: 16px; --e-24: 24px; --e-32: 32px; --e-48: 48px; --e-64: 64px;
  --r-6: 6px; --r-10: 10px; --r-14: 14px; --r-pastille: 999px }
h1, h2, .prix, .score-bloc b, .bande a, .cle b { font-family: var(--f-titre) }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; border-radius: var(--r-6) }
.bande :focus-visible { outline-color: var(--focus-clair) }
body { margin: 0; font: var(--t-16)/1.6 var(--f-texte);
       color: #23301f; background: #f7f6f1 }
.bande { background: #1b4332; color: #f4f1e8; padding: var(--e-16) var(--e-24) }
.bande a { color: #f4f1e8; text-decoration: none; font-weight: 700;
           display: inline-flex; align-items: center; gap: var(--e-8) }
main { max-width: 760px; margin: 0 auto; padding: var(--e-24) var(--e-24) var(--e-64) }
h1 { font-size: var(--t-24); line-height: 1.25; margin: 0 0 var(--e-4); text-wrap: balance }
h2 { font-size: var(--t-20); margin: var(--e-32) 0 var(--e-8); text-wrap: balance }
.chapeau { font-size: var(--t-18); color: #46543f }
.prix { font-size: var(--t-32); font-weight: 800; color: #1b4332; margin: 0; line-height: 1.1;
        letter-spacing: -.5px }
/* Le prix et le score, côte à côte sous la photo : les deux choses qu'on
   vient lire, et la seconde est la seule qu'aucun portail ne donne. */
.resume { display: flex; align-items: center; justify-content: space-between;
          gap: var(--e-16); margin: var(--e-16) 0 var(--e-4) }
.classe-score { margin: var(--e-4) 0 0; font-weight: 600; color: #2d6a4f; font-size: var(--t-16) }
.score-bloc { flex: none; min-width: 76px; padding: var(--e-12) var(--e-12) var(--e-8); border-radius: var(--r-14);
              display: flex; flex-direction: column; align-items: center; line-height: 1;
              border: 2px solid #1b4332 }
.score-bloc b { font-size: var(--t-32); font-weight: 800; letter-spacing: -.5px }
.score-bloc i { font-style: normal; font-size: var(--t-12); font-weight: 700; opacity: .8; margin-top: 2px }
.score-bloc small { font-size: var(--t-12); font-weight: 600; margin-top: var(--e-4); opacity: .9 }
.score-bloc.n1 { background: #c9dcc2; color: #24312a }
.score-bloc.n2 { background: #7fae84; color: #14281c }
.score-bloc.n3 { background: #3f7d53; color: #fff }
.score-bloc.n4 { background: #1b4332; color: #fff }
.ico { width: 1.15em; height: 1.15em; flex: none; vertical-align: -.2em; fill: none;
       stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round }
.actions { display: flex; flex-wrap: wrap; gap: var(--e-12); margin: var(--e-16) 0 }
/* Le score critère par critère : nom, jauge, points. */
.piliers { list-style: none; padding: 0; margin: var(--e-12) 0 var(--e-4) }
.piliers li { display: grid; grid-template-columns: 220px 1fr 56px; gap: var(--e-12);
              align-items: center; margin: 0; padding: var(--e-8) 0; font-size: var(--t-16) }
.p-nom { display: flex; align-items: center; gap: var(--e-8) }
.p-nom .ico { color: #2d6a4f }
.p-jauge { height: 12px; background: #ece8dd; border-radius: var(--r-6); overflow: hidden }
.p-jauge span { display: block; height: 100%; background: #3f7d53; border-radius: var(--r-6); min-width: 2px }
.p-points { text-align: right; color: #5f6a58; font-variant-numeric: tabular-nums }
.p-points b { color: #23301f }
.note-piliers { font-size: var(--t-14); margin: var(--e-4) 0 0 }
.note-piliers a { color: #2d6a4f }
@media (max-width: 560px) {
  .piliers li { grid-template-columns: 1fr 56px; row-gap: var(--e-4) }
  .p-nom { grid-column: 1 / -1 }
}
/* Les biens voisins : des liens à la couleur du site, un par ligne, séparés
   d'un filet — et non la liste à puces bleue par défaut du navigateur. */
.voisins { list-style: none; padding: 0; margin: var(--e-8) 0 }
.voisins li { margin: 0; border-bottom: 1px solid #e4e0d5 }
.voisins a { display: block; padding: var(--e-12) 0; color: #1b4332; text-decoration: none; font-weight: 600 }
.voisins a:hover { text-decoration: underline }
dl { display: grid; grid-template-columns: minmax(150px, auto) 1fr; gap: 0 var(--e-16); margin: var(--e-12) 0 }
dt, dd { padding: var(--e-8) 0; border-bottom: 1px solid #e4e0d5 }
dt { color: #5f6a58 } dd { margin: 0; font-weight: 600 }
ul { padding-left: var(--e-24) } li { margin: 3px 0 }
.faits-courts { list-style: none; padding: var(--e-16) var(--e-16); margin: var(--e-8) 0 var(--e-4); font-size: var(--t-16);
                background: #fff; border: 1px solid #e4e0d5; border-radius: var(--r-14);
                display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-8) var(--e-24) }
.faits-courts li { margin: 0; display: flex; align-items: center; gap: var(--e-8) }
.faits-courts .ico { color: #2d6a4f }
@media (max-width: 560px) { .faits-courts { grid-template-columns: 1fr } }
.jetons { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: var(--e-4) }
.jetons li { background: #e6ece1; border-radius: var(--r-pastille); padding: 3px var(--e-12); font-size: var(--t-14) }
.bouton { display: inline-flex; align-items: center; justify-content: center; gap: var(--e-8);
          background: #1b4332; color: #fff; padding: var(--e-12) var(--e-24); min-height: 48px;
          box-sizing: border-box; border: 1.5px solid #1b4332;
          border-radius: var(--r-10); text-decoration: none; font-weight: 700; margin: var(--e-4) var(--e-8) var(--e-4) 0 }
.bouton:hover { background: #2d6a4f; border-color: #2d6a4f }
.bouton.clair { background: #fff; color: #1b4332; border: 1.5px solid #1b4332 }
.bouton.clair:hover { background: #eaf2ec }
.actions .bouton { margin: 0 }
@media (max-width: 560px) { .actions .bouton { flex: 1 1 100% } }
.fil { font-size: var(--t-14); color: #5f6a58; margin-bottom: var(--e-12) }
.fil a { color: #46543f }
.note { font-size: var(--t-14); color: #5f6a58; border-top: 1px solid #ddd8cc;
        margin-top: var(--e-32); padding-top: var(--e-16) }
table { border-collapse: collapse; width: 100%; margin: var(--e-8) 0 }
td, th { text-align: left; padding: var(--e-8) var(--e-12); border-bottom: 1px solid #e4e0d5 }
img { max-width: 100%; height: auto; border-radius: var(--r-10) }
figure.aerienne { margin: var(--e-12) 0 } 
figure.aerienne img { width: 100%; border-radius: var(--r-10) }
/* Le viager n'est pas un défaut du bien : c'est un avertissement sur la
   LECTURE de son prix. D'où le ton d'alerte, juste sous le prix. */
p.viager { margin: calc(-1 * var(--e-4)) 0 var(--e-12); padding: var(--e-8) var(--e-12); border-radius: var(--r-10);
           background: #fbece8; border: 1px solid #efcdc4; color: #8c3325 }
figure.aerienne figcaption { font-size: var(--t-14); color: #5f6a58; margin-top: var(--e-4) }
.manque { color: #9a6a2b; font-style: italic }
.climat { background: #fff; border: 1px solid #e4e0d5; border-radius: var(--r-14);
          padding: var(--e-16) var(--e-16) var(--e-16); margin: var(--e-24) 0 }
.climat h2 { margin: 0 0 var(--e-12) }
.climat h3 { font-size: var(--t-16); margin: var(--e-16) 0 var(--e-4); display: flex; align-items: center; gap: var(--e-8) }
.cles-climat { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
               gap: var(--e-8) }
.cle { border-radius: var(--r-10); padding: var(--e-12) var(--e-12); background: #fbf3ec;
       border-left: 4px solid #d9622b; display: flex; flex-direction: column }
.cle.secheresse { background: #fbf6ea; border-left-color: #b5852b }
.cle b { font-size: var(--t-24); line-height: 1.1; color: #23301f; white-space: nowrap }
.cle span { font-size: var(--t-14); color: #46543f }
.cle small { font-size: var(--t-12); color: #5f6a58 }
@media (max-width: 520px) {
  .cles-climat { grid-template-columns: 1fr; gap: var(--e-4) }
  .cle { display: grid; grid-template-columns: 5.8rem 1fr; column-gap: var(--e-12); align-items: center; padding: var(--e-8) var(--e-12) }
  .cle b { grid-row: 1 / 3; font-size: var(--t-24) }
  .cle span, .cle small { grid-column: 2 }
}
.ligne-climat { padding: var(--e-8) 0; border-bottom: 1px solid #efece4 }
.ligne-climat:last-child { border-bottom: 0 }
.l-tete { display: flex; justify-content: space-between; align-items: baseline;
          gap: var(--e-8); flex-wrap: wrap }
.l-nom { font-size: var(--t-16) }
.l-nom small { color: #5f6a58 }
.l-chiffres { font-variant-numeric: tabular-nums; white-space: nowrap; font-size: var(--t-16) }
.v-ref { color: #5f6a58 }
.ecart { display: inline-block; margin-left: var(--e-4); font-size: var(--t-12); font-weight: 700;
         padding: 1px var(--e-8); border-radius: var(--r-pastille); background: #efede6; color: #5c6b60 }
.ecart.pire { background: #fbece8; color: #8c3325 }
.ecart.mieux { background: #e6f0e8; color: #1b4332 }
.barres { display: grid; gap: 3px; margin: var(--e-8) 0 3px }
.piste { height: 9px; background: #f2efe7; border-radius: var(--r-6); overflow: hidden }
.piste span { display: block; height: 100%; border-radius: var(--r-6); min-width: 2px }
.b-ref { background: #cfc8b8 }
.b-fut { background: #d9622b }
.b-fut.secheresse { background: #b5852b }
.b-fut.rr_jja { background: #3a7ca5 }
.b-fut.ifm40d { background: #b33a2a }
.rang { font-size: var(--t-14); color: #5f6a58 }
.legende-climat { font-size: var(--t-14); color: #5f6a58; margin: var(--e-12) 0 0;
                  display: flex; gap: var(--e-12); flex-wrap: wrap; align-items: center }
.legende-climat i { display: inline-block; width: 22px; height: 8px; border-radius: var(--r-6);
                    margin-right: var(--e-4); vertical-align: 1px }
.note-climat { font-size: var(--t-14); color: #5f6a58; margin: var(--e-8) 0 0; max-width: 68ch }
.pied { font-size: var(--t-14); color: #5f6a58; margin-top: var(--e-8) }
.pied a { color: #46543f }
/* Le bloc professionnel, sur fond blanc : il ne s'adresse pas au même
   visiteur que le reste du pied, et se distingue donc au lieu de se fondre
   dans la liste des mentions. */
.pied-pro { background: #fff; border: 1px solid #e2e6dc; border-radius: var(--r-10);
            padding: var(--e-12) var(--e-16); margin-top: var(--e-12); font-size: var(--t-14) }
.pied-pro a { color: #46543f; font-weight: 600; text-decoration: none }
.pied-pro a:hover { text-decoration: underline }
.engagement { background: #fff; border-left: 3px solid #46543f;
              padding: var(--e-12) var(--e-16); border-radius: 0 var(--r-10) var(--r-10) 0 }
ul.offres { list-style: none; padding: 0; display: grid; gap: var(--e-12) }
ul.offres li { background: #fff; border: 1px solid #e2e6dc; border-radius: var(--r-10);
               padding: var(--e-16) var(--e-16) }
ul.offres h3 { margin: 0 0 var(--e-4); font-size: var(--t-16) }
ul.offres p { margin: 0 0 var(--e-4) }
.modalite { font-size: var(--t-14); color: #5f6a58; font-style: italic }
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
<link rel="preload" href="/vendor/fonts/figtree.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/vendor/fonts/bricolage-grotesque.woff2" as="font" type="font/woff2" crossorigin>
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
<p class="pied"><a href="{_e(base)}{seo.URL_MENTIONS}">Mentions légales</a> ·
<a href="{_e(base)}{seo.URL_CONFIDENTIALITE}">Confidentialité</a> ·
<a href="{_e(base)}{seo.URL_METHODE}">Méthode de la note</a> ·
<a href="{_e(base)}{seo.URL_ALERTES}">Soyez alerté</a></p>
<p class="pied-pro"><a href="{_e(base)}{seo.URL_PROFESSIONNELS}">Professionnel
de l'immo ?</a></p>
</main>
<script defer src="/_vercel/insights/script.js"></script>
</body>
</html>
"""


# L'emprise, en KILOMÈTRES et non en degrés : de quoi lire le bâti, les haies
# et l'eau sans que la commune se perde dans la campagne. En kilomètres, parce
# qu'une emprise en degrés change de taille réelle selon la latitude — c'est
# la cause de la déformation décrite plus bas, et la dire en degrés la
# ramènerait par la fenêtre.
_LARGEUR_KM = 1.85
_KM_PAR_DEGRE_LAT = 111.32
# La colonne fait 760 px moins ses marges (voir `main` dans la feuille de
# style), soit ~720 px d'image. Un écran à forte densité en réclame donc
# 1 440, et c'est ce que montraient les captures : 1 280 ne suffisait pas,
# l'image restait étirée d'un dixième. 2 048 couvre le double et au-delà.
_LARGEUR_PX, _HAUTEUR_PX = 2048, 1024


# Ce que le segment DRG du référentiel SNCF veut dire, en clair.
_SEGMENT_GARE = {"A": "grande gare", "B": "gare régionale", "C": "halte"}

# Les mêmes tracés que app/static/app.js (TRACES) : deux rendus, un seul
# dessin. Ils remplacent les émojis, dont le dessin changeait d'un appareil à
# l'autre et donnait à la fiche l'allure d'un message plutôt que d'un document.
_TRACES = {
    "lieu": '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "voiture": '<path d="M4 16v-3.5l2-5.5h12l2 5.5V16M4 12.5h16"/><circle cx="7.5" cy="16.5" r="1.8"/><circle cx="16.5" cy="16.5" r="1.8"/>',
    "train": '<rect x="6" y="3" width="12" height="14" rx="3"/><path d="M6 11h12M9 21l1.5-4M15 21l-1.5-4M9.5 14h.01M14.5 14h.01"/>',
    "prix": '<path d="M17 6.5a6.5 6.5 0 1 0 0 11M4.5 10.5H13M4.5 13.5H13"/>',
    "surface": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 4v3M14 4v3M4 9h3M4 14h3"/>',
    "pieces": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 4v16M4 12h8"/>',
    "energie": '<path d="M12 3c1 3.5 5 5.5 5 10.5a5 5 0 0 1-10 0c0-2 1-3.5 2-4.5 0 2 1 3 2 3 0-3-1-6 1-9z"/>',
    "eau": '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
    "abri": '<path d="M4 20V10l8-6 8 6v10zM9.5 20v-6h5v6"/>',
    "alimentation": '<path d="M12 21v-9M12 12c0-3-2.2-5-6-5 0 3.2 2.2 5 6 5zM12 9.5c0-3 2.2-5 6-5 0 3.2-2.2 5-6 5z"/>',
    "risques": '<path d="M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z"/>',
    "chaleur": '<path d="M10 14.5V5a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/>',
    "sortie": '<path d="M14 5h5v5M19 5l-8 8M11 7H6.5A1.5 1.5 0 0 0 5 8.5v9A1.5 1.5 0 0 0 6.5 19h9a1.5 1.5 0 0 0 1.5-1.5V13"/>',
}
# redaction.bloc_de_faits désigne ses lignes par un pictogramme : la donnée
# reste ce qu'elle est (et ses tests avec), seul le dessin change au rendu.
_PICTO_VERS_ICONE = {"📍": "lieu", "💶": "prix", "📐": "surface", "🛏": "pieces",
                     "🚉": "train", "🚗": "voiture", "🛡": "risques"}
_ICONES_PILIERS = {"eau": "eau", "abri": "abri", "energie": "energie",
                   "alimentation": "alimentation", "risques": "risques",
                   "situation": "voiture"}


def _ico(nom: str) -> str:
    """Une icône au trait, décorative : le texte voisin dit toujours la chose."""
    trace = _TRACES.get(nom)
    if not trace:
        return ""
    return f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{trace}</svg>'


def _niveau(score) -> str:
    """La classe de couleur d'un score — mêmes seuils que niveauScore (app.js)."""
    score = score or 0
    return "n4" if score >= 70 else "n3" if score >= 55 else "n2" if score >= 40 else "n1"


def _virgule(nombre) -> str:
    """« 14,7 » et non « 14.7 » : la page est en français."""
    return str(nombre).replace(".", ",")


def _piliers_html(bien: dict) -> str:
    """Le score, critère par critère.

    La page servie ne montrait le score que comme une ligne de liste et une
    phrase : ce que le site a de propre — la note, et de quoi elle est faite —
    n'apparaissait dessiné que dans l'application. C'est pourtant cette page
    qu'on partage et qu'on trouve depuis un moteur de recherche.
    """
    piliers = ((bien.get("score_detail") or {}).get("piliers")) or {}
    lignes = []
    for cle, pilier in piliers.items():
        maxi = pilier.get("max") or 0
        points = pilier.get("points") or 0
        if not maxi:
            continue
        part = max(0, min(100, round(points / maxi * 100)))
        points = int(points) if float(points).is_integer() else _virgule(points)
        lignes.append(
            f'<li><span class="p-nom">{_ico(_ICONES_PILIERS.get(cle, ""))} {_e(pilier.get("libelle") or cle)}</span>'
            f'<span class="p-jauge" role="meter" aria-valuemin="0" aria-valuemax="{maxi}" '
            f'aria-valuenow="{points}" aria-label="{_e(pilier.get("libelle") or cle)}">'
            f'<span style="width:{part}%"></span></span>'
            f'<span class="p-points"><b>{points}</b>/{maxi}</span></li>')
    if not lignes:
        return ""
    return (f'<h2>Le score de résilience en détail</h2>'
            f'<ul class="piliers">{"".join(lignes)}</ul>'
            f'<p class="note-piliers"><a href="{seo.URL_METHODE}">Comment la note est calculée</a></p>')

# Deux des huit gares à grande vitesse portent « TGV » dans leur nom officiel
# (Vendôme–Villiers-sur-Loir, Le Creusot–Montceau–Montchanin), et elles pèsent
# un quart des biens concernés. Écrire « en TGV depuis Vendôme–Villiers-sur-Loir
# TGV » dirait deux fois la même chose : la phrase le dit déjà.
_SUFFIXE_TGV = re.compile(r"\s+TGV$")


def _gare_proche(bien: dict) -> str:
    """« Troyes (grande gare) à 4,8 km » — la gare, et ce qu'elle est.

    Depuis l'import du référentiel, 46 % des gares les plus proches sont des
    haltes. Écrire « gare à 2 km » sans le dire ferait passer deux trains par
    jour pour une desserte, et c'est exactement le genre de demi-vérité que
    le reste de la fiche refuse.
    """
    train = bien.get("train")
    if not isinstance(train, dict) or not train.get("nom"):
        return ""
    quoi = _SEGMENT_GARE.get(train.get("segment") or "")
    return (f"{train['nom']}{f' ({quoi})' if quoi else ''} "
            f"à {_virgule(train.get('km'))} km")


def _gare_vers_paris(bien: dict) -> str:
    """« 1 h 05 en TGV depuis Le Mans (à 15 km) » — le temps, et SA gare.

    Le référentiel ne porte aucun temps de trajet : seules les gares saisies
    à la main en ont un. La plus proche n'en fait partie que dans un cas sur
    trois, d'où la mention de la gare d'où part ce temps.
    """
    train = bien.get("train")
    if not isinstance(train, dict) or train.get("minutes_paris") is None:
        return ""
    temps = _temps(train.get("minutes_paris"))
    depuis = train.get("nom_vers_paris") or train.get("nom")
    ailleurs = bool(depuis) and depuis != train.get("nom")
    # « en TGV » répond à la question que se pose qui garde son travail à
    # Paris : non pas « y a-t-il un train ? » mais « l'aller-retour tient-il
    # dans une journée ? ». 21 % des biens au temps connu sont dans ce cas.
    vite = " en TGV" if train.get("grande_vitesse") else ""
    if vite:
        depuis = _SUFFIXE_TGV.sub("", depuis)
    if ailleurs:
        return f"{temps}{vite} depuis {depuis} (à {_virgule(train.get('km_vers_paris'))} km)"
    return f"{temps}{vite} depuis cette gare"


def _carte_aerienne(bien: dict, largeur: int = _LARGEUR_PX,
                    hauteur: int = _HAUTEUR_PX) -> str:
    """La commune vue du ciel — orthophotos IGN, Licence Ouverte.

    C'est la seule image de la fiche qui nous appartienne de plein droit, et
    la seule qui illustre ce que la page analyse : le paysage, le bâti, la
    forêt, l'eau. Elle est CADRÉE SUR LA COMMUNE, pas sur le bien — notre
    géolocalisation vient de la BAN sur commune et code postal, l'adresse
    exacte n'étant presque jamais publiée. La légende le dit en toutes
    lettres : la montrer comme la parcelle serait inventer.

    Deux défauts corrigés le 15 novembre 2026, tous deux invisibles tant
    qu'on ne mesure pas :

    **L'image était étirée.** Un degré de longitude rétrécit avec la latitude,
    un degré de latitude jamais. L'emprise était fixée en degrés — 0,024 de
    longitude sur 0,012 de latitude — ce qui fait à 47° un terrain de 1,82 km
    sur 1,34, soit un rapport de 1,36, servi dans un cadre de 2,00. Le WMS ne
    recadre pas : il étire pour remplir. Chaque commune arrivait allongée de
    moitié dans le sens est-ouest. L'emprise se dit donc maintenant en
    kilomètres, et les degrés s'en déduisent par la latitude : le rapport
    colle où qu'on soit, et la vue couvre la même étendue partout.

    **L'image était floue.** 640 pixels pour 1,8 km font 2,85 m par pixel,
    quand l'orthophoto IGN en offre 0,20 : on jetait quatorze fois le détail
    disponible, et un écran à forte densité étalait encore ce peu sur quatre
    fois la surface. La source est désormais rendue bien au-delà de sa taille
    d'affichage, soit 0,90 m par pixel — toujours loin du grain natif, mais
    c'est la commune qu'on montre, pas la parcelle, et une haie s'y distingue
    d'un talus.
    """
    lat, lon = bien.get("lat"), bien.get("lon")
    if lat is None or lon is None:
        return ""
    demi_largeur_km = _LARGEUR_KM / 2
    demi_hauteur_km = demi_largeur_km * hauteur / largeur
    # cos(lat) borné : sans cela une latitude polaire ferait diverger
    # l'emprise. Aucun bien du catalogue n'en approche, mais une fiche ne
    # doit pas dépendre de cela pour rester correcte.
    retrecissement = max(math.cos(math.radians(lat)), 0.15)
    dlon = demi_largeur_km / (_KM_PAR_DEGRE_LAT * retrecissement)
    dlat = demi_hauteur_km / _KM_PAR_DEGRE_LAT
    bbox = f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}"
    return ("https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0"
            "&REQUEST=GetMap&LAYERS=ORTHOIMAGERY.ORTHOPHOTOS&STYLES="
            f"&FORMAT=image/jpeg&CRS=CRS:84&BBOX={bbox}"
            f"&WIDTH={largeur}&HEIGHT={hauteur}")


def climat_html(v: dict | None) -> str:
    """Le climat de 2050, dessiné : chiffres clés, puis par thème une ligne
    par indicateur — valeurs, écart, deux barres (1976-2005, 2050) sur
    l'échelle commune à la zone, et le rang de la maille. Le contenu vient de
    climat.vue ; app/static/app.js dessine le même pour la carte."""
    if not v:
        return ""
    cles = "".join(
        f'<div class="cle {_e(c["theme"])}"><b>{_e(c["valeur"])}</b>'
        f'<span>{_e(c["titre"])}</span><small>{_e(c["detail"])}</small></div>'
        for c in v["cles"])
    themes = []
    for t in v["themes"]:
        lignes = []
        for ligne in t["lignes"]:
            barres = ""
            if ligne["barre_horizon"] is not None:
                ref = ("" if ligne["barre_reference"] is None else
                       f'<div class="piste"><span class="b-ref" '
                       f'style="width:{ligne["barre_reference"]}%"></span></div>')
                barres = (f'<div class="barres" aria-hidden="true">{ref}'
                          f'<div class="piste"><span class="b-fut {_e(t["code"])} {_e(ligne["code"])}" '
                          f'style="width:{ligne["barre_horizon"]}%"></span></div></div>')
            avant = (f'<span class="v-ref">{_e(ligne["reference"])}</span> → '
                     if ligne["reference"] else "")
            ecart = (f'<span class="ecart {_e(ligne["sens"])}">{_e(ligne["ecart"])}</span>'
                     if ligne["ecart"] else "")
            unite = f' <small>{_e(ligne["unite"])}</small>' if ligne["unite"] else ""
            rang = f'<div class="rang">{_e(ligne["rang"])}</div>' if ligne["rang"] else ""
            lignes.append(
                f'<div class="ligne-climat"><div class="l-tete">'
                f'<span class="l-nom">{_e(ligne["libelle"])}{unite}</span>'
                f'<span class="l-chiffres">{avant}<b>{_e(ligne["horizon"])}</b>{ecart}</span>'
                f'</div>{barres}{rang}</div>')
        themes.append(f'<h3>{_ico("chaleur" if t.get("code") == "chaleur" else "eau")} '
                      f'{_e(t["nom"])}</h3>{"".join(lignes)}')
    legende = (f'<p class="legende-climat"><span><i class="b-ref"></i>{_e(v["legende"][0])}</span>'
               f'<span><i class="b-fut"></i>{_e(v["legende"][1])}</span></p>')
    return (f'<section class="climat"><h2>{_e(v["titre"])}</h2>'
            f'<div class="cles-climat">{cles}</div>{"".join(themes)}{legende}'
            f'<p class="note-climat">{_e(v["note"])}</p></section>')


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
            # Deux faits, deux lignes. Les réunir attribuait à la gare la
            # plus proche un temps qui, deux fois sur trois, est celui d'une
            # autre — depuis que le référentiel SNCF a remplacé les 41 gares
            # saisies à la main, la plus proche est souvent une halte.
            ("Gare la plus proche", _gare_proche(bien)),
            ("Paris en train", _gare_vers_paris(bien)),
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

    # Les faits avant la prose : on veut d'abord savoir SI l'on continue à
    # lire. Voir redaction.bloc_de_faits.
    faits_courts = "".join(
        f'<li>{_ico(_PICTO_VERS_ICONE.get(picto, ""))} {_e(texte)}</li>'
        for picto, texte in redaction.bloc_de_faits(bien))

    suite = "".join(
        f'<li><a href="{_e(base + seo.url_annonce(v))}">{_e(seo.titre_annonce(v))}</a></li>'
        for v in voisins[:8])

    # Les deux actions de la page. Elles n'existaient qu'en bas, sous quatre
    # mille pixels d'analyse et de projections climatiques : qui venait pour
    # l'annonce devait tout faire défiler pour la trouver. Elles sont donc
    # AUSSI en tête — la section « Comment visiter ce bien ? » garde les
    # siennes, avec l'explication qui les accompagne.
    actions = (
        (f'<a class="bouton" href="{_e(bien.get("url"))}" rel="nofollow noopener">'
         f'Voir l’annonce chez {_e(bien.get("agence") or "l’agence")} {_ico("sortie")}</a>'
         if bien.get("url") else "")
        + f'<a class="bouton clair" href="{_e(base)}/?bien={_e(bien.get("id"))}">'
          f'Ouvrir la carte et les filtres</a>')

    score = bien.get("score_total")
    classe = (bien.get("score_detail") or {}).get("classe") or ""
    bloc_score = (
        f'<div class="score-bloc {_niveau(score)}" title="Score de résilience">'
        f'<b>{round(score)}</b><i>/100</i><small>résilience</small></div>'
    ) if score else ""

    # Le climat de 2050 : projections DRIAS de la maille la plus proche. La
    # section n'existe que si les données existent — voir app/climat.py.
    projection = climat.au_point(bien.get("lat"), bien.get("lon"))
    bloc_climat = climat_html(climat.vue(projection))

    corps = f"""
<nav class="fil">{" › ".join(
    f'<a href="{_e(base + lien)}">{_e(nom)}</a>' if rang < len(fil) else _e(nom)
    for rang, (nom, lien) in enumerate(fil, start=1))}</nav>

<h1>{_e(seo.titre_annonce(bien))}</h1>
<p class="chapeau">{_e(seo.description_annonce(bien))}</p>
{f'<img src="{_e(bien["photo"])}" alt="{_e(seo.titre_annonce(bien))}" loading="lazy" onerror="this.remove()">' if bien.get("photo") else ""}
<div class="resume">
<div class="resume-texte">
<p class="prix">{_e(seo._euros(bien.get("prix")) or "Prix sur demande")}</p>
{f'<p class="classe-score">{_e(classe)}</p>' if classe else ""}
</div>
{bloc_score}
</div>
{'<p class="viager">Vente en viager : le prix affiché est le <b>bouquet</b>, '
 'pas la valeur du bien. Le prix au m² et la comparaison au marché local ne '
 'valent donc pas pour cette annonce.</p>' if bien.get("viager") else ""}
<p class="actions">{actions}</p>
{f'<ul class="faits-courts">{faits_courts}</ul>' if faits_courts else ""}

<h2>Que disent les données sur ce bien ?</h2>
{prose}
{aerienne}

{_piliers_html(bien)}

<h2>Caractéristiques et analyse en bref</h2>
<dl>{"".join(faits)}{"".join(analyse)}</dl>
{f'<ul class="jetons">{badges}</ul>' if badges else ""}

{bloc_climat}

<h2>Comment visiter ce bien ?</h2>
<p>L'annonce est publiée par <strong>{_e(bien.get("agence") or "une agence partenaire")}</strong>.
Refuge Immo ne prend pas de mandat : la visite et la transaction se font
directement avec elle.</p>
<p class="actions">{actions}</p>
{f'<p class="note">Annonce vérifiée en ligne le {_e(bien.get("revue_le"))}. Un bien peut avoir été vendu depuis.</p>' if bien.get("revue_le") else ""}

{f'<h2>Autres biens du même terroir</h2><ul class="voisins">{suite}</ul>' if suite else ""}
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

<h2>Voir aussi</h2>
<ul>
<li><a href="{_e(base + seo.URL_SANS_TRAVAUX)}">Maisons sans travaux entre {_e(seo._tranche_sans_travaux())}</a>
 — la tranche du dessus, celle des biens dont l'annonce dit qu'ils sont prêts.</li>
</ul>

<h2>Chercher par terroir</h2>
<ul>{terroirs}</ul>
"""
    structure = _jsonld(
        seo.jsonld_liste(biens[:60], base),
        seo.jsonld_fil([("Accueil", "/"),
                        (f"Maisons sous {seuil}", seo.URL_PETITS_PRIX)], base),
        seo.jsonld_organisation(base))
    return _document(titre, description, canonique, corps, structure, base)


def page_sans_travaux(biens: list[dict], stats: dict,
                      base: str = seo.SITE) -> str:
    """Les biens d'une tranche de prix dont l'annonce dit qu'ils sont prêts.

    Tous les portails proposent un filtre « sans travaux ». Il repose sur une
    case que le vendeur coche lui-même, et que personne ne vérifie. Nous
    n'avons pas de case : nous avons le texte des annonces, et ne retenons que
    celles qui l'affirment — « habitable de suite », « aucun travaux à
    prévoir », « entièrement rénovée ».

    Ce qui distingue cette page n'est donc pas sa liste, c'est son aveu : la
    plupart des annonces ne disent rien de leur état, et une annonce muette
    n'est pas une bonne nouvelle. La page l'écrit dès le chapeau plutôt que de
    gonfler sa liste en comptant le silence comme une promesse. C'est aussi ce
    qui la rend citable : elle est la seule à dire ce qu'elle ignore.
    """
    canonique = f"{base}{seo.URL_SANS_TRAVAUX}"
    titre = seo.titre_sans_travaux(len(biens))
    description = seo.description_sans_travaux(
        len(biens), stats.get("bien_notes", 0), stats.get("prix_median"))
    reponse = seo.reponse_sans_travaux(
        len(biens), stats.get("dans_la_tranche", 0), stats.get("muettes", 0),
        stats.get("communes", 0), stats.get("prix_median"),
        stats.get("bien_notes", 0))

    lignes = "".join(
        f'<tr><td><a href="{_e(base + seo.url_annonce(b))}">'
        f'{_e(seo.titre_annonce(b))}</a></td>'
        f'<td>{_e(seo._euros(b.get("prix")))}</td>'
        f'<td>{_e(round(b["score_total"]) if b.get("score_total") else "—")}</td></tr>'
        for b in biens[:60])

    terroirs = "".join(
        f'<li><a href="{_e(base + seo.url_terroir(r))}">'
        f'{_e(seo.TERROIRS[r]["cherche"])}</a></li>' for r in seo.TERROIRS)

    tranche = seo._tranche_sans_travaux()
    # Le lien vers la carte ne porte que la borne HAUTE : le filtre de
    # l'accueil n'a pas de plancher, et lui en inventer un ferait promettre au
    # bouton une liste qu'il ne montrerait pas.
    vers_la_carte = f"{_e(base)}/?prix_max={seo.PLAFOND_SANS_TRAVAUX}"
    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Maisons sans travaux</nav>

<h1>Maisons sans travaux entre {_e(tranche)}, classées par résilience</h1>
<p class="chapeau">{_e(reponse)}</p>

<p>
<a class="bouton" href="{vers_la_carte}">Voir les biens de cette tranche sur la carte</a>
</p>

<h2>Ce que contient cette sélection</h2>
<table>
<tr><th>Biens annoncés sans travaux</th><td>{len(biens)}</td></tr>
<tr><th>Biens dans cette tranche de prix</th><td>{_e(stats.get("dans_la_tranche", 0))}</td></tr>
<tr><th>Annonces muettes sur l'état</th><td>{_e(stats.get("muettes", 0))}</td></tr>
<tr><th>Annonces qui signalent des travaux</th><td>{_e(stats.get("avec_travaux", 0))}</td></tr>
<tr><th>Communes couvertes</th><td>{_e(stats.get("communes", 0))}</td></tr>
{f'<tr><th>Prix médian de la sélection</th><td>{_e(seo._euros(stats["prix_median"]))}</td></tr>' if stats.get("prix_median") else ""}
{f'<tr><th>Surface médiane</th><td>{_e(round(stats["surface_mediane"]))} m²</td></tr>' if stats.get("surface_mediane") else ""}
<tr><th>Notés 40 sur 100 ou plus</th><td>{_e(stats.get("bien_notes", 0))}</td></tr>
</table>

<h2>Comment ces biens ont été retenus</h2>
<p>Aucune case n'a été cochée par personne. Chaque annonce de la tranche a été
lue, et seules ont été retenues celles qui <strong>affirment</strong> que le
bien est prêt : « aucun travaux à prévoir », « habitable de suite »,
« entièrement rénovée », « en bon état général ». Sont écartées celles qui
annoncent des travaux — « à rénover », « travaux à prévoir », « projet de
rénovation » — et celles qui n'en disent rien.</p>
<p>Deux précautions ont demandé plus de soin que le reste. « Pas de travaux à
prévoir » contient mot pour mot la formule qui annonce des travaux : la
lecture traite donc la négation avant de conclure. Et « toiture en bon état »
ne vaut pas pour le bien entier — on ne vante le gros œuvre que lorsque le
second œuvre est à refaire.</p>

<h2>Ce que cette page ne sait pas</h2>
<p>Sur les {_e(stats.get("dans_la_tranche", 0))} biens de la tranche,
{_e(stats.get("muettes", 0))} annonces ne disent rien de l'état du logement.
Elles ne sont pas ici, et ce n'est pas un jugement : parmi elles se trouvent
certainement des maisons parfaitement prêtes, dont l'agence n'a pas jugé utile
de l'écrire. Une page qui les aurait ajoutées serait plus fournie et moins
vraie.</p>
<p>« Sans travaux » reste la parole de l'agence, relevée dans son annonce. Ce
n'est pas un constat fait sur place : cela ne remplace ni une visite, ni les
diagnostics obligatoires, ni un devis. Le mot recouvre d'ailleurs des réalités
très différentes — un logement habitable en l'état n'est pas un logement
isolé, et l'étiquette énergétique dit souvent le contraire du confort.</p>

<h2>Les biens, du mieux noté au moins bien noté</h2>
<table>
<tr><th>Bien</th><th>Prix</th><th>Résilience</th></tr>
{lignes}
</table>
{f'<p>… et {len(biens) - 60} autres, à parcourir sur <a href="{vers_la_carte}">la carte</a>.</p>' if len(biens) > 60 else ""}

<h2>Voir aussi</h2>
<ul>
<li><a href="{_e(base + seo.URL_PETITS_PRIX)}">Maisons sous {_e(seo._euros(seo.SEUIL_PETITS_PRIX))}</a>
 — la tranche du dessous, où les travaux sont presque toujours de la partie.</li>
</ul>

<h2>Chercher par terroir</h2>
<ul>{terroirs}</ul>
"""
    structure = _jsonld(
        seo.jsonld_liste(biens[:60], base),
        seo.jsonld_fil([("Accueil", "/"),
                        ("Maisons sans travaux", seo.URL_SANS_TRAVAUX)], base),
        seo.jsonld_organisation(base))
    return _document(titre, description, canonique, corps, structure, base)


def page_alertes(stats: dict, prix_choisi: int | None = None,
                 region_choisie: str = "", base: str = seo.SITE,
                 api_active: bool = False) -> str:
    """« Soyez alerté » — le visiteur choisit, personne ne choisit pour lui.

    Cette page remplace le bloc de mise en relation, retiré le 17 août 2026.
    Celui-ci recueillait l'e-mail du visiteur pour le transmettre à l'agence,
    contre rémunération : prêter son concours, même accessoire et même
    rémunéré indirectement, à la recherche d'un immeuble pour autrui est
    l'activité que la loi Hoguet réserve aux titulaires d'une carte
    professionnelle. Écrire « nous ne sommes pas une agence » ne défait pas ce
    qui est fait.

    La différence n'est donc pas cosmétique, et la page doit la porter :

    - le visiteur fixe LUI-MÊME son budget et ses terroirs ; nous ne
      sélectionnons rien pour lui et ne conseillons aucun bien ;
    - son adresse ne part chez personne — surtout pas chez une agence ;
    - aucune commission n'est perçue, à aucun moment ;
    - le lien vers l'annonce d'origine reste le seul chemin vers le vendeur.

    Rien n'est enregistré sur le serveur : le formulaire ouvre le logiciel de
    courrier du visiteur avec ses critères déjà écrits, et c'est lui qui
    envoie. Ce n'est pas une élégance technique, c'est la seule option
    honnête — l'hébergement n'a pas de stockage durable, et le dispositif
    précédent recueillait des adresses dans un fichier temporaire effacé à
    chaque redémarrage. Recueillir une donnée personnelle pour la perdre est
    pire que ne pas la recueillir.
    """
    canonique = f"{base}{seo.URL_ALERTES}"
    titre = "Soyez alerté des maisons qui entrent au catalogue"
    description = (
        "Choisissez un budget et des terroirs : nous vous prévenons quand une "
        "maison résiliente y entre au catalogue. Gratuit, sans mise en "
        "relation, sans commission.")

    paliers = "".join(
        f'<option value="{p}"{" selected" if prix_choisi == p else ""}>'
        f'Jusqu\'à {_e(seo._euros(p))}</option>' for p in seo.PALIERS_ALERTE)
    terroirs = "".join(
        f'<label class="case"><input type="checkbox" name="terroir" '
        f'value="{_e(region)}"{" checked" if region == region_choisie else ""}> '
        f'{_e(seo.TERROIRS[region]["cherche"])}</label>' for region in seo.TERROIRS)

    formulaire_api = f"""
<form id="form-alerte" class="alerte-form">
  <label class="champ"><span>Mon budget maximum</span>
    <select id="alerte-prix">{paliers}</select></label>
  <fieldset class="champ"><legend>Les terroirs qui m'intéressent</legend>
    {terroirs}</fieldset>
  <label class="champ"><span>Mon adresse e-mail</span>
    <input type="email" id="alerte-mail" placeholder="vous@exemple.fr"
           autocomplete="email" required></label>
  <button class="bouton" type="submit">Créer mon alerte</button>
  <p class="alerte-note" id="alerte-note">Vous recevrez un unique courriel
    d'activation : sans clic de votre part, rien ne sera envoyé et l'adresse
    ne sera pas conservée active. Chaque alerte contient son lien de
    désinscription — effacement immédiat, sans condition.</p>
</form>
<script>
(function () {{
  var f = document.getElementById("form-alerte");
  if (!f) return;
  f.addEventListener("submit", function (e) {{
    e.preventDefault();
    var note = document.getElementById("alerte-note");
    var mail = (document.getElementById("alerte-mail").value || "").trim();
    var zones = [].slice.call(f.querySelectorAll("input[name=terroir]:checked"))
                  .map(function (c) {{ return c.value; }});
    if (!zones.length) {{ note.textContent = "Choisissez au moins un terroir."; return; }}
    note.textContent = "Enregistrement…";
    fetch("/api/alertes", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ email: mail, terroirs: zones,
        prix_max: parseInt(document.getElementById("alerte-prix").value, 10) || null }}),
    }}).then(function (r) {{
      if (r.ok) {{
        note.textContent = "Un courriel d'activation vient de partir : "
          + "ouvrez-le et cliquez le lien pour démarrer l'alerte.";
        f.querySelector("button").disabled = true;
      }} else {{
        return r.json().then(function (d) {{
          note.textContent = (d && d.detail) || "L'enregistrement a échoué. Réessayez.";
        }});
      }}
    }}).catch(function () {{ note.textContent = "L'enregistrement a échoué. Réessayez."; }});
  }});
}})();
</script>"""

    ouvert = bool(seo.COURRIEL_ALERTES)
    envoi = (f"""
<form id="form-alerte" class="alerte-form">
  <label class="champ"><span>Mon budget maximum</span>
    <select id="alerte-prix">{paliers}</select></label>
  <fieldset class="champ"><legend>Les terroirs qui m'intéressent</legend>
    {terroirs}</fieldset>
  <label class="champ"><span>Mon adresse e-mail</span>
    <input type="email" id="alerte-mail" placeholder="vous@exemple.fr"
           autocomplete="email" required></label>
  <button class="bouton" type="submit">Créer mon alerte</button>
  <p class="alerte-note" id="alerte-note"></p>
</form>
<script>
// Rien ne part vers ce site : le formulaire ouvre le logiciel de courrier du
// visiteur avec ses critères déjà écrits. Aucune adresse n'est enregistrée
// ici, donc aucune ne peut être perdue ni transmise.
(function () {{
  var f = document.getElementById("form-alerte");
  if (!f) return;
  f.addEventListener("submit", function (e) {{
    e.preventDefault();
    var mail = (document.getElementById("alerte-mail").value || "").trim();
    var note = document.getElementById("alerte-note");
    if (mail.indexOf("@") < 0) {{
      note.textContent = "Indiquez une adresse e-mail valide.";
      return;
    }}
    var prix = document.getElementById("alerte-prix").value;
    var zones = [].slice.call(f.querySelectorAll("input[name=terroir]:checked"))
                  .map(function (c) {{ return c.value; }});
    if (!zones.length) {{
      note.textContent = "Choisissez au moins un terroir.";
      return;
    }}
    var corps = "Bonjour,\\n\\nJe souhaite être alerté des nouvelles maisons :\\n"
      + "\\n- budget maximum : " + prix + " EUR"
      + "\\n- terroirs : " + zones.join(", ")
      + "\\n- mon adresse : " + mail
      + "\\n\\nMerci.";
    note.textContent = "Votre logiciel de courrier s'ouvre avec votre demande. "
      + "Il ne reste qu'à l'envoyer.";
    window.location.href = "mailto:{seo.COURRIEL_ALERTES}"
      + "?subject=" + encodeURIComponent("Alerte Refuge Immo")
      + "&body=" + encodeURIComponent(corps);
  }});
}})();
</script>""" if ouvert else """
<p class="alerte-note"><strong>Les alertes ne sont pas encore ouvertes.</strong>
Plutôt que de recueillir votre adresse pour la perdre — c'est ce que faisait le
dispositif précédent, dont le journal vivait dans un fichier temporaire effacé
à chaque redémarrage — cette page attend d'avoir une boîte qui les reçoive
vraiment. En attendant, le lien ci-dessous garde vos critères : mettez-le en
favori, la liste s'y met à jour toute seule.</p>""")

    if api_active:
        envoi = formulaire_api

    lien_carte = f"{_e(base)}/?prix_max={prix_choisi or seo.PALIERS_ALERTE[1]}"
    if region_choisie:
        lien_carte += f"&region={_e(region_choisie)}"

    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Soyez alerté</nav>

<h1>Soyez alerté des maisons qui entrent au catalogue</h1>
<p class="chapeau">Choisissez un budget et les terroirs qui vous intéressent.
Quand une maison y entre, nous vous écrivons. C'est tout : nous ne vous mettons
en relation avec personne, nous ne transmettons votre adresse à aucune agence,
et nous ne touchons aucune commission.</p>

{envoi}

<p><a class="bouton clair" href="{lien_carte}">Voir dès maintenant ce qui correspond</a></p>

<h2>Ce que nous faisons, et ce que nous ne faisons pas</h2>
<table>
<tr><th>Vous choisissez vos critères</th><td>oui — nous n'en fixons aucun à votre place</td></tr>
<tr><th>Votre adresse est transmise à une agence</th><td>non, jamais</td></tr>
<tr><th>Nous vous proposons une sélection personnalisée</th><td>non : la même liste que le site, filtrée par vos critères</td></tr>
<tr><th>Nous organisons des visites ou négocions</th><td>non</td></tr>
<tr><th>Nous touchons une commission</th><td>non, ni de vous ni de l'agence</td></tr>
<tr><th>Vous contactez le vendeur</th><td>vous-même, par le lien vers l'annonce d'origine</td></tr>
</table>
<p>Cette page a remplacé un bloc « recevez les photos, soyez recontacté » qui,
lui, recueillait votre adresse pour la transmettre à l'agence et rémunérait le
site à la mise en relation. C'était une activité d'entremise, que la loi
réserve aux titulaires d'une carte professionnelle. Nous ne l'exerçons pas.</p>

<h2>Votre adresse e-mail</h2>
<p>Elle ne sert qu'à vous envoyer les alertes que vous avez demandées. Elle
n'est ni revendue, ni transmise à une agence, ni utilisée pour autre chose.
Vous pouvez demander son effacement à tout moment, par simple réponse à l'un
de nos courriers — et l'effacement est immédiat et sans condition.</p>

<h2>Ce que l'alerte ne vous dit pas</h2>
<p>Une alerte signale qu'une annonce est <em>entrée au catalogue</em>, pas
qu'elle est encore disponible : ce sont des annonces publiées par des agences,
relevées automatiquement, et un bien peut être vendu avant que nous le
sachions. La date de dernière vérification figure sur chaque fiche. Le prix,
la surface et les caractéristiques sont ceux annoncés par l'agence, que nous ne
vérifions pas sur place.</p>

<h2>Chercher tout de suite</h2>
<ul>
<li><a href="{_e(base + seo.URL_PETITS_PRIX)}">Maisons sous {_e(seo._euros(seo.SEUIL_PETITS_PRIX))}</a></li>
<li><a href="{_e(base + seo.URL_SANS_TRAVAUX)}">Maisons sans travaux entre {_e(seo._tranche_sans_travaux())}</a></li>
</ul>
"""
    structure = _jsonld(
        seo.jsonld_fil([("Accueil", "/"), ("Soyez alerté", seo.URL_ALERTES)], base),
        seo.jsonld_organisation(base))
    return _document(titre, description, canonique, corps, structure, base)


def _ligne(etiquette: str, valeur: str, manque: str = "") -> str:
    """Une ligne d'identité — ou l'aveu franc qu'elle manque encore.

    Une mention légale approximative est pire qu'une mention légale
    incomplète : elle a l'air complète, et personne ne la corrige.
    """
    if valeur:
        return f"<tr><th>{_e(etiquette)}</th><td>{_e(valeur)}</td></tr>"
    return (f'<tr><th>{_e(etiquette)}</th>'
            f'<td class="manque">{_e(manque or "à compléter")}</td></tr>')


def page_mentions_legales(base: str = seo.SITE) -> str:
    """Qui édite ce site, qui en répond, et où le joindre.

    La loi impose que l'éditeur d'un service en ligne puisse être identifié et
    joint. Le site n'affichait rien de tel : une agence dont l'annonce est
    reprise, ou une personne voulant exercer un droit sur ses données, n'avait
    aucune porte à laquelle frapper. « Refuge Immo n'est pas une agence » n'est
    pas une identité, et une clause d'exclusion n'a jamais tenu lieu de
    mentions légales.

    La page dit aussi ce que le service EST et n'est pas — non par prudence
    rédactionnelle, mais parce que la qualification juridique dépend de ce
    qu'on fait, jamais de ce qu'on déclare.
    """
    e, h = seo.EDITEUR, seo.HEBERGEUR
    # Une porte ouverte tant que le courriel n'existe pas : les mentions
    # promettent le retrait « sans discussion et sans délai », et une promesse
    # sans destination ne vaut rien.
    provisoire = "" if e["courriel"] else (
        "<p>L'adresse postale et le courriel de contact seront publiés dès "
        "l'ouverture de la domiciliation et du nom de domaine. En attendant, "
        "et pour qu'aucune demande ne reste sans destinataire, toute "
        "sollicitation — retrait d'annonces, exercice d'un droit sur vos "
        "données, signalement d'une erreur — peut être déposée publiquement "
        f'ici : <a href="{_e(seo.CONTACT_PROVISOIRE)}" rel="noopener">'
        f"{_e(seo.CONTACT_PROVISOIRE)}</a>. Les demandes y sont horodatées et "
        "consultables par tous.</p>")
    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Mentions légales</nav>

<h1>Mentions légales</h1>

<h2>Éditeur du site</h2>
<table>
{_ligne("Éditeur", e["nom"])}
{_ligne("Forme juridique", e["forme"])}
{_ligne("SIREN", seo.siren_lisible())}
{_ligne("Adresse", e["adresse"])}
{_ligne("Contact", e["courriel"], "en cours d'ouverture — voir ci-dessous")}
{_ligne("Directeur de la publication", e["directeur"])}
</table>
{provisoire}

<h2>Hébergeur</h2>
<table>
{_ligne("Hébergeur", h["nom"])}
{_ligne("Adresse", h["adresse"])}
{_ligne("Site", h["site"])}
</table>

<h2>Ce que ce site fait, et ce qu'il ne fait pas</h2>
<p>{seo.NOM} recense des annonces immobilières publiées par des agences et des
réseaux de mandataires, et leur attribue une note de résilience calculée à
partir de données publiques. Chaque fiche renvoie vers l'annonce d'origine.</p>
<table>
<tr><th>Vend ou loue des biens</th><td>non</td></tr>
<tr><th>Détient un mandat</th><td>non, aucun</td></tr>
<tr><th>Met en relation acheteur et vendeur</th><td>non</td></tr>
<tr><th>Transmet vos coordonnées à une agence</th><td>non, jamais</td></tr>
<tr><th>Perçoit une commission</th><td>non</td></tr>
<tr><th>Organise des visites, négocie, rédige des actes</th><td>non</td></tr>
</table>
<p>Ces lignes ne sont pas une clause d'exclusion : elles décrivent le service
réellement rendu. Un dispositif de mise en relation rémunéré, qui existait
jusqu'au 17 août 2026, a été retiré précisément parce qu'il ne correspondait
plus à cette description — recueillir les coordonnées d'un acheteur pour les
transmettre à une agence contre rémunération relève de l'entremise
immobilière, réservée aux titulaires d'une carte professionnelle.</p>

<h2>Annonces : origine, fraîcheur et retrait</h2>
<p>Les annonces proviennent des sites des agences et des réseaux qui les
publient. Nous n'en reprenons que des <strong>faits</strong> — prix, surface,
nombre de pièces, terrain, commune, étiquette énergétique — et le lien vers la
page d'origine. Le texte de vente rédigé par l'agence n'est pas republié, ni
sur les pages ni dans notre interface programmable. Notre robot se présente
sous le nom <code>RefugeImmoBot</code> : <a href="{_e(base + seo.URL_ROBOT)}">la
page qui le décrit</a> dit ce qu'il retient et comment le bloquer.</p>
<p>Les photographies restent hébergées chez l'agence et sont affichées depuis
ses serveurs : elle voit ce trafic et peut nous en empêcher d'un réglage.</p>
<p>Un prix, une surface ou une disponibilité peuvent avoir changé depuis notre
dernier passage. La date de dernière vérification figure sur chaque fiche.
<strong>Rien de ce que nous affichons ne vaut engagement</strong> : seule
l'annonce d'origine fait foi.</p>
<p><strong>Vous êtes une agence et souhaitez le retrait de vos annonces ?</strong>
Écrivez à l'adresse de contact ci-dessus : le retrait est effectué sans
discussion et sans délai, et le
site est ajouté à une liste d'exclusion pour que la collecte n'y revienne pas.
Aucune justification n'est demandée.</p>

<h2>Note de résilience</h2>
<p>La note est un <strong>indicateur éditorial</strong> construit par nos soins
à partir de données publiques. Ce n'est ni un diagnostic immobilier, ni une
expertise technique, ni une garantie de sécurité, d'habitabilité ou de valeur
future. Les risques recensés valent pour la <strong>commune</strong> et non
pour la parcelle : ils ne remplacent pas l'état des risques, obligatoire à la
vente.</p>

<h2>Propriété intellectuelle</h2>
<p>La note de résilience, son barème, les textes de présentation et les pages
d'analyse sont notre travail. Les annonces, leurs textes et leurs
photographies appartiennent à leurs auteurs et à leurs ayants droit.</p>

<h2>Données personnelles</h2>
<p>Voir la <a href="{_e(base + seo.URL_CONFIDENTIALITE)}">politique de
confidentialité</a>.</p>
"""
    return _document(
        "Mentions légales", f"Éditeur, hébergeur et cadre juridique de {seo.NOM}.",
        f"{base}{seo.URL_MENTIONS}", corps,
        _jsonld(seo.jsonld_fil([("Accueil", "/"),
                                ("Mentions légales", seo.URL_MENTIONS)], base)),
        base)


def page_confidentialite(base: str = seo.SITE) -> str:
    """Ce que le site fait — et surtout ne fait pas — de vos données.

    La page la plus courte possible, parce que le traitement l'est : à ce jour
    le site ne demande rien, ne dépose aucun traceur de mesure d'audience et
    n'a aucun compte. Écrire une politique bavarde décrivant des traitements
    qui n'existent pas serait aussi trompeur qu'en omettre.
    """
    e = seo.EDITEUR
    alertes_ouvertes = bool(seo.COURRIEL_ALERTES)
    provisoire = "" if e["courriel"] else (
        "<p>En attendant l'ouverture du courriel, toute demande relative à vos "
        f'données peut être déposée ici : <a href="{_e(seo.CONTACT_PROVISOIRE)}" '
        f'rel="noopener">{_e(seo.CONTACT_PROVISOIRE)}</a>. N\'y écrivez aucune '
        "donnée sensible : la page est publique.</p>")
    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Confidentialité</nav>

<h1>Politique de confidentialité</h1>
<p class="chapeau">Le site ne vous demande rien pour être consulté : ni compte,
ni inscription, ni adresse. Cette page dit ce qui est traité malgré tout, et
par qui.</p>

<h2>Responsable du traitement</h2>
<table>
{_ligne("Responsable", e["nom"])}
{_ligne("SIREN", seo.siren_lisible())}
{_ligne("Adresse", e["adresse"])}
{_ligne("Contact", e["courriel"], "en cours d'ouverture")}
</table>
{provisoire}

<h2>Ce que nous ne faisons pas</h2>
<ul>
<li>Aucun compte, aucun identifiant, aucun mot de passe.</li>
<li>Aucune régie publicitaire, aucun pixel de réseau social.</li>
<li>Aucune revente, aucune location, aucun partage de données à des tiers
à des fins commerciales.</li>
<li>Aucun profilage, aucune décision automatisée vous concernant.</li>
</ul>

<h2>Ce qui est traité</h2>
<table>
<tr><th>Donnée</th><th>Pourquoi</th><th>Combien de temps</th></tr>
<tr><td>Adresse IP et journaux techniques</td>
    <td>Faire fonctionner le site et le protéger des abus. Ces journaux sont
        tenus par l'hébergeur, non par nous.</td>
    <td>Selon la politique de l'hébergeur</td></tr>
<tr><td>Vos filtres de recherche</td>
    <td>Ils voyagent dans l'adresse de la page et restent dans votre
        navigateur. Ils ne nous parviennent pas sous une forme qui vous
        désigne.</td>
    <td>Non conservés</td></tr>
<tr><td>Pages vues</td>
    <td>Mesure de fréquentation de l'hébergeur (Vercel Web Analytics), sans
        cookie ni identifiant durable : elle compte les visites sans suivre
        le visiteur, ni ici ni ailleurs.</td>
    <td>Statistiques agrégées</td></tr>
<tr><td>Adresse e-mail d'alerte</td>
    <td>{"Vous envoyer les alertes que vous avez demandées, et rien d'autre."
        if alertes_ouvertes else
        "Aucune n'est recueillie : les alertes ne sont pas encore ouvertes."}</td>
    <td>{"Jusqu'à votre demande d'arrêt" if alertes_ouvertes else "—"}</td></tr>
</table>

<h2>Cookies et traceurs</h2>
<p>Le site ne dépose <strong>aucun cookie de mesure d'audience, de publicité
ou de réseau social</strong>. Il n'y a donc pas de bandeau de consentement à
afficher : il n'y a rien à consentir.</p>
<p>Deux services extérieurs sont sollicités par votre navigateur quand vous
consultez une fiche, et ils voient de ce fait votre adresse IP :</p>
<ul>
<li><strong>Les photographies</strong>, qui restent hébergées chez l'agence
qui publie l'annonce.</li>
<li><strong>Les fonds de carte et les vues aériennes</strong>, servis par
l'IGN et par les serveurs de tuiles cartographiques.</li>
</ul>

<h2>Vos droits</h2>
<p>Vous disposez d'un droit d'accès, de rectification, d'effacement,
d'opposition et de portabilité. Pour l'exercer, écrivez à l'adresse de contact
ci-dessus. S'agissant d'une alerte e-mail, l'effacement est immédiat et sans
condition — une simple réponse à l'un de nos courriers suffit.</p>
<p>Vous pouvez également introduire une réclamation auprès de la Commission
nationale de l'informatique et des libertés (CNIL), 3 place de Fontenoy,
75007 Paris — <a href="https://www.cnil.fr" rel="noopener">cnil.fr</a>.</p>

<h2>Vous êtes une agence</h2>
<p>Le nom de votre agence et le lien vers vos annonces figurent sur ce site.
Pour en demander le retrait, voir les
<a href="{_e(base + seo.URL_MENTIONS)}">mentions légales</a> : c'est fait sans
discussion et sans délai.</p>
"""
    return _document(
        "Politique de confidentialité",
        f"Ce que {seo.NOM} traite comme données, pourquoi, et vos droits.",
        f"{base}{seo.URL_CONFIDENTIALITE}", corps,
        _jsonld(seo.jsonld_fil([("Accueil", "/"),
                                ("Confidentialité", seo.URL_CONFIDENTIALITE)], base)),
        base)


def page_methode(base: str = seo.SITE) -> str:
    """Ce que la note mesure, d'où viennent ses données, et ce qu'elle ignore.

    Le strict nécessaire, volontairement. La note est ce que ce site apporte
    de propre : publier la formule et ses coefficients reviendrait à la
    donner. Ce que la loi exige n'est pas la formule — c'est que l'annonce
    faite au public ne soit pas trompeuse. Il faut donc dire les sources, leur
    millésime, leur ÉCHELLE, le poids relatif de chaque pilier, et surtout ce
    que la note ne dit pas. Tout cela est ici ; le barème détaillé n'y est pas.

    Le point le plus important de la page est l'échelle : nos risques valent
    pour la COMMUNE. Une note élevée ne dit rien de la parcelle, et c'est la
    confusion qui rendrait la note réellement trompeuse.
    """
    from . import scoring
    lignes = "".join(
        f'<tr><td>{_e(scoring.LIBELLES_PILIERS[cle])}</td>'
        f'<td>{maxi} points</td></tr>'
        for cle, maxi in scoring.MAX_PILIERS.items())
    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Méthode</nav>

<h1>Comment la note de résilience est calculée</h1>
<p class="chapeau">Une note sur 100, construite à partir de données publiques
et du texte des annonces. C'est un <strong>indicateur éditorial de comparaison
entre les biens de ce catalogue</strong> — ni un diagnostic, ni une expertise,
ni une garantie.</p>

<h2>Les six piliers et leur poids</h2>
<table>
<tr><th>Pilier</th><th>Poids</th></tr>
{lignes}
</table>
<p>Le détail du barème — quels indices comptent, pour combien de points, à
partir de quels seuils — n'est pas publié : c'est le travail propre de ce
site. Ce qui est publié, ci-dessous, est ce qui permet de juger si la note
mérite d'être crue.</p>

<h2>D'où viennent les données</h2>
<table>
<tr><th>Donnée</th><th>Source</th><th>Échelle</th></tr>
<tr><td>Risques naturels et technologiques</td><td>Géorisques (État)</td>
    <td><strong>Commune</strong></td></tr>
<tr><td>Communes, population, densité</td><td>Insee et data.gouv.fr</td>
    <td>Commune</td></tr>
<tr><td>Coordonnées et altitude</td><td>Base Adresse Nationale, IGN</td>
    <td>Commune et code postal</td></tr>
<tr><td>Gares et temps de trajet</td><td>Table de gares constituée par nos soins</td>
    <td>Gare la plus proche</td></tr>
<tr><td>Équipements du bien (cave, puits, poêle, dépendances…)</td>
    <td>Détection automatique dans le texte de l'annonce</td>
    <td>Ce que l'agence a écrit</td></tr>
</table>

<h2>Ce que la note ne dit pas</h2>
<ul>
<li><strong>Les risques valent pour la commune, pas pour la parcelle.</strong>
C'est la limite la plus importante de toute la page. Une commune documentée
inondable comporte des rues sèches ; une commune sans risque recensé comporte
des points bas. La note ne remplace pas l'état des risques, obligatoire à la
vente, ni une visite.</li>
<li><strong>Les équipements sont ceux que l'agence a écrits.</strong> Une
maison peut avoir une cave dont l'annonce ne parle pas : elle ne sera pas
créditée. Nous ne vérifions rien sur place.</li>
<li><strong>La note compare, elle ne certifie pas.</strong> Elle situe un bien
par rapport aux autres du catalogue. Elle ne dit ni qu'une maison est sûre, ni
qu'elle sera habitable dans vingt ans, ni ce qu'elle vaudra.</li>
<li><strong>Elle ne chiffre aucun travaux.</strong> Ni toiture, ni isolation,
ni assainissement, ni mise aux normes.</li>
<li><strong>Elle ignore l'état du bâti.</strong> Fondations, structure,
humidité, réseaux : rien de tout cela n'est observable depuis une annonce.</li>
</ul>

<h2>Ce qui a changé récemment</h2>
<p>Le barème évolue quand les données ou la littérature le justifient. Deux
révisions notables :</p>
<ul>
<li><strong>La cave n'est bonifiée que si l'eau ne l'atteint pas.</strong> En
zone inondable, une cave cesse d'être un cellier : la nappe en charge pousse
sur les parois enterrées et peut soulever la dalle. Le bonus est réduit quand
la commune est documentée inondable, et supprimé quand le bien l'est.</li>
<li><strong>Le poêle de masse est distingué du poêle à bois ordinaire.</strong>
Il restitue sa chaleur pendant douze à vingt-quatre heures sans électricité et
permet de cuisiner : c'est le seul chauffage qui tienne une coupure de réseau
en hiver.</li>
</ul>

<h2>Les mots que nous employons</h2>
<p>« Résilient » désigne ici un score de comparaison entre les biens de ce
catalogue, sur les six piliers ci-dessus — pas une propriété du bâtiment.
« Commune sans inondation recensée » signifie qu'<em>aucun événement
d'inondation ne figure dans les données Géorisques que nous avons
consultées</em>, et rien de plus.</p>
"""
    return _document(
        "Méthode de la note de résilience",
        "Sources, échelle, poids des piliers et limites de la note de "
        "résilience de Refuge Immo.",
        f"{base}{seo.URL_METHODE}", corps,
        _jsonld(seo.jsonld_fil([("Accueil", "/"), ("Méthode", seo.URL_METHODE)], base)),
        base)


def page_robot(base: str = seo.SITE) -> str:
    """La page vers laquelle pointe l'identité de nos robots.

    Un robot qui dit son nom doit dire aussi où lire ce qu'il fait : c'est la
    convention des moteurs de recherche, et c'est ce qui rend le refus
    possible. La page tient donc les trois réponses qu'un administrateur de
    site d'agence vient chercher — qui est-ce, comment le bloquer, comment
    obtenir un retrait — avant toute autre chose.
    """
    from . import robot
    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Notre robot</nav>

<h1>Notre robot : ce qu'il fait chez vous, et comment l'arrêter</h1>
<p class="chapeau">Les annonces de ce site viennent des sites des agences et des
réseaux qui les publient, lues par un robot qui dit son nom. Cette page est
celle qu'il indique dans chacune de ses requêtes.</p>

<h2>Comment il se présente</h2>
<pre><code>User-Agent: {_e(robot.USER_AGENT)}</code></pre>
<p>Il lit d'abord votre fichier <code>robots.txt</code> et le respecte. Il
suit votre plan de site (<code>sitemap.xml</code>), celui que vous destinez
aux moteurs de recherche, n'ouvre qu'une connexion à la fois sur votre site et
attend quelques secondes entre deux pages. Il ne contourne aucune protection :
une page qui lui est refusée n'est pas lue, et un site qui le refuse n'est pas
visité sous un autre nom.</p>

<h2>Ce qu'il retient, et ce qu'il ne retient pas</h2>
<ul>
<li>Il retient des <strong>faits</strong> : prix, surface, nombre de pièces,
terrain, commune, étiquette énergétique — et le lien vers votre page, vers
laquelle chaque fiche renvoie.</li>
<li>Il lit le texte de l'annonce pour y repérer une cave, un puits, un poêle,
des travaux à prévoir, et <strong>ne le conserve pas</strong>. Seul le constat
est gardé ; le texte n'est ni republié ni stocké.</li>
<li>Il n'enregistre <strong>aucune coordonnée</strong> : ni téléphone, ni
courriel, ni nom d'agent. S'il en rencontre dans un titre, elles sont effacées
à l'entrée.</li>
<li>Les photographies restent chez vous : nous les affichons depuis vos
serveurs, sans en faire de copie. Vous voyez ce trafic et pouvez le refuser
d'un réglage.</li>
</ul>

<h2>Pour le bloquer</h2>
<p>Deux lignes dans votre <code>robots.txt</code> suffisent ; il les lit avant
toute page :</p>
<pre><code>User-agent: {_e(robot.NOM)}
Disallow: /</code></pre>

<h2>Pour retirer vos annonces</h2>
<p>Écrivez-nous — l'adresse est dans les
<a href="{_e(base + seo.URL_MENTIONS)}">mentions légales</a>. Le retrait est
fait sans discussion et sans délai, et votre site est ajouté à une liste
d'exclusion que consultent tous nos robots, y compris celui qui découvre de
nouvelles agences : nous n'y reviendrons pas. Aucune justification n'est
demandée.</p>

<h2>Pourquoi un robot qui dit son nom</h2>
<p>Jusqu'au 1<sup>er</sup> octobre 2026, nos robots se présentaient comme un
navigateur. Un robot qui s'annonce vous laisse le choix de le refuser ; nous
préférons votre choix à notre confort.</p>
"""
    return _document(
        "Notre robot",
        "Ce que le robot de Refuge Immo fait sur les sites d'agences, sous quel "
        "nom il se présente, et comment le bloquer ou obtenir un retrait.",
        f"{base}{seo.URL_ROBOT}", corps,
        _jsonld(seo.jsonld_fil([("Accueil", "/"), ("Notre robot", seo.URL_ROBOT)], base)),
        base)


def page_professionnels(nombre: int = 0, base: str = seo.SITE) -> str:
    """Ce que le site fait, et ce qu'un professionnel peut en acheter.

    Une règle gouverne cette page, et elle est écrite dessus : **rien de ce
    qui est vendu ne modifie une note ni un classement**. Un site qui promet
    une sélection objective et vend de la mise en avant ment sur les deux.
    Les prestations proposées portent donc toutes sur ce que l'agence fait de
    NOS données chez elle — jamais sur sa place dans nos listes.

    Le formulaire suit la règle des alertes : tant qu'aucune boîte ne reçoit,
    on ne recueille rien. Il ouvre le logiciel de courrier du visiteur, ou —
    si l'adresse n'est pas encore ouverte — renvoie au canal provisoire en le
    disant. Recueillir une donnée pour la perdre est pire que ne pas la
    recueillir : c'est la leçon de la mise en relation retirée le 17 août.
    """
    canonique = f"{base}{seo.URL_PROFESSIONNELS}"
    titre = "Professionnel de l'immobilier ?"
    description = (
        "Refuge Immo note la résilience climatique des maisons publiées par "
        "les agences. Ce que le site fait de vos annonces, ce qu'il ne fera "
        "jamais, et ce que vous pouvez en obtenir.")

    catalogue = (f"{nombre:,}".replace(",", " ") if nombre
                 else "Plusieurs milliers de")

    offres = [
        ("Rapport de résilience à votre marque",
         "Le rapport complet d'un bien — risques Géorisques, exposition "
         "argile, autonomie en eau et en chauffage, accès sans voiture — mis "
         "en page à vos couleurs, à joindre à votre dossier de vente.",
         "à l'unité ou par lot"),
        ("Vos annonces relevées en priorité",
         "Vos nouvelles annonces sont relevées à chaque passage plutôt qu'à "
         "leur tour de rotation, et vos retraits pris en compte le jour même. "
         "Cela change la FRAÎCHEUR de vos fiches, jamais leur note.",
         "abonnement mensuel"),
        ("Les données de résilience pour votre propre site",
         "Un export ou un accès programmatique aux indicateurs que nous "
         "calculons, pour les afficher chez vous. Vous restez maître de la "
         "présentation, nous restons la source citée.",
         "sur devis"),
        ("Une étude de votre secteur",
         "Ce que vaut votre zone de chalandise sur nos critères, comparée aux "
         "communes voisines : où sont les biens qui tiendront, et lesquels de "
         "vos mandats sortent du lot.",
         "prestation ponctuelle"),
    ]
    liste_offres = "".join(
        f'<li><h3>{_e(nom)}</h3><p>{_e(texte)}</p>'
        f'<p class="modalite">{_e(modalite)}</p></li>'
        for nom, texte, modalite in offres)

    ouvert = bool(seo.COURRIEL_PRO)
    formulaire = f"""
<form id="form-pro" class="alerte-form">
  <label class="champ"><span>Votre agence ou votre réseau</span>
    <input type="text" id="pro-agence" autocomplete="organization" required></label>
  <label class="champ"><span>Votre nom</span>
    <input type="text" id="pro-nom" autocomplete="name" required></label>
  <label class="champ"><span>Votre adresse e-mail</span>
    <input type="email" id="pro-mail" placeholder="vous@votre-agence.fr"
           autocomplete="email" required></label>
  <label class="champ"><span>Ce qui vous intéresse</span>
    <textarea id="pro-message" rows="4"
      placeholder="En deux lignes : ce que vous cherchez."></textarea></label>
  <button class="bouton" type="submit">Écrire</button>
  <p class="alerte-note" id="pro-note">Votre message part depuis votre propre
    logiciel de courrier : rien n'est enregistré sur ce site.</p>
</form>
<script>
// Rien ne transite par ce serveur : le formulaire compose un courriel que le
// visiteur envoie lui-même. Aucune coordonnée professionnelle n'est stockée
// ici, donc aucune ne peut être perdue.
(function () {{
  var f = document.getElementById("form-pro");
  if (!f) return;
  f.addEventListener("submit", function (e) {{
    e.preventDefault();
    var note = document.getElementById("pro-note");
    var val = function (id) {{
      return (document.getElementById(id).value || "").trim();
    }};
    if (val("pro-mail").indexOf("@") < 0) {{
      note.textContent = "Indiquez une adresse e-mail valide.";
      return;
    }}
    var corps = "Bonjour,\\n\\n"
      + "Agence : " + val("pro-agence") + "\\n"
      + "Nom : " + val("pro-nom") + "\\n"
      + "E-mail : " + val("pro-mail") + "\\n\\n"
      + val("pro-message") + "\\n";
    note.textContent = "Votre logiciel de courrier s'ouvre avec votre message. "
      + "Il ne reste qu'à l'envoyer.";
    window.location.href = "mailto:{seo.COURRIEL_PRO}"
      + "?subject=" + encodeURIComponent("Refuge Immo — professionnel")
      + "&body=" + encodeURIComponent(corps);
  }});
}})();
</script>""" if ouvert else f"""
<p class="alerte-note"><strong>L'adresse professionnelle est en cours
d'ouverture.</strong> Plutôt qu'un formulaire qui recueillerait vos
coordonnées sans boîte pour les recevoir, voici le canal qui fonctionne
aujourd'hui : <a href="{_e(seo.CONTACT_PROVISOIRE)}">le suivi de questions du
dépôt public</a>. Il est horodaté, consultable par tous, et n'expose aucune
adresse personnelle. Il disparaîtra le jour où le courriel existera.</p>"""

    corps = f"""
<nav class="fil"><a href="{_e(base)}/">Accueil</a> › Professionnels</nav>
<h1>Professionnel de l'immobilier ?</h1>
<p class="chapeau">{_e(catalogue)} maisons sont au catalogue. Refuge Immo les
lit là où vous les publiez et les note sur leur résilience au changement
climatique — sécheresse, inondation, argile, autonomie en eau et en
chauffage, accès sans voiture.</p>

<h2>Ce que le site fait de vos annonces</h2>
<p>Il les lit là où vous les publiez — votre site, votre sitemap — au rythme
d'une rotation qui repasse sur chaque agence. Il en extrait les faits (prix,
surface, terrain, pièces, commune), les croise avec des données publiques
(Géorisques pour les risques naturels, l'Insee pour les communes, l'IGN pour
les vues aériennes), et en tire une note.</p>
<p>Chaque fiche renvoie vers <strong>votre</strong> annonce. Le visiteur qui
veut visiter passe par vous : le site ne prend aucun mandat, ne perçoit
aucune commission et n'intervient dans aucune transaction.</p>

<h2>Ce que le site ne fera jamais</h2>
<p class="engagement"><strong>Aucune des prestations ci-dessous ne modifie une
note ni un classement.</strong> Un site qui promet une sélection objective et
vend de la mise en avant ment sur les deux. Ce qui se vend ici porte sur ce
que vous faites de nos données chez vous — jamais sur votre place dans nos
listes. Une prestation qui viendrait contredire cette règle n'existerait
pas.</p>

<h2>Ce que vous pouvez en obtenir</h2>
<ul class="offres">{liste_offres}</ul>
<p class="note">Ces prestations sont en cours de mise en place : tarifs et
conditions se fixeront avec les premiers professionnels intéressés. Écrivez si
l'une d'elles vous parle — ou si vous en voyez une meilleure.</p>

<h2>Faire corriger ou retirer une annonce</h2>
<p>C'est gratuit, et cela le restera. Si l'une de vos annonces est mal lue,
mal située, ou si vous ne souhaitez pas y figurer, dites-le et ce sera fait.
Aucune contrepartie n'est demandée pour cela.</p>

<h2>Nous écrire</h2>
{formulaire}
"""
    return _document(
        titre, description, canonique, corps,
        _jsonld(seo.jsonld_fil([("Accueil", "/"),
                                ("Professionnels", seo.URL_PROFESSIONNELS)], base)),
        base)


def page_message(titre: str, texte: str, base: str = seo.SITE) -> str:
    """Une page d'une phrase — la réponse aux liens d'activation et de
    désinscription. Elle dit ce qui vient de se passer, et ramène à l'accueil.
    Volontairement sans balisage riche : personne ne doit indexer ces pages.
    """
    corps = f"""
<h1>{_e(titre)}</h1>
<p class="chapeau">{_e(texte)}</p>
<p><a class="bouton" href="{_e(base)}/">Retour au catalogue</a></p>
"""
    page = _document(titre, texte, f"{base}{seo.URL_ALERTES}", corps, "", base)
    # Ces pages portent une action sur une adresse précise : les moteurs n'ont
    # rien à y faire.
    return page.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
