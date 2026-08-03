"""Robot immo-entre-particuliers.com — petit portail d'annonces de particuliers.

Mêmes précautions que pour PAP : robots.txt respecté, URL de départ à
ajuster depuis le site si besoin. Lancement :  bash scripts/collecter.sh iep
"""

from .base import SpiderAnnonces


class SpiderImmoEntreParticuliers(SpiderAnnonces):
    name = "iep"
    allowed_domains = ["immo-entre-particuliers.com", "www.immo-entre-particuliers.com"]
    motif_lien_annonce = r"/annonce"
    type_bien = "maison"

    start_urls = [
        "https://www.immo-entre-particuliers.com/annonces/france-ile-de-france/vente",
        "https://www.immo-entre-particuliers.com/annonces/france-bourgogne/vente",
        "https://www.immo-entre-particuliers.com/annonces/france-basse-normandie/vente",
    ]
