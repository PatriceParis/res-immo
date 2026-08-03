"""Robot générique de collecte sur les sites d'AGENCES immobilières.

C'est l'idée centrale du POC : plutôt que de forcer les grands portails
(bloqués et interdits de collecte), on passe par les sites des agences, qui
sont faits pour être référencés par Google — donc ouverts, et qui publient
sur chaque annonce des données structurées schema.org (voir app/extraction).

Le robot, pour chaque agence de l'annuaire (scraper/refuge_scraper/agences.json) :
  1. lit son sitemap.xml (le plan que le site fournit aux moteurs) ;
  2. en extrait les URL de pages d'annonces ;
  3. sur chaque page, lit les données schema.org (prix, surface, position…) ;
  4. calcule le score de résilience et enregistre le bien.

Un SEUL robot couvre ainsi des centaines de sites, quel que soit leur logiciel.

Exemples :
    bash scripts/collecter.sh agence                       # tout l'annuaire
    bash scripts/collecter.sh agence -a agence="Patrice Besse"
    bash scripts/collecter.sh agence -a site=https://une-agence-locale.fr
    bash scripts/collecter.sh agence -a site=https://x.fr -a sitemap=https://x.fr/sitemap_biens.xml

⚠️ Usage personnel, robots.txt respecté d'office, cadence lente (voir
docs/LEGAL.md et docs/STRATEGIE_COLLECTE.md). Écrit hors ligne : au premier
lancement, surveillez le journal — il indique ce qui a été trouvé ou non.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import scrapy

from app.extraction import extraire_annonce

ANNUAIRE = Path(__file__).resolve().parent.parent / "agences.json"

# URL qui ressemblent à une page d'annonce (et pas à une page « contact »…).
MOTIF_PAGE_BIEN = re.compile(
    r"/(annonces?|biens?|vente|vendre|a-vendre|property|properties|nos-biens|detail|ref)[-/]",
    re.IGNORECASE,
)


def _slug(nom: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (nom or "agence").lower()).strip("-")


class SpiderAgence(scrapy.Spider):
    name = "agence"

    def __init__(self, agence: str = "", site: str = "", sitemap: str = "",
                 max_biens: str = "40", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_biens = int(max_biens)
        self._comptes: dict[str, int] = {}
        self.cibles = self._construire_cibles(agence, site, sitemap)

    def _construire_cibles(self, agence, site, sitemap) -> list[dict]:
        if site:  # agence ad hoc passée en ligne de commande
            nom = agence or urlparse(site).netloc
            return [{"nom": nom, "site": site.rstrip("/"), "sitemap": sitemap or None}]
        try:
            annuaire = json.loads(ANNUAIRE.read_text(encoding="utf-8")).get("agences", [])
        except (OSError, ValueError):
            self.logger.error("Annuaire illisible : %s", ANNUAIRE)
            return []
        if agence:
            annuaire = [a for a in annuaire if agence.lower() in a["nom"].lower()]
            if not annuaire:
                self.logger.warning("Aucune agence « %s » dans l'annuaire", agence)
        return annuaire

    def start_requests(self):
        for cible in self.cibles:
            base = (cible.get("site") or "").rstrip("/")
            sitemap = cible.get("sitemap") or (base + "/sitemap.xml" if base else None)
            if not sitemap:
                continue
            meta = {"nom": cible["nom"], "site": base, "profondeur": 0}
            yield scrapy.Request(sitemap, callback=self.parse_sitemap,
                                 cb_kwargs=meta, dont_filter=True)

    def parse_sitemap(self, response, nom, site, profondeur):
        locs = response.xpath('//*[local-name()="loc"]/text()').getall()
        if not locs:
            self.logger.info("[%s] sitemap sans URL : %s", nom, response.url)
            return

        sous_sitemaps = [u for u in locs if u.lower().endswith(".xml")]
        pages = [u for u in locs if MOTIF_PAGE_BIEN.search(u)]

        # Sitemap index : suivre quelques sous-sitemaps (profondeur limitée).
        if sous_sitemaps and profondeur < 2:
            for u in sous_sitemaps[:10]:
                yield scrapy.Request(u, callback=self.parse_sitemap, dont_filter=True,
                                     cb_kwargs={"nom": nom, "site": site,
                                                "profondeur": profondeur + 1})

        restant = self.max_biens - self._comptes.get(nom, 0)
        if restant <= 0:
            return
        for u in pages[:restant]:
            yield scrapy.Request(u, callback=self.parse_bien,
                                 cb_kwargs={"nom": nom, "site": site})

    def parse_bien(self, response, nom, site):
        if "html" not in (response.headers.get("Content-Type", b"").decode("latin1").lower()):
            return
        annonce = extraire_annonce(
            response.text, response.url, source=_slug(nom),
            agence=nom, agence_url=site)
        if annonce is None:
            return
        self._comptes[nom] = self._comptes.get(nom, 0) + 1
        yield annonce
