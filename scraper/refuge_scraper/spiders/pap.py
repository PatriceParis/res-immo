"""Robot PAP.fr (De Particulier à Particulier) — annonces de particuliers.

⚠️ À vérifier avant usage :
- le robots.txt de PAP est respecté automatiquement : si le site interdit la
  collecte d'une page, elle est simplement ignorée ;
- les URL de recherche ci-dessous couvrent des départements cibles autour de
  Paris ; ajustez-les depuis le site (faites une recherche sur pap.fr puis
  copiez l'adresse de la page de résultats) ;
- voir docs/LEGAL.md.

Lancement :  bash scripts/collecter.sh pap
"""

from .base import SpiderAnnonces


class SpiderPap(SpiderAnnonces):
    name = "pap"
    allowed_domains = ["pap.fr", "www.pap.fr"]
    motif_lien_annonce = r"/annonces/maison"
    type_bien = "maison"

    # Recherches « vente maison » — remplacez par vos propres URL de recherche
    # copiées depuis pap.fr si celles-ci ne renvoient plus de résultats.
    start_urls = [
        "https://www.pap.fr/annonce/vente-maisons",
    ]
