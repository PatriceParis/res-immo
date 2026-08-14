"""La page des petits prix, et le seul angle qui la distingue.

« Maison pas chère à la campagne » est l'une des requêtes les plus tapées du
marché. Des comptes entiers en vivent — un prix incrusté sur une photo, une
commune, rien d'autre — et répondent tous la même chose : une liste de prix
croissants. Aucun ne peut dire si le lieu tiendra dans vingt ans.

C'est la seule chose que nous ayons en propre. Le tri de cette page l'affirme
donc dès la première ligne : le moins cher n'ouvre pas la liste, le mieux noté
l'ouvre. Une page triée par prix croissant serait la millième de son espèce,
et ces tests existent pour qu'elle ne le devienne pas par inadvertance.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import pages, seo  # noqa: E402

BIENS = [
    {"id": "a", "titre": "Longère", "prix": 95000, "score_total": 52,
     "commune": "Herry", "code_postal": "18140", "surface_m2": 98, "pieces": 4,
     "type_bien": "maison"},
    {"id": "b", "titre": "Maison de bourg", "prix": 28000, "score_total": 45,
     "commune": "Athie", "code_postal": "21500", "surface_m2": 64, "pieces": 3,
     "type_bien": "maison"},
    {"id": "c", "titre": "Petite maison", "prix": 15000, "score_total": 20,
     "commune": "Vorly", "code_postal": "18340", "surface_m2": 49, "pieces": 2,
     "type_bien": "maison"},
]
STATS = {"communes": 3, "moins_cher": 15000, "prix_median": 28000,
         "surface_mediane": 64, "bien_notes": 2, "mediane_generale": 30}


def _page(biens=None):
    biens = sorted(biens or BIENS,
                   key=lambda b: (-(b["score_total"]), b["prix"]))
    return pages.page_petits_prix(biens, STATS, "https://exemple.fr")


def _notes(page):
    corps = page[page.index("du mieux noté"):]
    return [int(n) for n in
            re.findall(r"<tr><td>.*?</td><td>.*?</td><td>(\d+)</td></tr>",
                       corps, re.S)]


def test_le_mieux_note_ouvre_la_liste_pas_le_moins_cher():
    """LE point de la page. Le bien à 15 000 € est le moins cher et le plus
    mal noté : s'il apparaît en tête, la page a perdu sa raison d'être."""
    notes = _notes(_page())
    assert notes == sorted(notes, reverse=True)
    assert notes[0] == 52, "la meilleure note doit ouvrir la liste"


def test_le_prix_reste_visible_sur_chaque_ligne():
    """Trier par note n'est pas cacher le prix : c'est ce qu'on est venu
    chercher."""
    page = _page()
    # On formate avec la fonction du site, jamais à la main : les milliers y
    # sont séparés par une espace INSÉCABLE, et un test qui recopie le format
    # à l'espace ordinaire échoue sans rien dire de la page.
    for montant in (95000, 28000, 15000):
        assert seo._euros(montant) in page, f"{montant} € manque au tableau"


def test_la_page_dit_ce_que_le_prix_ne_dit_pas():
    """Un petit prix suppose presque toujours des travaux. Une page qui
    empile des maisons à trente mille euros sans le dire vend du rêve."""
    page = _page()
    assert "travaux" in page
    assert "demandés" in page, "les prix affichés sont ceux demandés"
    assert "commune" in page and "parcelle" in page, "portée des risques"


def test_le_paragraphe_citable_porte_des_chiffres_verifiables():
    """C'est ce qu'une IA reprendra telle quelle : sans chiffres, elle
    reprendra la page d'un autre."""
    texte = seo.reponse_petits_prix(183, 27, 113, 64800, 30, 15000)
    mots = len(texte.split())
    assert 120 <= mots <= 200, f"{mots} mots — hors cible de citation"
    for chiffre in ("183", "27", "113", seo._euros(64800), seo._euros(15000),
                    seo._euros(seo.SEUIL_PETITS_PRIX)):
        assert chiffre in texte, f"{chiffre} manque au paragraphe"
    assert "Géorisques" in texte


def test_la_comparaison_au_catalogue_disparait_si_on_ne_l_a_pas():
    """Sans la médiane générale, « 27 biens au-dessus de 40 » ne se compare à
    rien : la phrase doit se refermer proprement plutôt que rester en l'air."""
    texte = seo.reponse_petits_prix(183, 27, 113, 64800, None, 15000)
    assert "quand la médiane" not in texte
    assert "40 sur 100 ou davantage." in texte


def test_la_page_est_trouvable():
    """Sans entrée au plan du site ni dans llms.txt, la page existe pour
    personne — c'est tout l'objet de l'exercice."""
    plan = seo.sitemap(BIENS, {}, "https://exemple.fr")
    assert "https://exemple.fr/petits-prix" in plan
    resume = seo.llms_txt(1200, {}, "https://exemple.fr")
    assert "/petits-prix" in resume
    assert seo._euros(seo.SEUIL_PETITS_PRIX) in resume


def test_le_lien_vers_la_carte_porte_le_filtre():
    """La carte doit s'ouvrir sur la même sélection. Le lien annonce
    `prix_max` ; app.js doit savoir le lire — voir test_filtres_url.py."""
    assert f"prix_max={seo.SEUIL_PETITS_PRIX}" in _page()
