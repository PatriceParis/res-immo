#!/usr/bin/env bash
# Lance un robot de collecte d'annonces. Usage : bash scripts/collecter.sh pap
set -e
cd "$(dirname "$0")/.."
if [ -z "$1" ]; then
    echo "Usage : bash scripts/collecter.sh <robot> [options]"
    echo "Robots disponibles : agence, bienici, pap, iep   (voir scraper/README.md)"
    echo "Exemples :"
    echo "  bash scripts/collecter.sh agence                          # tout l'annuaire d'agences"
    echo "  bash scripts/collecter.sh agence -a site=https://une-agence-locale.fr"
    echo "  bash scripts/collecter.sh bienici -a \"lieux=orne, yonne\" -a prix_max=300000"
    exit 1
fi
if [ -d .venv ]; then source .venv/bin/activate; fi
cd scraper
robot="$1"; shift
scrapy crawl "$robot" "$@"
