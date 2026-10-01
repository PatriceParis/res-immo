"""Les coordonnées d'autrui ne franchissent pas l'export.

Mesuré le 1er octobre dans le fichier public : un descriptif portait encore
un numéro de téléphone, et le texte des pages — qui ne sort plus — en portait
quatre mille deux cents. Le caviardage à l'entrée efface désormais numéros et
courriels des champs libres, comme il effaçait déjà les clés d'API.

Et il ne touche PAS aux adresses : un identifiant de photo fait souvent dix
chiffres, et casser une adresse pour un numéro qui n'en est pas un retirerait
l'image d'un bien parfaitement honnête.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import caviardage  # noqa: E402


def test_un_numero_et_un_courriel_sont_effaces_des_champs_libres():
    propre = caviardage.caviarder_annonce({
        "titre": "Maison — contactez Jean au 06 12 34 56 78",
        "description": "Visite sur rendez-vous : jean.dupont@agence-test.fr ou 02.33.44.55.66.",
        "texte": "Mandataire : +33 6 12 34 56 78",
    })
    for champ in ("titre", "description", "texte"):
        assert "06 12 34 56 78" not in propre[champ] and "@" not in propre[champ], propre[champ]
    assert caviardage.MARQUE_COORDONNEES in propre["description"]
    assert propre["titre"].startswith("Maison — contactez Jean au ")


def test_un_prix_ou_une_surface_ne_sont_pas_pris_pour_un_numero():
    """Dix chiffres collés ne forment pas un numéro français : il commence par
    0 ou +33. Un prix écrit en chiffres doit rester lisible."""
    texte = "Prix : 1 250 000 € — 140 m², terrain 2 500 m², réf. 0123456"
    assert caviardage.caviarder(texte) == texte


def test_les_adresses_ne_sont_jamais_touchees():
    bien = {"photo": "https://cdn.agence.fr/0612345678/photo.jpg",
            "url": "https://agence.fr/bien/0612345678",
            "photos": ["https://cdn.agence.fr/0612345678/photo.jpg"]}
    propre, retires = caviardage.preparer_pour_publication(dict(bien))
    assert propre["photo"] == bien["photo"] and propre["url"] == bien["url"]
    assert retires == []
    assert caviardage.identifiants_restants(bien) == [], (
        "un numéro n'est pas un identifiant de tiers : il ne doit pas faire "
        "abandonner le bien")
