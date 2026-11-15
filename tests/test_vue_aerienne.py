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

import json
import math
import re
import shutil
import subprocess
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


def test_la_source_depasse_la_taille_d_affichage():
    """La colonne fait ~720 px d'image. Un écran à forte densité en réclame
    1 440 : une source de 1 280, comme au premier jet, restait étirée. Il en
    faut davantage, pas moins."""
    _, _, url = _emprise_km(47.0)
    largeur = int(re.search(r"WIDTH=(\d+)", url).group(1))
    assert largeur >= 1440, "une source sous 1 440 px est étirée sur écran 2×"


def test_la_resolution_a_triple():
    """2,85 m par pixel avant, 0,90 après. On reste loin des 0,20 m de
    l'orthophoto native — c'est la commune qu'on montre, pas la parcelle —
    mais une haie s'y distingue d'un talus."""
    largeur, _, url = _emprise_km(47.0)
    px = int(re.search(r"WIDTH=(\d+)", url).group(1))
    metres_par_pixel = largeur * 1000 / px
    assert metres_par_pixel < 1.0
    assert metres_par_pixel == pytest.approx(0.90, abs=0.05)


def test_un_bien_sans_coordonnees_n_a_pas_de_vue():
    """Sans latitude, pas d'emprise : mieux vaut aucune image qu'une image
    du golfe de Guinée, où mènent les coordonnées nulles."""
    assert pages._carte_aerienne({"lat": None, "lon": None}) == ""
    assert pages._carte_aerienne({}) == ""


# --- L'AUTRE générateur d'URL -----------------------------------------------
#
# Il y en a deux : `pages._carte_aerienne` sert la fiche publique, et
# `urlAerienne` dans app.js sert la fiche affichée au clic. Le premier a été
# redressé le 15 novembre ; le second ne l'a pas été, et personne ne l'a vu —
# aucun test ne le regardait. Il servait une TUILE WMTS de 256 pixels au zoom
# 15, soit 3,18 m par pixel, étirée sur les 780 px de la fiche : six fois
# agrandie. C'est la capture d'un utilisateur qui l'a dit, trois échanges
# après que j'eus annoncé le problème réglé.
#
# Ces tests-ci exécutent le vrai code JavaScript, et le dernier interdit qu'un
# troisième générateur apparaisse sans être tenu.

SCRIPT = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _url_client(lat, lon=2.0, largeur=2048, hauteur=525):
    """Exécute `urlAerienne` telle qu'elle est écrite dans app.js."""
    extrait = re.search(
        r"const CIEL_LARGEUR_KM[\s\S]*?\nfunction urlAerienne\([\s\S]*?\n\}",
        SCRIPT).group(0)
    sortie = subprocess.run(
        [NODE, "-e", extrait + f"\nprocess.stdout.write(urlAerienne("
                                f"{{lat:{lat},lon:{lon}}},{largeur},{hauteur}));"],
        capture_output=True, text=True, timeout=30)
    assert sortie.returncode == 0, sortie.stderr
    return sortie.stdout


@pytest.mark.skipif(NODE is None, reason="node absent")
@pytest.mark.parametrize("lat", LATITUDES)
def test_le_client_ne_deforme_pas_non_plus(lat):
    """La même exigence que pour la fiche publique, sur l'autre moitié du
    site : le rapport du terrain doit être celui du cadre demandé."""
    url = _url_client(lat)
    ouest, sud, est, nord = (float(x) for x in
                             re.search(r"BBOX=([^&]+)", url).group(1).split(","))
    largeur = (est - ouest) * KM_PAR_DEGRE * math.cos(math.radians(lat))
    hauteur = (nord - sud) * KM_PAR_DEGRE
    assert largeur / hauteur == pytest.approx(2048 / 525, rel=0.01)


@pytest.mark.skipif(NODE is None, reason="node absent")
def test_les_deux_generateurs_montrent_la_meme_etendue():
    """Une fiche publique et une fiche affichée qui cadrent différemment, ce
    sont deux vues d'un même lieu qui ne se ressemblent pas."""
    url = _url_client(47.0)
    ouest, _, est, _ = (float(x) for x in
                        re.search(r"BBOX=([^&]+)", url).group(1).split(","))
    largeur_client = (est - ouest) * KM_PAR_DEGRE * math.cos(math.radians(47.0))
    largeur_serveur, _, _ = _emprise_km(47.0)
    assert largeur_client == pytest.approx(largeur_serveur, rel=0.01)


@pytest.mark.skipif(NODE is None, reason="node absent")
def test_le_client_demande_une_image_assez_grande():
    """780 px de fiche, donc 1 560 sur un écran à forte densité. Une tuile de
    256 y était agrandie six fois — c'est tout le flou constaté."""
    url = _url_client(47.0)
    largeur_px = int(re.search(r"WIDTH=(\d+)", url).group(1))
    assert largeur_px >= 1560


def test_aucune_vue_aerienne_ne_passe_plus_par_une_tuile():
    """LE garde-fou. Une tuile est une image complète : elle n'échoue jamais,
    elle arrive seulement trop petite — un défaut qu'aucune erreur ne signale.
    Tout générateur d'orthophoto doit demander sa taille, pas la subir.

    Il ne vérifie QUE cela. Les tailles demandées, elles, sont concaténées
    dans les URL (« "&WIDTH=" + largeur ») et non écrites en toutes lettres :
    les chercher dans le texte ferait un test qui tourne à vide et passe
    toujours. Ce sont les deux tests d'exécution ci-dessus qui les tiennent,
    un par générateur — et c'est l'absence d'un tel test sur le second qui a
    laissé la tuile en place un mois."""
    vus = 0
    for fichier in (RACINE / "app").rglob("*"):
        if fichier.suffix not in (".py", ".js") or "vendor" in fichier.parts:
            continue
        texte = fichier.read_text(encoding="utf-8", errors="ignore")
        if "ORTHOIMAGERY" not in texte:
            continue
        vus += 1
        assert "GetTile" not in texte, (
            f"{fichier.name} sert l'orthophoto par tuile : elle sera étirée")
    assert vus >= 2, (
        f"{vus} générateur(s) inspecté(s) : il y en a deux, "
        "la fiche publique et la fiche affichée")
