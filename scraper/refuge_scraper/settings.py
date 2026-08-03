"""Réglages Scrapy — volontairement « polis » :

- robots.txt respecté (un site qui refuse les robots n'est pas collecté) ;
- une seule requête à la fois, cadence lente et adaptative ;
- identification honnête du robot (pas de faux navigateur) ;
- cache HTTP local pour ne pas re-télécharger pendant les mises au point.

Voir docs/LEGAL.md avant toute collecte réelle.
"""

import sys
from pathlib import Path

# Rend le paquet `app` (score, base de données) importable depuis les robots.
RACINE_PROJET = Path(__file__).resolve().parents[2]
if str(RACINE_PROJET) not in sys.path:
    sys.path.insert(0, str(RACINE_PROJET))

BOT_NAME = "refuge_immo"

SPIDER_MODULES = ["refuge_scraper.spiders"]
NEWSPIDER_MODULE = "refuge_scraper.spiders"

USER_AGENT = "RefugeImmo-POC/0.1 (projet personnel de veille immobilière)"

ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 2.5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = "httpcache"

ITEM_PIPELINES = {
    "refuge_scraper.pipelines.PipelineRefuge": 300,
}

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"
