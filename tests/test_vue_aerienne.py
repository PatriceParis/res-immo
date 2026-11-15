"""La commune vue du ciel arrivait étirée, et quatorze fois trop floue.

Deux défauts d'une même image, tous deux invisibles tant qu'on ne mesure pas.

**L'étirement.** L'emprise était fixée en degrés — 0,024 de longitude sur
0,012 de latitude. Mais un degré de longitude rétrécit avec la latitude quand
un degré de latitude ne bouge jamais : à 47°, cela fait un terrain de 1,82 km
sur 1,34, soit un rapport de 1,36, servi dans un cadre de 640 × 320, soit
2,00. Le WMS ne recadre pas, il étire pour remplir : chaque commune de France
arrivait allongée de moitié dans le sens est-ouest.

**Le flou.** 640 pixels pour 1,8 km font 2,85 m par pixel, quand l'orthophoto
IGN en offre 0,20 — quatorze fois le détail jeté, et un écran à forte densité
étalait encore ce peu sur quatre fois la surface.

Le remède tient en une inversion : dire l'emprise en KILOMÈTRES et en déduire
les degrés par la latitude, au lieu de l'inverse.
"""

import math
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import pages  # noqa: E402

KM_PAR_DEGRE = 111.32
# Du sud de la France au nord : le cosinus de la latitude varie de 17 % entre
# les deux, et c'est exactement ce que l'ancien cadrage ignorait.
LATITUDES = (42.5, 45.0, 47.0, 48.9, 51.1)


def _emprise_km(lat, lon=2.0):
    url = pages._carte_aerienne({"lat": lat, "lon": lon})
    ouest, sud, est, nord = (float(x) for x in
                             re.search(r"BBOX=([^&]+)", url).group(1).split(","))
    largeur = (est - ouest) * KM_PAR_DEGRE * math.cos(math.radians(lat))
    hauteur = (nord - sud) * KM_PAR_DEGRE
    return largeur, hauteur, url


@pytest.mark.parametrize("lat", LATITUDES)
def test_l_image_n_est_pas_deformee(lat):
    """LE test. Le rapport du terrain doit être celui du cadre, partout —
    sinon le WMS étire, et le paysage ment sur ses propres proportions."""
    largeur, hauteur, url = _emprise_km(lat)
    px_l = int(re.search(r"WIDTH=(\d+)", url).group(1))
    px_h = int(re.search(r"HEIGHT=(\d+)", url).group(1))
    assert largeur / hauteur == pytest.approx(px_l / px_h, rel=0.01), (
        f"à {lat}° : terrain {largeur:.2f}×{hauteur:.2f} km "
        f"(rapport {largeur / hauteur:.2f}) dans un cadre {px_l}×{px_h}")


@pytest.mark.parametrize("lat", LATITUDES)
def test_la_vue_couvre_la_meme_etendue_partout(lat):
    """Une emprise en degrés montrait 2,0 km à Dunkerque et 1,7 à Perpignan.
    En kilomètres, la même commune occupe la même place où qu'elle soit."""
    largeur, _, _ = _emprise_km(lat)
    assert largeur == pytest.approx(1.85, rel=0.01)


def test_la_source_est_rendue_au_double_de_sa_taille_d_affichage():
    """La figure fait 100 % de sa colonne, soit ~640 px au plus large. Rendre
    la source à 1280 px laisse un pixel d'image par pixel d'écran sur les
    affichages à forte densité, là où le CSS en étalait un pour quatre."""
    _, _, url = _emprise_km(47.0)
    assert "WIDTH=1280" in url and "HEIGHT=640" in url


def test_la_resolution_a_double():
    """2,85 m par pixel avant, moitié moins après. On reste loin des 0,20 m
    de l'orthophoto native — c'est la commune qu'on montre, pas la parcelle —
    mais le bâti et les haies se lisent."""
    largeur, _, url = _emprise_km(47.0)
    px = int(re.search(r"WIDTH=(\d+)", url).group(1))
    metres_par_pixel = largeur * 1000 / px
    assert metres_par_pixel < 1.5
    assert metres_par_pixel == pytest.approx(1.45, abs=0.05)


def test_un_bien_sans_coordonnees_n_a_pas_de_vue():
    """Sans latitude, pas d'emprise : mieux vaut aucune image qu'une image
    du golfe de Guinée, où mènent les coordonnées nulles."""
    assert pages._carte_aerienne({"lat": None, "lon": None}) == ""
    assert pages._carte_aerienne({}) == ""
