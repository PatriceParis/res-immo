#!/usr/bin/env bash
# Lance un robot de collecte d'annonces. Usage : bash scripts/collecter.sh pap
set -e
cd "$(dirname "$0")/.."
if [ -z "$1" ]; then
    echo "Usage : bash scripts/collecter.sh <robot>"
    echo "Robots disponibles : pap, iep   (voir scraper/README.md)"
    exit 1
fi
if [ -d .venv ]; then source .venv/bin/activate; fi
cd scraper
scrapy crawl "$1"
