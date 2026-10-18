"""Le texte d'une annonce s'affiche tel que l'agence l'a écrit, pas son code.

Mesuré le 18 octobre 2026 : trente-quatre titres servis portaient des entités
HTML brutes — « Maison en pierre avec dépendances &#8211; Portes de Bayeux »
chez ACI, « d&#8217;une » ailleurs. Le site échappe tout ce qu'il affiche :
la fiche et la carte montraient « &#8211; » en toutes lettres.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement  # noqa: E402


def brut(**autres) -> dict:
    bien = {"id": "aci-1", "titre": "Maison en pierre avec dépendances", "type_bien": "maison",
            "agence": "ACI Agence Capital Immobilier", "agence_url": "https://agence-aci.com",
            "url": "https://agence-aci.com/propriete/maison-en-pierre-portes-de-bayeux/",
            "prix": 285000, "surface_m2": 140, "terrain_m2": 2500, "pieces": 6,
            "commune": "Vaux-sur-Aure", "code_postal": "14400", "departement": "14",
            "lat": 49.296, "lon": -0.705, "description": "Belle longère."}
    bien.update(autres)
    return bien


def test_les_entites_du_titre_et_de_la_description_sont_decodees():
    source = brut(titre="Maison en pierre avec dépendances &#8211; Portes de Bayeux",
                  description="Au calme, &quot;coup de c&oelig;ur&quot; d&#8217;une rare qualité.")
    annonce = chargement.preparer_annonce(source)
    assert annonce["titre"] == "Maison en pierre avec dépendances – Portes de Bayeux"
    assert annonce["description"] == "Au calme, \"coup de cœur\" d’une rare qualité."
    assert "&#8211;" in source["titre"], "l'annonce brute, elle, n'est pas modifiée"


def test_un_texte_sans_entite_ne_bouge_pas():
    for titre in ("Maison de maître & dépendances", "Longère 5 pièces – 2 ha"):
        assert chargement.preparer_annonce(brut(titre=titre))["titre"] == titre
