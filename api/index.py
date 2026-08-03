"""Point d'entrée pour l'hébergement Vercel : expose l'application FastAPI.

Vercel détecte la variable `app` (application ASGI) et route toutes les
requêtes vers elle (voir vercel.json à la racine).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402,F401
