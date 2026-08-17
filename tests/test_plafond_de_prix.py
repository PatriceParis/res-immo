"""Au-delà de 700 000 €, ce n'est plus le projet.

L'application cherche un refuge habitable et résilient, pas un patrimoine.
Cent treize biens du catalogue dépassaient ce seuil — jusqu'à 4 494 000 € —
et occupaient des places en tête de liste que personne ne venait chercher ici.

Le plafond vit dans `est_bien_valide`, seul endroit traversé par les DEUX
chemins : la collecte, qui n'enregistre plus ces biens, et le chargement, qui
écarte ceux déjà en base. Une copie posée d'un seul côté aurait laissé le
fichier et l'écran se contredire — c'est déjà arrivé avec les photos.

Ces tests tiennent les deux sens : écarter ce qui est trop cher, mais ne
JAMAIS écarter un bien dont on n'a pas su lire le prix. Ils sont cent
dix-huit dans ce cas, et un plafond appliqué à l'aveugle les effacerait tous.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import chargement, qualite  # noqa: E402


def bien(**extra) -> dict:
    base = {"titre": "Maison de campagne avec jardin", "type_bien": "maison",
            "surface_m2": 120, "pieces": 5, "prix": 250_000,
            "url": "https://agence.fr/maison-1"}
    base.update(extra)
    return base


def test_un_bien_trop_cher_est_ecarte():
    assert qualite.est_bien_valide(bien(prix=700_001)) is False
    assert qualite.est_bien_valide(bien(prix=4_494_000)) is False


def test_le_seuil_lui_meme_reste_admis():
    """700 000 € pile est dans le projet : le plafond exclut au-DELÀ."""
    assert qualite.est_bien_valide(bien(prix=qualite.PRIX_MAXI)) is True


def test_un_bien_sans_prix_n_est_pas_ecarte_par_le_plafond():
    """L'excès inverse, et le plus coûteux : cent dix-huit biens servis n'ont
    pas de prix lisible. Comparer None à un plafond les effacerait tous."""
    assert qualite.est_bien_valide(bien(prix=None)) is True


def test_le_plafond_s_applique_aussi_aux_biens_deja_en_base():
    """La collecte cesse d'en ramener, mais le catalogue en contient déjà. Le
    chargement doit les écarter, sinon ils resteraient affichés indéfiniment."""
    catalogue = [bien(id="cher", prix=1_500_000, url="https://agence.fr/cher"),
                 bien(id="normal", prix=180_000, url="https://agence.fr/normal")]
    for b in catalogue:
        b.update(commune="Chartres", code_postal="28000", departement="28",
                 lat=48.44, lon=1.49)
    servis = {b["id"] for b in chargement.biens_servis(catalogue)}
    assert "cher" not in servis
    assert "normal" in servis


def test_le_curseur_de_l_ecran_s_arrete_au_meme_endroit():
    """Un curseur qui monterait plus haut que le plafond promettrait des biens
    qui n'existent plus dans le catalogue — la butée doit dire le vrai."""
    html = (RACINE / "app" / "static" / "index.html").read_text(encoding="utf-8")
    ligne = next(l for l in html.splitlines() if 'id="f-prix"' in l)
    assert f'max="{qualite.PRIX_MAXI}"' in ligne, ligne
    assert f'value="{qualite.PRIX_MAXI}"' in ligne, ligne
