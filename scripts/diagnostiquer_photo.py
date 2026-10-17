"""Sonde : pourquoi telle annonce n'a-t-elle pas de photo ?

Six agences n'affichent aucune image, et on ne peut pas le diagnostiquer depuis
le poste de développement — le réseau y est fermé. Cette sonde tourne donc là
où il est ouvert (GitHub Actions) et rapporte, pour chaque URL, CE QUE LA PAGE
CONTIENT VRAIMENT :

  - ce que l'extraction choisit aujourd'hui, et pourquoi ;
  - les images présentes, avec le verdict de chaque filtre ;
  - la même chose après une attente plus longue.

Ce dernier point teste l'hypothèse la plus probable : le collecteur n'attend
que 600 ms après `domcontentloaded`, et les galeries chargées en JavaScript
n'existent pas encore à cet instant. Deviner sans mesurer nous a déjà coûté
trois allers-retours sur les noms de fichiers — on mesure.

Usage :  python scripts/diagnostiquer_photo.py URL [URL...]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.extraction import (  # noqa: E402
    ATTRS_IMAGE, RE_IMG_BIEN, RE_IMG_HABILLAGE, RE_IMG_LANGUE,
    _image_de_la_page, _metas, _url_img, extraire_annonce,
)

# Instants d'observation, en millisecondes. 600 ms est ce qu'attend le
# collecteur aujourd'hui ; les suivants disent ce qu'on gagnerait à patienter.
INSTANTS = (600, 2500, 6000)


def _images_brutes(html: str, base: str) -> list[tuple[str, str]]:
    """Toutes les URL d'images de la page, avec le verdict des filtres."""
    import re
    vues, sortie = set(), []
    for balise in re.findall(r"<(?:img|source)\b[^>]*>", html or "", re.IGNORECASE):
        attrs = dict(re.findall(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']', balise))
        for cle in ("srcset", "data-srcset", *ATTRS_IMAGE):
            if not attrs.get(cle):
                continue
            brute = attrs[cle].split(",")[0].strip().split(" ")[0]
            url = _url_img(brute, base)
            if not url or url in vues:
                continue
            vues.add(url)
            if RE_IMG_HABILLAGE.search(url):
                verdict = "habillage (refusée)"
            elif RE_IMG_LANGUE.search(url):
                verdict = "code de langue (refusée)"
            elif RE_IMG_BIEN.search(url):
                verdict = "PHOTO PRÉFÉRÉE"
            else:
                verdict = "secours"
            sortie.append((verdict, url))
            break
    return sortie


def _texte(fragment: str) -> str:
    import html as entites
    import re
    return entites.unescape(re.sub(r"<[^>]+>|\s+", " ", fragment)).strip()[:120]


def _lecture(html: str, annonce) -> None:
    """Ce que l'extracteur a LU — titre, prix, surface — et les candidats de
    titre que la page offrait. Ajouté le 16 octobre 2026 : L'Agence Smith,
    45 pages sur 45 écartées au titre « L », La Plaine Immobilier 38 pages sur
    38 sans annonce lue — et rien, dans le déroulé, pour dire d'où venait ce
    titre ni ce qui manquait. La sonde photo ouvrait déjà la page ; elle dit
    maintenant aussi ce qu'on y lit."""
    import re
    from app.qualite import _REFERENCE, motif_de_rejet
    if annonce:
        print(f"  lu              : titre={annonce.get('titre')!r} prix={annonce.get('prix')} "
              f"surface={annonce.get('surface_m2')} type={annonce.get('type_bien')} "
              f"vendu={annonce.get('vendu')}")
        # Le verdict du filtre qualité et, pour « page_catalogue », les
        # références qu'il a comptées : Agence du Terroir et Demonchy, 17
        # octobre 2026, 60 pages refusées comme catalogues sans qu'on sache
        # si ce sont des listes ou des annonces qui citent leurs voisines.
        refs = sorted(set(_REFERENCE.findall(annonce.get("texte") or "")))
        print(f"  verdict qualité : {motif_de_rejet(annonce) or 'gardée'} | "
              f"{len(refs)} référence(s) lue(s) {refs[:8]} | "
              f"texte : {len(annonce.get('texte') or '')} caractères")
        # Et ce qui entoure chaque référence : la sienne, ou celle d'un voisin
        # en marge ? Ajouté le 17 octobre 2026 pour l'Agence du Terroir, dont
        # 40 pages par visite tombent en « catalogue » sans qu'on sache si ce
        # sont des listes par commune ou des fiches qui citent leurs voisines.
        texte = annonce.get("texte") or ""
        for m in list(_REFERENCE.finditer(texte))[:6]:
            debut = max(0, m.start() - 60)
            print(f"     réf {m.group(1)} au caractère {m.start()} : "
                  f"« {_texte(texte[debut:m.end() + 60])} »")
    else:
        print("  lu              : aucune annonce lue")
    metas = _metas(html)
    balise = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html or "", re.I | re.S)
    h2 = re.findall(r"<h2[^>]*>(.*?)</h2>", html or "", re.I | re.S)
    print(f"  <h2>            : {[_texte(h) for h in h2[:5]]}")
    noms = re.findall(r'"name"\s*:\s*"([^"]{0,120})"', html or "")
    types = sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html or "")))
    print(f"  og:title        : {metas.get('og:title')!r}")
    print(f"  <title>         : {_texte(balise.group(1))!r}" if balise else "  <title>         : —")
    print(f"  <h1>            : {_texte(h1.group(1))!r}" if h1 else "  <h1>            : —")
    print(f"  JSON-LD name    : {[_texte(n) for n in noms[:6]]}")
    print(f"  JSON-LD @type   : {types[:10]}")


def sonder(page, url: str) -> None:
    print("=" * 78)
    print(url)
    print("=" * 78)
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    for attente in INSTANTS:
        page.wait_for_timeout(attente if attente == INSTANTS[0]
                              else attente - INSTANTS[INSTANTS.index(attente) - 1])
        html = page.content()
        metas = _metas(html)
        choisie = _image_de_la_page(html, url)
        annonce = extraire_annonce(html, url, source="sonde")
        images = _images_brutes(html, url)
        print(f"\n--- après {attente} ms "
              f"({len(html)} octets de HTML, {len(images)} image(s)) ---")
        print(f"  og:image        : {metas.get('og:image') or '—'}")
        print(f"  <img> retenue   : {choisie or '—'}")
        print(f"  photo finale    : "
              f"{(annonce or {}).get('photo') if annonce else 'annonce rejetée'}")
        if attente == INSTANTS[0]:
            _lecture(html, annonce)
        for verdict, u in images[:14]:
            print(f"     [{verdict:22}] {u[:110]}")
        if len(images) > 14:
            print(f"     … et {len(images) - 14} autre(s)")

    # Le diaporama se déclenche parfois au premier défilement.
    page.mouse.wheel(0, 2000)
    page.wait_for_timeout(2500)
    html = page.content()
    images = _images_brutes(html, url)
    print(f"\n--- après défilement ({len(images)} image(s)) ---")
    print(f"  <img> retenue   : {_image_de_la_page(html, url) or '—'}")
    # C'est APRÈS le défilement que le collecteur lit la page (une molette,
    # puis 900 ms) : la lecture qui compte est celle-ci.
    _lecture(html, extraire_annonce(html, url, source="sonde"))
    for verdict, u in images[:14]:
        print(f"     [{verdict:22}] {u[:110]}")


def main() -> None:
    urls = [u for u in sys.argv[1:] if u.startswith("http")]
    if not urls:
        print("Usage : python scripts/diagnostiquer_photo.py URL [URL...]")
        raise SystemExit(2)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        navigateur = p.chromium.launch(
            executable_path=os.environ.get("REFUGE_CHROMIUM") or None, headless=True)
        page = navigateur.new_page()
        page.set_viewport_size({"width": 1400, "height": 1000})
        for url in urls:
            try:
                sonder(page, url)
            except Exception as erreur:            # une page morte n'arrête pas la sonde
                print(f"!! {url} : {type(erreur).__name__} — {erreur}")
        navigateur.close()


if __name__ == "__main__":
    main()
