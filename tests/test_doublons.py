"""Détection des « biens fantômes » issus d'un bandeau de site.

Cas réel : dix annonces de la même agence, dans dix communes différentes,
toutes à 530 000 € / 265 m² / 1 000 m². L'extraction avait lu un encart
commun à toutes les pages du site. Ces biens n'existent pas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chargement import _signatures_suspectes  # noqa: E402
from app.extraction import extraire_annonce  # noqa: E402


def test_signature_repetee_detectee():
    annonces = [
        {"agence": "Agence du Terroir", "prix": 530000, "surface_m2": 265, "terrain_m2": 1000},
        {"agence": "Agence du Terroir", "prix": 530000, "surface_m2": 265, "terrain_m2": 1000},
        {"agence": "Agence du Terroir", "prix": 530000, "surface_m2": 265, "terrain_m2": 1000},
        {"agence": "Agence du Terroir", "prix": 189000, "surface_m2": 120, "terrain_m2": 800},
        {"agence": "Autre agence", "prix": 530000, "surface_m2": 265, "terrain_m2": 1000},
    ]
    suspectes = _signatures_suspectes(annonces)
    assert ("Agence du Terroir", 530000, 265, 1000) in suspectes
    # Un bien unique de la même agence n'est pas suspect…
    assert ("Agence du Terroir", 189000, 120, 800) not in suspectes
    # …ni le même prix chez une autre agence (coïncidence, pas un bandeau).
    assert ("Autre agence", 530000, 265, 1000) not in suspectes


def test_deux_biens_identiques_ne_suffisent_pas():
    """Deux biens jumeaux (lotissement, maisons mitoyennes) peuvent exister."""
    annonces = [{"agence": "A", "prix": 200000, "surface_m2": 100, "terrain_m2": 500}] * 2
    assert _signatures_suspectes(annonces) == set()


def test_page_sans_titre_exploitable_est_ignoree():
    """Inventer un titre (« Agence X — bien à vendre ») masquait l'échec complet
    de l'extraction : la page ressortait avec le prix lu dans un bandeau."""
    html = ("<html><head></head><body><p>Coup de coeur : 530 000 € — 265 m²"
            "</p></body></html>")
    assert extraire_annonce(html, "https://a.fr/maison-1.html", source="a",
                            agence="Agence du Terroir") is None


def test_titre_pris_dans_la_balise_title_a_defaut():
    html = ("<html><head><title>Maison de bourg à Montoire 120 m²</title></head>"
            "<body><p>Prix : 189 000 €. Surface 120 m². 41800 Montoire.</p></body></html>")
    a = extraire_annonce(html, "https://a.fr/maison-2.html", source="a")
    assert a["titre"] == "Maison de bourg à Montoire 120 m²"
    assert a["code_postal"] == "41800"
