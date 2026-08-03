#!/usr/bin/env bash
# Démarrage en un clic (Mac / Linux) :  bash demarrer.sh
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "⚠ Python 3 n'est pas installé. Téléchargez-le sur https://www.python.org/downloads/"
    exit 1
fi

if [ ! -d .venv ]; then
    echo "• Première installation (environnement Python isolé)…"
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "• Vérification des dépendances…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo ""
echo "──────────────────────────────────────────────────────"
echo "  Refuge Immo démarre."
echo "  Ouvrez votre navigateur sur :  http://localhost:8000"
echo "  (Ctrl+C dans cette fenêtre pour arrêter)"
echo "──────────────────────────────────────────────────────"
echo ""
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
