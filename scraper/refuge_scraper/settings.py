"""Réglages Scrapy — usage personnel, « poli mais fonctionnel » :

- le collecteur se présente comme un NAVIGATEUR courant (User-Agent Chrome +
  en-têtes de navigateur) : beaucoup de sites d'agences renvoient une erreur
  aux clients qui s'annoncent « robot », alors qu'ils servent normalement la
  page à un navigateur ;
- une seule requête à la fois, cadence lente et adaptative (on ne surcharge
  jamais le site) ;
- robots.txt respecté par défaut (désactivable pour un usage strictement
  personnel) ;
- cache HTTP local pour ne pas re-télécharger pendant les mises au point.

À réserver à une veille personnelle — voir docs/LEGAL.md.
"""

import os
import sys
from pathlib import Path

# Rend le paquet `app` (score, base de données) importable depuis les robots.
RACINE_PROJET = Path(__file__).resolve().parents[2]
if str(RACINE_PROJET) not in sys.path:
    sys.path.insert(0, str(RACINE_PROJET))

BOT_NAME = "refuge_immo"

SPIDER_MODULES = ["refuge_scraper.spiders"]
NEWSPIDER_MODULE = "refuge_scraper.spiders"

# On se présente comme un navigateur récent (Chrome). Surchargeable :
#   export REFUGE_USER_AGENT="…"
USER_AGENT = os.environ.get(
    "REFUGE_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
)

# En-têtes envoyés par un vrai navigateur (langue française, types acceptés).
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

# robots.txt respecté par défaut ; pour un usage strictement personnel on peut
# le désactiver avec :  export REFUGE_ROBOTSTXT=0
ROBOTSTXT_OBEY = os.environ.get("REFUGE_ROBOTSTXT", "1") != "0"
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
