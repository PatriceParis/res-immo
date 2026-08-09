"""Une description écrite depuis nos données — et rien d'autre.

Trois garanties, chacune répondant à une objection précise.

1. **Rien de l'agence n'y passe.** Sinon ce serait du contenu récupéré, que
   la réécriture n'excuse pas : « modifier légèrement le contenu provenant
   d'autres sources » figure aux règles anti-spam de Google au même titre que
   la copie.
2. **Rien n'est inventé.** C'est l'argument décisif contre le passage par un
   modèle de langage : chaque nombre du texte doit se retrouver dans les
   données. Une qualité inventée sur un bien à deux cent mille euros est un
   mensonge.
3. **Les textes se distinguent entre eux.** Le vrai risque n'est pas la
   duplication avec les agences, c'est la duplication entre nos propres
   pages. La mesure se fait sur le catalogue réel, pas sur un exemple choisi.
"""

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

from app import redaction  # noqa: E402
from app.chargement import _preparer_toutes  # noqa: E402

BIEN = {
    "id": "x-1", "type_bien": "longère", "commune": "Bellême",
    "code_postal": "61130", "departement": "61", "region": "Normandie",
    "prix": 250000, "surface_m2": 120.0, "terrain_m2": 3250.0, "pieces": 5,
    "altitude": 210.0, "densite_hab_km2": 38.0, "dpe": "D",
    "score_total": 46.0, "temps_voiture_min": 110, "distance_km": 140.0,
    "train": {"nom": "Nogent-le-Rotrou", "km": 25.0, "minutes_paris": 105},
    "badges": ["Chauffage au bois", "Puits"],
    "score_detail": {"total": 46, "classe": "Bon potentiel", "piliers": {
        "eau": {"points": 9, "max": 12, "libelle": "Autonomie en eau"},
        "risques": {"points": 4, "max": 15, "libelle": "Exposition aux risques"}}},
    "risques": {"nucleaire_km": 122.6, "nucleaire_nom": "Saint-Laurent",
                "vigilances": ["Retrait-gonflement des argiles"]},
    "texte": "MAGNIFIQUE longère de charme ! Coup de cœur assuré, "
             "lumineuse et pleine de cachet. À visiter sans tarder !!! " * 20,
}
CONTEXTE = {"61": {"nombre": 40, "altitude": 156.0, "surface": 140.0,
                   "terrain": 2000.0, "score": 33.0}}


def _texte(bien=BIEN, contexte=CONTEXTE) -> str:
    return " ".join(redaction.description_longue(bien, contexte))


# --- 1. Rien de l'agence -----------------------------------------------------

def test_aucun_mot_de_l_agence_ne_passe_dans_la_description():
    texte = _texte()
    for prose in ("MAGNIFIQUE", "coup de cœur", "cachet", "sans tarder",
                  "lumineuse", "charme"):
        assert prose.lower() not in texte.lower(), prose


def test_la_description_tient_sans_le_texte_de_l_agence():
    """Preuve que la source n'est pas lue du tout : retirer le champ ne
    change rien au résultat."""
    sans = dict(BIEN)
    sans.pop("texte")
    assert _texte(sans) == _texte()


# --- 2. Rien d'inventé -------------------------------------------------------

def test_chaque_nombre_du_texte_se_retrouve_dans_les_donnees():
    """Le garde-fou qui remplace un modèle de langage.

    Un modèle reformulant « maison de 120 m² » écrirait « spacieuse maison
    baignée de lumière » — la lumière, personne ne l'a mesurée. Ici, tout
    nombre affiché doit provenir d'un champ.
    """
    texte = _texte()
    attendus = {
        210, 156, 54,            # altitude, médiane, écart
        38,                      # densité
        120, 140, 14,            # surface, médiane, écart en %
        3250, 62,                # terrain et son écart
        5, 2083,                 # pièces, prix au m²
        46, 33, 39,              # score, médiane, écart
        9, 12, 4, 15,            # piliers
        110, 1, 50, 175,         # trajet (1 h 50), km estimés
        25, 105, 45,             # gare
        123,                     # centrale
        100,                     # l'échelle de la note, seule constante admise
    }
    trouves = {int(n.replace(" ", "").replace(" ", ""))
               for n in re.findall(r"\d[\d  ]*", texte)}
    orphelins = trouves - attendus
    assert not orphelins, f"nombres sans source dans les données : {orphelins}"


def test_une_donnee_absente_ne_produit_aucune_phrase():
    """Plutôt que d'écrire « altitude inconnue » ou, pire, d'en inventer une."""
    sans_altitude = {k: v for k, v in BIEN.items() if k != "altitude"}
    texte = _texte(sans_altitude)
    assert "altitude" not in texte
    assert "Bellême" in texte, "le reste de la description doit subsister"


def test_un_bien_sans_rien_ne_produit_pas_de_phrase_vide():
    assert redaction.description_longue({"id": "y"}, {}) == []


def test_le_risque_est_toujours_accompagne_de_sa_portee():
    texte = _texte()
    assert "Retrait-gonflement" in texte or "retrait-gonflement" in texte
    assert "commune entière et non pour cette parcelle" in texte
    assert "obligatoire à la vente" in texte


# --- Langue ------------------------------------------------------------------

def test_le_participe_s_accorde_avec_le_type_de_bien():
    """« Maison situé » se remarque à la première lecture."""
    assert "Longère située à" in _texte()
    assert "Moulin situé à" in _texte(dict(BIEN, type_bien="moulin"))
    assert "Château situé à" in _texte(dict(BIEN, type_bien="château"))


def test_les_distances_s_ecrivent_en_francais():
    """« 25.0 km » trahit la fabrication ; « 25 km » et « 2,8 km » non."""
    assert redaction._distance(25.0) == "25 km"
    assert redaction._distance(2.8) == "2,8 km"
    assert "25.0" not in _texte()


def test_un_ecart_negligeable_n_est_pas_mentionne():
    """« 3 % au-dessus de la médiane » est du bruit présenté comme un fait."""
    proche = dict(BIEN, surface_m2=142.0)     # médiane 140 → 1 %
    assert "% de plus" not in _texte(proche)


# --- 3. Distinction entre nos propres pages ----------------------------------

def _catalogue():
    fichier = RACINE / "data" / "annonces_reel.json"
    if not fichier.exists():
        pytest.skip("catalogue absent")
    return _preparer_toutes(None, json.loads(fichier.read_text(encoding="utf-8")))


def test_les_descriptions_du_catalogue_reel_se_distinguent():
    """Le risque véritable, mesuré là où il se produit.

    Neuf cent quatre-vingt-treize fiches sur un même gabarit diraient la même
    chose, et seraient à bon droit jugées sans valeur. On exige que la
    quasi-totalité des textes soient uniques, et qu'ils portent assez de
    matière propre pour qu'un lecteur les distingue.
    """
    biens = _catalogue()
    contexte = redaction.contexte_departemental(biens)
    textes = [" ".join(redaction.description_longue(b, contexte)) for b in biens]
    textes = [t for t in textes if t]

    uniques = len(set(textes))
    assert uniques / len(textes) >= 0.98, (
        f"{len(textes) - uniques} description(s) identique(s) sur {len(textes)}")

    # Une phrase de gabarit se répète forcément ; ce qui compte est la part
    # de matière PROPRE. On la mesure sur les nombres, qui portent les faits.
    chiffres = [len(set(re.findall(r"\d+", t))) for t in textes]
    mediane = sorted(chiffres)[len(chiffres) // 2]
    assert mediane >= 8, (
        f"médiane de {mediane} nombres distincts par fiche : trop de gabarit, "
        f"pas assez de fait")


def test_aucune_description_du_catalogue_reel_n_est_squelettique():
    """Une fiche de deux lignes serait une page maigre — mieux vaut alors
    savoir combien elles sont."""
    biens = _catalogue()
    contexte = redaction.contexte_departemental(biens)
    courtes = [b for b in biens
               if len(" ".join(redaction.description_longue(b, contexte))) < 200]
    assert len(courtes) / len(biens) <= 0.05, (
        f"{len(courtes)} fiches sur {len(biens)} ont moins de 200 signes")
