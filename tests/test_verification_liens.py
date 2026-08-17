"""Un lien mort retire l'annonce — au deuxième constat, jamais au premier.

Le cas d'origine : une maison de Saint-Bérain-sur-Dheune vendue chez IAD, son
lien redirigé vers la liste, sa fiche toujours servie. La règle de sortie ne
pouvait rien : elle s'abstient sur les cibles tronquées, et un département de
six cents annonces parcouru cinquante par cinquante est tronqué à CHAQUE
passage. L'abstention, correcte pour protéger les vivants, immortalisait les
morts.

Ces tests tiennent les deux sens : les morts sortent, mais un site qui tousse
une heure ne perd pas ses annonces — et un lien revenu vivant est innocenté
entièrement.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import liens  # noqa: E402

URL = "https://www.iadfrance.fr/annonce/maison-vente-6-pieces-x-245m2/r1949496"


# --- verdicts ---------------------------------------------------------------

def test_une_erreur_http_est_une_mort():
    assert liens.verdict(404, URL, URL, "")[0] == "mort"
    assert liens.verdict(410, URL, URL, "")[0] == "mort"


def test_une_redirection_ailleurs_est_une_mort():
    """Le sort le plus courant d'une annonce retirée : renvoyer vers la liste."""
    etat, motif = liens.verdict(200, URL, "https://www.iadfrance.fr/annonces", "")
    assert etat == "mort" and "redirigé" in motif


def test_les_redirections_de_pure_forme_ne_comptent_pas():
    """http vers https, www, barre finale : la page n'a pas déménagé."""
    for finale in (URL + "/", URL.replace("https://www.", "https://"),
                   URL.replace("https://", "http://")):
        assert liens.verdict(200, URL, finale, "")[0] == "vivant", finale


def test_une_page_qui_annonce_la_vente_est_reperee():
    assert liens.verdict(200, URL, URL, "Ce bien est vendu !")[0] == "vendu"
    assert liens.verdict(200, URL, URL, "bien sous compromis")[0] == "vendu"
    assert liens.verdict(200, URL, URL, "belle maison vendue avec meubles")[0] == "vivant"


# --- constats ---------------------------------------------------------------

def test_deux_constats_confirment_un_seul_ne_suffit_pas():
    journal = {}
    liens.noter(journal, URL, "mort", "2026-08-17", "HTTP 404")
    assert liens.morts_confirmes(journal) == set()
    liens.noter(journal, URL, "mort", "2026-08-18", "HTTP 404")
    assert liens.morts_confirmes(journal) == {URL}


def test_deux_constats_le_meme_jour_ne_font_qu_un():
    """La mort se confirme dans la durée, pas en rappuyant sur le bouton."""
    journal = {}
    liens.noter(journal, URL, "mort", "2026-08-17", "HTTP 404")
    liens.noter(journal, URL, "mort", "2026-08-17", "HTTP 404")
    assert journal[URL]["constats"] == 1


def test_un_lien_revenu_vivant_est_innocente_entierement():
    """Garder un demi-constat ferait qu'une vraie panne d'un jour, des mois
    plus tard, achèverait une annonce parfaitement en ligne."""
    journal = {}
    liens.noter(journal, URL, "mort", "2026-08-17", "HTTP 404")
    liens.noter(journal, URL, "vivant", "2026-08-18", "")
    assert journal == {}


# --- effet sur le catalogue --------------------------------------------------

def test_le_retrait_ne_touche_que_les_morts_confirmes():
    annonces = [{"id": "a", "url": URL}, {"id": "b", "url": "https://x.fr/b"},
                {"id": "c"}]
    journal = {URL: {"constats": 2, "dernier": "2026-08-18", "motif": "HTTP 404"},
               "https://x.fr/b": {"constats": 1, "dernier": "2026-08-18",
                                  "motif": "HTTP 404"}}
    gardees, retirees = liens.sans_liens_morts(annonces, journal)
    assert [a["id"] for a in gardees] == ["b", "c"]
    assert retirees == 1


def test_les_suspects_passent_devant_dans_la_rotation():
    """Sans cette priorité, le second constat attendrait un tour complet —
    huit jours pour confirmer une mort déjà vue. Avec elle, deux passages."""
    annonces = [{"url": "https://x.fr/ancien"}, {"url": "https://x.fr/suspect"},
                {"url": "https://x.fr/jamais-vu"}]
    verifies = {"https://x.fr/ancien": "2026-08-01",
                "https://x.fr/suspect": "2026-08-17"}
    journal = {"https://x.fr/suspect": {"constats": 1, "dernier": "2026-08-17"}}
    ordre = [a["url"] for a in liens.ordre_de_verification(annonces, verifies, journal)]
    assert ordre[0] == "https://x.fr/suspect"
    assert ordre[1:] == ["https://x.fr/jamais-vu", "https://x.fr/ancien"]


def test_le_journal_ne_garde_pas_les_annonces_deja_sorties():
    journal = {URL: {"constats": 2}, "https://x.fr/encore-la": {"constats": 1}}
    propre = liens.nettoyer(journal, {"https://x.fr/encore-la"})
    assert list(propre) == ["https://x.fr/encore-la"]
