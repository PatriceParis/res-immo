"""Écrit data/annonces_demo.json à partir du générateur (app/demo.py).

Usage :  python scripts/generer_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.demo import generer_annonces  # noqa: E402


def main() -> None:
    annonces = generer_annonces()
    sortie = RACINE / "data" / "annonces_demo.json"
    sortie.parent.mkdir(exist_ok=True)
    sortie.write_text(
        json.dumps(annonces, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✔ {len(annonces)} annonces de démonstration écrites dans {sortie}")


if __name__ == "__main__":
    main()
