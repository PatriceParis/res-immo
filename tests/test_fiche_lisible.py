"""La fiche d'un bien se lit de haut en bas, et dit d'abord l'essentiel.

Refonte de novembre 2026, sur une demande simple : que les fiches fassent
plus professionnel et se lisent mieux. Ce qui a été trouvé en les mesurant :

- l'action qu'on vient y faire — aller voir l'annonce — était une ligne
  soulignée tout en bas de la fiche, et sur la page servie un bouton placé
  sous quatre mille pixels d'analyse ;
- le titre de l'agence (« Acheter maison de 5 pièces 140 m² 265 000 € à … :
  une annonce … ») redisait le prix, la surface et la commune, sur cinq
  lignes de téléphone ;
- les icônes étaient des émojis, dont le dessin change d'un appareil à
  l'autre ;
- la page servie, celle qu'on partage et qu'on trouve par un moteur, ne
  DESSINAIT pas le score : une ligne de liste et une phrase, rien d'autre.

Ces tests tiennent l'ordre de lecture et les deux rendus ensemble.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages  # noqa: E402

SCRIPT = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")
FICHE = SCRIPT[SCRIPT.index("function ouvrirFiche(id)"):SCRIPT.index("function climatHtml(v)")]

BIEN = {
    "id": "test-1", "titre": "ACHETER MAISON 5 PIECES", "type_bien": "maison",
    "commune": "Le Grand-Lucé", "code_postal": "72150", "prix": 265000,
    "surface_m2": 140, "pieces": 5, "terrain_m2": 11000, "score_total": 59,
    "url": "https://agence.example/annonce/42", "agence": "Arthurimmo",
    "altitude": 130, "temps_voiture_min": 170, "distance_km": 178,
    "train": {"nom": "Écommoy", "km": 14.7, "segment": "C", "minutes_paris": 55,
              "nom_vers_paris": "Le Mans", "km_vers_paris": 23.6,
              "grande_vitesse": True},
    "score_detail": {"classe": "Bien noté", "piliers": {
        "eau": {"points": 6, "max": 12, "libelle": "Autonomie en eau"},
        "energie": {"points": 13, "max": 17, "libelle": "Énergie"},
        "risques": {"points": 11.0, "max": 15, "libelle": "Exposition aux risques"}}},
}


# --- Les icônes ---------------------------------------------------------------

def _traces_js() -> dict[str, str]:
    bloc = SCRIPT[SCRIPT.index("const TRACES = {"):]
    bloc = bloc[:bloc.index("\n};")]
    return dict(re.findall(r"^\s+(\w+): '(.*)',$", bloc, flags=re.MULTILINE))


def test_les_deux_rendus_partagent_le_meme_dessin():
    """Une icône redessinée d'un côté et pas de l'autre, et la fiche de
    l'application ne ressemble plus à la page qu'on en partage."""
    js = _traces_js()
    communs = set(js) & set(pages._TRACES)
    assert len(communs) >= 9, "le jeu commun s'est vidé : le test ne compare plus rien"
    for nom in sorted(communs):
        assert js[nom] == pages._TRACES[nom], f"l'icône « {nom} » a divergé"


def test_la_fiche_n_emploie_plus_d_emoji_pour_icone():
    for emoji in "📍🚗🚆💧📦🔥🥕🌡⚠":
        assert emoji not in FICHE, f"{emoji} est revenu dans la fiche"
    page = pages.page_annonce(BIEN, [], "https://exemple.fr")
    for emoji in "📍💶📐🛏🚉🛡🌡💧":
        assert emoji not in page, f"{emoji} est revenu sur la page servie"


def test_les_faits_de_la_page_gardent_chacun_leur_icone():
    """Le pictogramme de redaction.bloc_de_faits reste la clé ; s'il en
    apparaît un nouveau sans dessin, la ligne perdrait son icône en silence."""
    from app import redaction
    for picto, _ in redaction.bloc_de_faits(BIEN):
        assert picto in pages._PICTO_VERS_ICONE, f"aucune icône pour {picto}"
        assert pages._PICTO_VERS_ICONE[picto] in pages._TRACES


# --- L'ordre de lecture ------------------------------------------------------

def test_la_fiche_porte_notre_titre_et_non_celui_de_l_agence():
    """Dernier texte d'un tiers encore republié sur la fiche depuis le retrait
    du descriptif — et il redisait ce que l'en-tête affiche déjà."""
    assert "a.titre" not in FICHE
    assert 'id="modale-titre">${echap(typeBien(a))} à ${echap(a.commune' in FICHE


def test_l_annonce_passe_avant_l_alerte():
    """L'une mène au bien, l'autre non : elles n'ont ni le même poids ni la
    même place. « Créer mon alerte » avait le seul bouton plein de la fiche."""
    assert FICHE.index('class="btn-principal"') < FICHE.index('class="btn-secondaire"')
    assert FICHE.index('class="btn-principal"') < FICHE.index('class="alerte-bloc"')
    assert FICHE.index("Le score en détail") < FICHE.index('class="alerte-bloc"')


def test_la_page_servie_montre_le_score_et_l_action_avant_le_texte():
    page = pages.page_annonce(BIEN, [], "https://exemple.fr")
    prose = page.index("Que disent les données sur ce bien")
    assert 'class="score-bloc n3"' in page, "59/100 doit porter la couleur n3"
    assert page.index('class="score-bloc') < prose
    assert page.index('class="bouton" href="https://agence.example/annonce/42"') < prose
    # l'explication et ses boutons restent en bas, pour qui a tout lu
    assert page.count('class="bouton" href="https://agence.example/annonce/42"') == 2


def test_la_page_servie_dessine_le_score_critere_par_critere():
    page = pages.page_annonce(BIEN, [], "https://exemple.fr")
    assert "Le score de résilience en détail" in page
    assert page.count('class="p-jauge"') == 3
    assert "<b>11</b>/15" in page, "11.0 doit s'écrire 11"
    assert 'style="width:76%"' in page, "13 sur 17, c'est 76 %"


def test_une_page_sans_detail_de_score_reste_entiere():
    sans = {k: v for k, v in BIEN.items() if k != "score_detail"}
    page = pages.page_annonce(sans, [], "https://exemple.fr")
    assert "Le score de résilience en détail" not in page
    assert "Que disent les données sur ce bien" in page


# --- Les nombres -------------------------------------------------------------

def test_les_distances_s_ecrivent_a_la_francaise():
    """« 14.7 km » côtoyait « 14,7 km » sur la même page, selon que la ligne
    venait du tableau ou de la phrase."""
    page = pages.page_annonce(BIEN, [], "https://exemple.fr")
    # « km » compris : le logo embarqué contient lui aussi des « 3.6 »
    assert "14.7 km" not in page and "23.6 km" not in page
    assert "à 14,7 km" in page
    assert "decimal(a.train.km)" in FICHE and "decimal(a.train.km_vers_paris)" in FICHE
