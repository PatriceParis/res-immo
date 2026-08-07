"""Une image récupérée est-elle vraiment la photo d'un bien ?

Ces tests fabriquent de vraies images et exigent le bon verdict. Le cas qui
justifie tout : chez immo-ray, l'étiquette DPE et la maison sont servies par
le MÊME script — `image-get.inc.php?f=1024x550&n=11837` contre `…&n=11838`.
Aucune règle sur l'adresse ne peut les séparer ; seule l'image le peut.
"""

import io
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.photos import dimensions, ressemble_a_une_photo  # noqa: E402

Image = pytest.importorskip("PIL.Image", reason="Pillow absent")


def _octets(image, format="PNG") -> bytes:
    tampon = io.BytesIO()
    image.save(tampon, format=format)
    return tampon.getvalue()


def _etiquette_dpe(largeur=1024, hauteur=550):
    """Sept aplats de couleur, comme le diagramme réglementaire."""
    image = Image.new("RGB", (largeur, hauteur), "white")
    barres = ["#008000", "#33cc33", "#99cc00", "#ffff00",
              "#ffcc00", "#ff9900", "#ff0000"]
    for rang, couleur in enumerate(barres):
        bloc = Image.new("RGB", (largeur - 250, 60), couleur)
        image.paste(bloc, (120, 30 + rang * 72))
    return image


def _photographie(largeur=1024, hauteur=550):
    """Du bruit dense : ce qu'une photo a et qu'un diagramme n'a pas."""
    random.seed(12)
    image = Image.new("RGB", (largeur, hauteur))
    image.putdata([(random.randrange(256), random.randrange(256), random.randrange(256))
                   for _ in range(largeur * hauteur)])
    return image


def test_l_etiquette_dpe_est_refusee():
    bonne, motif = ressemble_a_une_photo(_octets(_etiquette_dpe()))
    assert not bonne, motif
    assert "diagramme" in motif


def test_une_photographie_est_acceptee():
    bonne, motif = ressemble_a_une_photo(_octets(_photographie(), "JPEG"))
    assert bonne, motif


def test_une_vignette_est_refusee():
    bonne, motif = ressemble_a_une_photo(_octets(_photographie(120, 90), "JPEG"))
    assert not bonne
    assert "trop petite" in motif


def test_une_reponse_vide_ou_illisible_est_refusee():
    assert not ressemble_a_une_photo(b"")[0]
    assert not ressemble_a_une_photo(b"<html>404 introuvable</html>")[0]


@pytest.mark.parametrize("format", ["PNG", "JPEG", "GIF", "WEBP"])
def test_les_dimensions_se_lisent_sans_decoder(format):
    """L'en-tête suffit : on écarte une vignette sans charger toute l'image."""
    attendu = (640, 480)
    image = _photographie(*attendu)
    if format == "GIF":
        image = image.convert("P")
    assert dimensions(_octets(image, format)) == attendu


def test_le_repli_sans_pillow_separe_aussi_les_deux(monkeypatch):
    """Si Pillow manque, le poids par pixel doit encore trancher."""
    from app import photos

    monkeypatch.setattr(photos, "compte_les_couleurs", lambda *a, **k: None)
    assert not photos.ressemble_a_une_photo(_octets(_etiquette_dpe()))[0]
    assert photos.ressemble_a_une_photo(_octets(_photographie(), "JPEG"))[0]


def _charger_verificateur():
    import importlib.util
    racine = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "verifier_photos", racine / "scripts" / "verifier_photos.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_un_reseau_coupe_ne_vide_pas_le_catalogue(tmp_path, monkeypatch, capsys):
    """Ce script décide de ce qu'on affiche à partir de ce que le réseau
    répond. Coupé, il conclurait que TOUTES les photos sont mortes. Il doit
    s'arrêter sans rien écrire plutôt que vider le catalogue."""
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "verif.db"))
    from app import db

    conn = db.connexion()
    for n in range(30):
        db.upsert_annonce(conn, {
            "id": f"v{n}", "source": "agence-test", "titre": f"Longère {n}",
            "url": f"https://agence.fr/bien/{n}",
            "photo": f"https://agence.fr/photos/maison-{n}.jpg",
            "photos": [f"https://agence.fr/photos/maison-{n}.jpg"],
            "prix": 200000, "surface_m2": 120,
        })
    conn.commit()
    conn.close()

    verificateur = _charger_verificateur()
    monkeypatch.setattr(verificateur, "telecharger", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["verifier_photos.py"])

    with pytest.raises(SystemExit) as arret:
        verificateur.main()
    assert arret.value.code == 1
    assert "problème de réseau" in capsys.readouterr().out

    conn = db.connexion()
    restantes = conn.execute(
        "SELECT COUNT(*) c FROM annonces WHERE photo <> ''").fetchone()["c"]
    conn.close()
    assert restantes == 30, "aucune photo ne doit avoir été effacée"
