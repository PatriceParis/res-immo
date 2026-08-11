"""Le fichier publié doit annoncer la photo que le visiteur verra.

Trois points d'étape de suite ont vu grossir deux familles d'anomalies :
« photo annoncée mais jamais affichée » et « photo publiée différente de la
photo affichée ». Aucune n'était visible à l'écran — le chargement tranchait
déjà correctement. Elles faussaient le décompte : le catalogue se disait
illustré là où il ne l'était pas, et l'inverse.

La cause tient à deux temps différents. `photo` est choisie à la collecte,
bien par bien ; « c'est du mobilier de site » est un constat de corpus, qu'on
ne peut faire qu'en voyant la même image sur plusieurs annonces — donc plus
tard. L'export est le premier moment où l'on dispose des deux.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "scripts"))

from app.chargement import _photos_de_mobilier, photo_retenue  # noqa: E402
from exporter_reel import _photo_publiee_egale_photo_affichee  # noqa: E402

BANDEAU = "https://lor.fr/img/bandeau.jpg"


def _corpus():
    """Trois biens d'une même agence : deux partagent un bandeau de site."""
    return [
        {"id": "a", "agence": "LOR", "photo": BANDEAU,
         "photos": [BANDEAU, "https://lor.fr/img/maison-a.jpg"]},
        {"id": "b", "agence": "LOR", "photo": BANDEAU,
         "photos": [BANDEAU, "https://lor.fr/img/maison-b.jpg"]},
        # Rien de publié, alors qu'une candidate est parfaitement affichable.
        {"id": "c", "agence": "LOR", "photo": None,
         "photos": ["https://lor.fr/img/maison-c.jpg"]},
    ]


def test_le_mobilier_de_site_n_est_plus_annonce_comme_photo():
    """Une image servie à deux biens n'est la photo d'aucun : le fichier ne
    doit plus la présenter comme telle."""
    publie = {b["id"]: b["photo"] for b in _photo_publiee_egale_photo_affichee(_corpus())}
    assert publie["a"] == "https://lor.fr/img/maison-a.jpg"
    assert publie["b"] == "https://lor.fr/img/maison-b.jpg"
    assert BANDEAU not in publie.values()


def test_une_photo_affichable_n_est_plus_passee_sous_silence():
    """L'autre sens : le chargement trouvait la photo, le fichier n'en disait
    rien — le catalogue se comptait moins illustré qu'il ne l'est."""
    publie = {b["id"]: b["photo"] for b in _photo_publiee_egale_photo_affichee(_corpus())}
    assert publie["c"] == "https://lor.fr/img/maison-c.jpg"


def test_l_alignement_ne_change_rien_a_l_ecran():
    """LA propriété qui rend ce correctif sûr : il corrige la comptabilité,
    pas l'affichage. Ce que le visiteur voit doit être identique avant et
    après, bien par bien."""
    avant = _corpus()
    mob_avant = _photos_de_mobilier(avant)
    vu_avant = {b["id"]: photo_retenue(b, mob_avant) for b in avant}

    apres = _photo_publiee_egale_photo_affichee(avant)
    mob_apres = _photos_de_mobilier(apres)
    vu_apres = {b["id"]: photo_retenue(b, mob_apres) for b in apres}

    assert vu_avant == vu_apres


def test_l_operation_est_stable_si_on_la_repete():
    """L'export tourne six fois par jour sur son propre fichier. Un traitement
    qui déplacerait la photo à chaque passage ferait un catalogue instable et
    un dépôt qui grossit sans raison."""
    une = _photo_publiee_egale_photo_affichee(_corpus())
    deux = _photo_publiee_egale_photo_affichee(une)
    assert [b["photo"] for b in une] == [b["photo"] for b in deux]


def test_une_vraie_photo_partagee_par_personne_est_conservee():
    """Le garde-fou : on ne touche pas à ce qui va bien."""
    seule = [{"id": "x", "agence": "A", "photo": "https://a.fr/maison.jpg",
              "photos": ["https://a.fr/maison.jpg", "https://a.fr/jardin.jpg"]}]
    assert _photo_publiee_egale_photo_affichee(seule)[0]["photo"] == "https://a.fr/maison.jpg"
