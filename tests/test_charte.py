"""La charte graphique tient parce qu'un test la tient.

Mesuré avant de l'écrire (novembre 2026) : 22 tailles de texte, 25
espacements dont la moitié hors de toute grille, 10 arrondis, et aucune
police de marque — chaque appareil affichait la sienne. Rien de tout cela
n'avait été décidé : chaque valeur avait été choisie au cas par cas, une
règle après l'autre, et c'est exactement ainsi que cela reviendrait.

La charte (docs/CHARTE.md) fixe deux polices, sept tailles, huit pas et
quatre arrondis. Ces tests refusent toute valeur qui n'en fait pas partie.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import pages, seo  # noqa: E402

STATIQUE = RACINE / "app" / "static"
FEUILLES = {
    "style.css": (STATIQUE / "style.css").read_text(encoding="utf-8"),
    "pages.py": pages._ENTETE_STYLE,
}
PROPRIETES_D_ESPACE = ("padding", "padding-top", "padding-bottom", "padding-left",
                       "padding-right", "padding-block", "padding-inline", "margin",
                       "margin-top", "margin-bottom", "margin-left", "margin-right",
                       "gap", "row-gap", "column-gap")


def _sans_jetons(css: str) -> str:
    """La feuille sans ses déclarations de jetons ni ses commentaires : c'est
    l'USAGE qu'on vérifie, pas la définition."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return re.sub(r"--[a-z0-9-]+:\s*[^;}]+", "", css)


@pytest.mark.parametrize("nom", FEUILLES)
def test_toute_taille_de_texte_passe_par_un_jeton(nom):
    css = _sans_jetons(FEUILLES[nom])
    tailles = re.findall(r"font-size:\s*([^;}]+)", css)
    assert len(tailles) > 20, "le test ne lit plus rien"
    hors = [t.strip() for t in tailles if not re.fullmatch(r"\s*var\(--t-\d+\)\s*", t)]
    assert hors == [], f"tailles hors charte dans {nom} : {sorted(set(hors))}"


@pytest.mark.parametrize("nom", FEUILLES)
def test_tout_arrondi_passe_par_un_jeton(nom):
    css = _sans_jetons(FEUILLES[nom])
    rayons = re.findall(r"border-radius:\s*([^;}]+)", css)
    assert len(rayons) > 10
    for rayon in rayons:
        for part in rayon.split():
            assert part == "50%" or part == "0" or re.fullmatch(r"var\(--r-[\w-]+\)", part), (
                f"arrondi hors charte dans {nom} : {rayon.strip()}")


@pytest.mark.parametrize("nom", FEUILLES)
def test_aucun_espacement_n_echappe_a_la_grille(nom):
    """De 1 à 3 px, c'est un réglage d'alignement. À partir de 4, c'est un
    espacement, et il prend l'un des huit pas."""
    css = _sans_jetons(FEUILLES[nom])
    motif = (r"(?<![-\w])(" + "|".join(sorted(PROPRIETES_D_ESPACE, key=len, reverse=True))
             + r")\s*:\s*([^;}]+)")
    declarations = re.findall(motif, css)
    assert len(declarations) > 40
    hors = [f"{prop}: {valeur.strip()}" for prop, valeur in declarations
            for px in re.findall(r"(?<![\w.-])(\d+(?:\.\d+)?)px", valeur) if float(px) >= 4]
    assert hors == [], f"espacements hors grille dans {nom} : {hors[:6]}"


def _jetons(css: str) -> dict[str, str]:
    return dict(re.findall(r"(--(?:t|e|r)-[\w-]+):\s*([^;}\s]+)", css))


def test_les_deux_feuilles_portent_les_memes_jetons():
    """L'application et les pages servies ont chacune leur feuille. Un jeton
    changé d'un côté seulement, et la fiche ne ressemble plus à la page qu'on
    en partage."""
    a, b = _jetons(FEUILLES["style.css"]), _jetons(FEUILLES["pages.py"])
    assert len(a) == 19, f"7 tailles, 8 pas, 4 arrondis attendus, {len(a)} trouvés"
    assert a == b


def test_les_echelles_sont_celles_de_la_charte():
    jetons = _jetons(FEUILLES["style.css"])
    assert [jetons[f"--t-{n}"] for n in (12, 14, 16, 18, 20, 24, 32)] == [
        "12px", "14px", "16px", "18px", "20px", "24px", "32px"]
    assert all(int(v[:-2]) % 4 == 0 for k, v in jetons.items() if k.startswith("--e-"))


# --- Les polices -------------------------------------------------------------

@pytest.mark.parametrize("fichier", ["figtree.woff2", "bricolage-grotesque.woff2"])
def test_les_polices_sont_hebergees_ici(fichier):
    """Comme Leaflet : pas de CDN. Une police appelée chez un tiers, c'est une
    requête de chaque visiteur vers ce tiers, et un site qui change de visage
    le jour où il ne répond plus."""
    chemin = STATIQUE / "vendor" / "fonts" / fichier
    assert chemin.exists() and chemin.stat().st_size > 10_000
    assert chemin.read_bytes()[:4] == b"wOF2", "ce n'est pas un fichier woff2"
    for nom, css in FEUILLES.items():
        assert f"vendor/fonts/{fichier}" in css, f"{fichier} n'est pas déclarée dans {nom}"


def test_leurs_licences_les_accompagnent():
    for nom in ("LICENCE-figtree.txt", "LICENCE-bricolage-grotesque.txt"):
        texte = (STATIQUE / "vendor" / "fonts" / nom).read_text(encoding="utf-8")
        assert "SIL Open Font License" in texte


def test_aucune_police_ne_vient_d_ailleurs():
    for chemin in list((RACINE / "app").rglob("*.py")) + [STATIQUE / "index.html",
                                                          STATIQUE / "style.css"]:
        texte = chemin.read_text(encoding="utf-8")
        assert "fonts.googleapis" not in texte and "fonts.gstatic" not in texte, chemin


def test_la_police_des_titres_reste_aux_titres():
    """Elle a du caractère ; employée partout, elle fatiguerait. Le corps de
    page doit rester dans la police de texte."""
    css = FEUILLES["style.css"]
    corps = re.search(r"\nbody \{(.*?)\}", css, flags=re.DOTALL).group(1)
    assert "var(--f-texte)" in corps
    assert css.count("var(--f-titre)") <= 3, "la police des titres se répand"


# --- Le logo -----------------------------------------------------------------

def test_le_logo_n_a_que_deux_formes():
    """C'est ce qui le garde lisible à seize pixels, la taille d'un onglet :
    l'ancien en comptait quatre, qui s'y touchaient presque."""
    assert seo.marque_svg().count("<path") == 2


def test_l_accueil_porte_le_meme_logo_que_les_pages_servies():
    """index.html en garde une copie statique : elle doit être celle de seo."""
    accueil = (STATIQUE / "index.html").read_text(encoding="utf-8")
    assert seo.logo(30) in accueil
    assert f'<link rel="icon" href="{seo.favicon()}">' in accueil


def test_la_feuille_du_logo_prend_la_couleur_du_fond():
    """Elle est découpée dans la maison : sur le vert de l'en-tête elle est
    verte, sur une page claire elle serait claire."""
    assert 'fill="#1b4332"' in seo.marque_svg()                 # version par défaut
    clair = seo.marque_svg(trait="#1b4332", feuille="#f6f3ec")
    assert 'fill="#f6f3ec"' in clair and 'stroke="#1b4332"' in clair
