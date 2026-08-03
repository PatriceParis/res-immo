"""Tests des calculs géographiques."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import geo  # noqa: E402


def test_distance_paris_provins():
    d = geo.distance_paris_km(48.559, 3.299)
    assert 70 <= d <= 90  # Provins est à ~80 km à vol d'oiseau


def test_temps_croissant_avec_la_distance():
    temps = [geo.temps_voiture_min(d) for d in (10, 50, 100, 200, 300)]
    assert temps == sorted(temps)
    assert 60 <= geo.temps_voiture_min(80) <= 110  # ~80 km vol d'oiseau ≈ 1 h 30


def test_centrale_proche_de_nogent():
    nom, dist = geo.centrale_la_plus_proche(48.493, 3.502)  # Nogent-sur-Seine
    assert nom == "Nogent-sur-Seine"
    assert dist < 10
