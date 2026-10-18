"""Un bien publié sous deux adresses n'est ni deux biens, ni du mobilier.

Mesuré le 18 octobre 2026. Début octobre, Maison Ancienne du Bessin a changé
le format de ses adresses : `…/25-le-manoir/propriete-xviiieme-…/752-maison`
est devenu `…/25-le-manoir/1-maison/t10/752-propriete-xviiieme-…/`. Les deux
exemplaires restaient au fichier, avec la même galerie. La règle du mobilier
— « deux maisons différentes ne partagent jamais leur photo » — voyait donc
chaque photo du bien sur deux annonces, et toute la galerie passait pour du
mobilier de site. Le site servait cinq maisons deux fois : le nouvel
exemplaire sans photo, l'ancien illustré par la vignette d'une voisine, seule
image qui ne fût pas en double.

Au fichier entier, 86 paires de ce genre : ancien et nouveau format, avec ou
sans « www », version française et anglaise, titre retouché.
"""

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "scripts"))

from app import chargement, exclusions  # noqa: E402
from app.chargement import _photos_de_mobilier, photo_retenue  # noqa: E402
from exporter_reel import _photo_publiee_egale_photo_affichee  # noqa: E402

SITE = "https://www.maisonsanciennes.fr"
CDN = "https://maisons-anciennes.staticlbi.com"
ANCIENNE = f"{SITE}/vente/14-calvados/25-le-manoir/propriete-xviiieme-caen-bayeux-la-mer/752-maison"
NOUVELLE = f"{SITE}/vente/14-calvados/25-le-manoir/1-maison/t10/752-propriete-xviiieme-caen-bayeux-la-mer/"
VOISINE = f"{SITE}/vente/14-calvados/64-trevieres/1-maison/t6/775-secteur-trevieres-maison-ancienne/"
GALERIE_752 = [f"{CDN}/1200xauto/images/biens/1/244c8486/photo_{i}.jpg" for i in range(8)]
GALERIE_775 = [f"{CDN}/1200xauto/images/biens/1/fc94f04c/photo_{i}.jpg" for i in range(6)]
# La vignette de la voisine, dans le bandeau « bien suivant » de l'ancienne page.
VIGNETTE_775 = f"{CDN}/450xauto/images/biens/1/fc94f04c/photo_0.jpg"
LOGO = f"{SITE}/images/modules/partners/interkab.png"


def annonce(ident: str, url: str, photos: list, revue_le: str, **autres) -> dict:
    """Une annonce que le site servirait, seule."""
    bien = {"id": ident, "titre": "Propriété XVIIIème - Caen - Bayeux - la mer",
            "type_bien": "maison", "agence": "Maison Ancienne du Bessin", "agence_url": SITE,
            "url": url, "prix": 419500, "surface_m2": 282, "terrain_m2": 5000, "pieces": 10,
            "commune": "Le Manoir", "code_postal": "14400", "departement": "14",
            "lat": 49.296, "lon": -0.623, "photo": photos[0], "photos": list(photos),
            "vue_le": "2026-08-07", "revue_le": revue_le}
    bien.update(autres)
    return bien


@pytest.fixture(autouse=True)
def sans_liste_d_exclusion(tmp_path, monkeypatch):
    monkeypatch.setattr(exclusions, "FICHIER", tmp_path / "absente.json")


def _bessin():
    ancien = annonce("752-ancien", ANCIENNE, [VIGNETTE_775] + GALERIE_752 + [LOGO], "2026-09-29")
    nouveau = annonce("752", NOUVELLE, GALERIE_752 + [LOGO], "2026-10-17")
    voisine = annonce("775", VOISINE, GALERIE_775 + [LOGO], "2026-10-17",
                      titre="Secteur Trévières - maison ancienne", prix=520000,
                      commune="Trévières", code_postal="14710")
    return ancien, nouveau, voisine


def test_les_deux_exemplaires_d_un_bien_ne_s_effacent_plus_leur_galerie():
    ancien, nouveau, voisine = _bessin()
    mobilier = _photos_de_mobilier([ancien, nouveau, voisine])
    assert photo_retenue(nouveau, mobilier) == GALERIE_752[0], \
        "sa galerie est la sienne, même publiée deux fois"
    assert not set(GALERIE_752) & mobilier
    assert LOGO in mobilier, "le logo, lui, reste du mobilier : trois annonces le portent"


def test_le_site_ne_sert_qu_un_exemplaire_le_plus_recemment_revu():
    ancien, nouveau, voisine = _bessin()
    servis = chargement.biens_servis([ancien, nouveau, voisine])
    assert sorted(b["id"] for b in servis) == ["752", "775"]
    mobilier = _photos_de_mobilier([ancien, nouveau, voisine])
    affichee = {b["id"]: photo_retenue(b, mobilier) for b in servis}
    assert affichee == {"752": GALERIE_752[0], "775": GALERIE_775[0]}, \
        "plus aucune maison illustrée par la photo d'une autre"


def test_l_exemplaire_ecarte_ne_fait_pas_disparaitre_celui_qui_reste():
    """Le tri se fait après les filtres : si l'exemplaire le plus récent est
    écarté pour son compte, l'autre doit rester servi."""
    ancien, nouveau, _ = _bessin()
    nouveau["vendu"] = True
    assert [b["id"] for b in chargement.biens_servis([ancien, nouveau])] == ["752-ancien"]


def test_deux_maisons_d_un_meme_programme_restent_deux():
    """Hamaris vend un type 3 et un type 4 du même programme sous les mêmes
    cinq photos. Rien dans leurs adresses ne dit « même bien » : deux biens,
    chacun illustré."""
    programme = [f"https://www.hamaris.fr/wp-content/uploads/mandres-{i}.jpg" for i in range(5)]
    commun = {"agence": "Hamaris", "agence_url": "https://www.hamaris.fr",
              "commune": "Mandres-la-Côte", "code_postal": "52800", "departement": "52",
              "lat": 48.061, "lon": 5.335, "terrain_m2": 600}
    t4 = annonce("t4", "https://www.hamaris.fr/logements-2/maison-type-4-avec-jardin-et-garage-mandres-la-cote/",
                 programme, "2026-10-17", titre="Maison type 4 avec jardin et garage",
                 prix=150000, surface_m2=84, pieces=4, **commun)
    t3 = annonce("t3", "https://www.hamaris.fr/logements-2/maison-type-3-avec-jardin-et-garage-mandres-la-cote/",
                 programme, "2026-10-17", titre="Maison type 3 avec jardin et garage",
                 prix=130000, surface_m2=72, pieces=3, **commun)
    servis = chargement.biens_servis([t4, t3])
    assert sorted(b["id"] for b in servis) == ["t3", "t4"]
    mobilier = _photos_de_mobilier([t4, t3])
    assert photo_retenue(t4, mobilier) and photo_retenue(t3, mobilier), \
        "les photos du programme sont les leurs, pas du mobilier"


def test_une_vignette_de_voisine_ne_fond_pas_deux_biens():
    """Le bandeau « bien précédent / bien suivant » fait apparaître la photo
    d'une maison sur la page d'une autre : une ou deux images en commun, pas
    une galerie. Elles restent du mobilier, et les deux biens restent deux."""
    _, nouveau, voisine = _bessin()
    nouveau["photos"].append(VIGNETTE_775)
    voisine["photos"].append(VIGNETTE_775)
    assert chargement._galeries_partagees([nouveau, voisine]) == []
    assert VIGNETTE_775 in _photos_de_mobilier([nouveau, voisine])
    assert sorted(b["id"] for b in chargement.biens_servis([nouveau, voisine])) == ["752", "775"]


@pytest.mark.parametrize("une, autre, meme", [
    (ANCIENNE, NOUVELLE, True),
    ("https://www.iadfrance.fr/annonce/maison-vente-1-piece-chateau-renault-33m2/r2102420",
     "https://www.iadfrance.fr/annonce/maison-vente-1-piece-chateau-renault-247m2/r2102420", True),
    ("https://www.safti.fr/annonces/achat/maison/bonneval-28800/1672962",
     "https://www.safti.fr/annonces/achat/maison/alluyes-28800/1672962", True),
    ("https://aude-immo-18.com/vente/1-nerondes/maison/t4/15-maison-nerondes/",
     "https://www.aude-immo-18.com/vente/1-nerondes/maison/t4/15-maison-nerondes/", True),
    # Deux références distinctes ; le seul nombre commun est le code postal.
    ("https://www.ill-immobilier.fr/vente/maison-mitoyenne-2-cotes-6-pieces-charleville-mezieres-08000,VM361",
     "https://www.ill-immobilier.fr/vente/maison-mitoyenne-1-cote-6-pieces-charleville-mezieres-08000,VM717", False),
    ("https://www.hamaris.fr/logements-2/maison-type-4-avec-jardin-et-garage-mandres-la-cote/",
     "https://www.hamaris.fr/logements-2/maison-type-3-avec-jardin-et-garage-mandres-la-cote/", False),
])
def test_meme_bien_demande_la_meme_reference_ou_la_meme_page(une, autre, meme):
    assert chargement._meme_bien({"url": une}, {"url": autre}) is meme


def _safti(ident: str, url: str, photos: list, revue_le: str, **autres) -> dict:
    lieu = {"agence": "Safti (70)", "agence_url": "https://www.safti.fr",
            "titre": "Vente de maison 5 pièces à Bougnon 70170 : 100m², prix 175 000 €",
            "prix": 175000, "surface_m2": 100, "terrain_m2": 800, "pieces": 5,
            "commune": "Vesoul", "code_postal": "70000", "departement": "70",
            "lat": 47.629, "lon": 6.158}
    lieu.update(autres)
    return annonce(ident, url, photos, revue_le, **lieu)


def test_un_numero_d_annonce_de_reseau_designe_un_seul_bien():
    """Safti a publié la même maison sous « bougnon-70170/1705631 », puis sous
    « vesoul-70000/1705631 ». Trois photos seulement leur sont propres — les
    autres reviennent dans le bandeau « biens similaires » des voisines —, trop
    peu pour une galerie partagée. Le numéro d'annonce, lui, ne trompe pas."""
    cdn = "https://cdn.safti.fr/bien-photo/71/05/1705631"
    galerie = [f"{cdn}/{i}/rg_nobn.jpg" for i in range(3)]
    ancien = _safti("s-ancien", "https://www.safti.fr/annonces/achat/maison/bougnon-70170/1705631",
                    galerie, "2026-09-04", commune="Bougnon", code_postal="70170")
    nouveau = _safti("s-nouveau", "https://www.safti.fr/annonces/achat/maison/vesoul-70000/1705631",
                     galerie, "2026-10-18")
    voisine = _safti("s-voisine", "https://www.safti.fr/annonces/achat/maison/vesoul-70000/1699999",
                     [f"https://cdn.safti.fr/bien-photo/69/99/1699999/{i}/rg_nobn.jpg" for i in range(3)],
                     "2026-10-18", prix=210000)
    corpus = [ancien, nouveau, voisine]
    assert chargement._galeries_partagees(corpus) == [], "pas assez de photos pour l'autre règle"
    servis = chargement.biens_servis(corpus)
    assert sorted(b["id"] for b in servis) == ["s-nouveau", "s-voisine"]
    assert photo_retenue(nouveau, _photos_de_mobilier(corpus)) == galerie[0], \
        "et l'exemplaire servi garde ses photos"


def test_le_meme_numero_iad_sous_deux_departements_n_est_servi_qu_une_fois():
    """Notre découpage fait d'IAD une « agence » par département : la même
    annonce, rangée une fois dans l'Aisne et une fois dans la Marne, n'avait
    aucune chance de se voir partager quoi que ce soit."""
    commun = {"commune": "Condé-en-Brie", "code_postal": "02330", "lat": 48.986, "lon": 3.553,
              "prix": 298000, "surface_m2": 291, "terrain_m2": 3000, "pieces": 12,
              "titre": "Maison 12 pièces de 291 m² à Condé-en-Brie", "agence_url": "https://www.iadfrance.fr"}
    aisne = annonce("iad-02", "https://www.iadfrance.fr/annonce/maison-vente-12-pieces-conde-en-brie-291m2/r2104708",
                    ["https://img.iadfrance.fr/a.jpg"], "2026-10-16", agence="IAD France (02)",
                    departement="02", **commun)
    marne = annonce("iad-51", "https://www.iadfrance.fr/annonce/maison-vente-12-pieces-dormans-291m2/r2104708",
                    ["https://img.iadfrance.fr/b.jpg"], "2026-09-30", agence="IAD France (51)",
                    departement="51", **commun)
    autre = annonce("iad-autre", "https://www.iadfrance.fr/annonce/maison-vente-12-pieces-dormans-291m2/r2104709",
                    ["https://img.iadfrance.fr/c.jpg"], "2026-09-30", agence="IAD France (51)",
                    departement="51", **dict(commun, prix=310000))
    assert sorted(b["id"] for b in chargement.biens_servis([aisne, marne, autre])) == ["iad-02", "iad-autre"]


def test_le_fichier_annonce_la_photo_que_le_site_montre():
    """L'export et le chargement doivent trancher pareil, sinon l'audit crie
    « photo annoncée mais jamais affichée » — c'est ainsi que le cas est sorti."""
    publies = _photo_publiee_egale_photo_affichee(list(_bessin()))
    mobilier = _photos_de_mobilier(publies)
    assert {b["id"]: b["photo"] for b in publies}["752"] == GALERIE_752[0]
    assert all(b["photo"] == photo_retenue(b, mobilier) for b in publies)
