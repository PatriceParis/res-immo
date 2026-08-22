"""Un réseau qui numérote ses photos n'est pas un site sans photos.

Le 22 août, soixante-dix-sept annonces Safti sont entrées au catalogue — les
premières du réseau, après le correctif du titre. Chacune portait douze à
vingt-deux photos, et pas une seule n'était affichée.

La cause est la règle qui repère le MOBILIER de page — logo, bandeau, icône de
cloche — à deux signes : la même URL sur deux annonces (une preuve : deux biens
distincts ne partagent jamais un fichier), ou le même NOM DE FICHIER sur trois
annonces (une heuristique, pour les gabarits qui servent `…/1942/img/bell.png`
et `…/1988/img/bell.png`).

Safti sert `rg_nobn-2.jpg`, `rg_nobn-3.jpg`… à chacune de ses annonces, sous
des chemins pourtant tous distincts. L'heuristique du nom les prenait donc
toutes, et vidait chaque annonce de sa galerie entière.

Le correctif tient en une distinction : la preuve peut vider une annonce de ses
photos, l'heuristique seule ne le peut pas. Une annonce dont TOUTES les images
portent un nom commun, et qui en a une galerie, décrit un réseau qui numérote —
pas un bien sans photo. Le seuil de galerie garde le cas d'origine : une cloche
ne vient pas par douze.

Mesuré sur le catalogue réel : 77 annonces gagnent une photo, AUCUNE n'en perd.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.chargement import _photos_de_mobilier, photo_retenue  # noqa: E402

# Douze, comme les galeries réelles de Safti. Écrit ici plutôt qu'importé de
# `chargement` : un test qui emprunte la constante du code testé échoue par
# ImportError contre l'ancienne version, ce qui ne prouve rien sur son
# comportement — seulement que le nom est neuf.
PHOTOS_D_UNE_GALERIE = 12


def annonce(agence: str, photos: list[str]) -> dict:
    return {"agence": agence, "url": f"https://x.fr/{photos[0][-12:]}",
            "photos": photos, "titre": "Maison"}


def galerie_safti(numero: int) -> list[str]:
    """Le gabarit réel : chemin unique par bien, noms de fichier communs."""
    return [f"https://cdn.safti.fr/bien-photo/{numero}/abc{numero}/rg_nobn-{n}.jpg"
            for n in range(2, 2 + PHOTOS_D_UNE_GALERIE)]


def test_une_galerie_numerotee_n_est_pas_du_mobilier():
    """LE test. Dix annonces d'un réseau, chacune sa galerie, noms communs."""
    annonces = [annonce("Safti (70)", galerie_safti(n)) for n in range(10)]
    mobilier = _photos_de_mobilier(annonces)
    for a in annonces:
        assert photo_retenue(a, mobilier), (
            "une annonce de douze photos reste affichée sans aucune")


def test_la_cloche_du_gabarit_reste_filtree():
    """Le cas d'origine, qu'il ne faut pas perdre : une image de gabarit servie
    sous un chemin propre à chaque annonce, parmi de vraies photos."""
    annonces = [annonce("Agence X", [f"https://x.fr/{n}/img/facade-{n}.jpg",
                                     f"https://x.fr/{n}/img/bell.png"])
                for n in range(8)]
    mobilier = _photos_de_mobilier(annonces)
    for a in annonces:
        retenue = photo_retenue(a, mobilier)
        assert retenue and "bell.png" not in retenue, (
            f"la cloche du gabarit est affichée comme photo du bien : {retenue}")


def test_une_page_qui_ne_porte_que_du_mobilier_reste_sans_photo():
    """Le garde-fou du seuil : deux images de gabarit et rien d'autre, ce n'est
    pas une galerie — l'annonce doit rester sans photo plutôt que d'afficher
    une cloche."""
    annonces = [annonce("Agence Y", [f"https://y.fr/{n}/img/bell.png",
                                     f"https://y.fr/{n}/img/logo.png"])
                for n in range(8)]
    mobilier = _photos_de_mobilier(annonces)
    for a in annonces:
        assert not photo_retenue(a, mobilier), (
            "une cloche est promue photo de bien faute d'autre candidate")


def test_la_preuve_prime_toujours_sur_l_heuristique():
    """Une URL IDENTIQUE sur deux annonces reste éliminatoire, même si elle
    vide l'annonce : deux biens distincts ne partagent jamais un fichier."""
    partagee = "https://z.fr/commun/photo.jpg"
    annonces = [annonce("Agence Z", [partagee] * 1 + [f"https://z.fr/{n}/a.jpg"])
                for n in range(3)]
    for a in annonces:
        a["photos"] = [partagee]
    mobilier = _photos_de_mobilier(annonces)
    assert partagee in mobilier, "la photo partagée doit rester du mobilier"
    for a in annonces:
        assert not photo_retenue(a, mobilier)
