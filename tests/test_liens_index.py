"""Les liens d'une page d'agence ne doivent pas se perdre sur un « www. ».

Un utilisateur a signalé qu'une maison vue chez son agence manquait au site.
En cherchant pourquoi, on a trouvé que l'Agence Saint-Joseph — comme cent
trente-quatre autres sur deux cent trente-cinq — est déclarée sans le
préfixe `www.` alors que ses pages vivent avec : le site redirige.

Le filtre des liens comparait les hôtes à l'identique. Les liens écrits en
ABSOLU par ces sites (`https://www.agence.fr/vente/maison-123`) ne
correspondaient donc à rien et étaient tous jetés. La panne était silencieuse
parce que les liens RELATIFS, eux, passaient : `urljoin` les reconstruit sur
l'adresse déclarée. Une agence ne livrait plus que ce que son sitemap voulait
bien donner — et rien du tout si elle n'en avait pas.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecteur", RACINE / "scripts" / "collecter_navigateur.py")
collecteur = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collecteur)


class PageFactice:
    """Une page qui rend les href qu'on lui donne — le navigateur en moins."""

    def __init__(self, hrefs):
        self._hrefs = hrefs

    def eval_on_selector_all(self, _selecteur, _script):
        return self._hrefs


def test_un_lien_absolu_vers_www_n_est_plus_jete():
    """LE cas : le site est déclaré sans www, ses liens sont écrits avec."""
    page = PageFactice([
        "https://www.immobiliersaintjoseph.com/vente/maison-ancienne-4-pieces-doudeville-76560,VM2599",
        "https://www.immobiliersaintjoseph.com/vente/maison-de-ville-5-pieces-doudeville-76560,VM2592",
    ])
    trouves = collecteur._liens_page(page, "https://immobiliersaintjoseph.com")
    assert len(trouves) == 2, "les deux annonces doivent être vues"


def test_l_inverse_marche_aussi():
    """Une agence déclarée AVEC www dont les liens n'en portent pas."""
    page = PageFactice(["https://agence.fr/vente/maison-12"])
    assert collecteur._liens_page(page, "https://www.agence.fr/") == [
        "https://agence.fr/vente/maison-12"]


def test_les_liens_relatifs_continuent_de_passer():
    """Ils marchaient déjà : la correction ne doit pas les casser."""
    page = PageFactice(["/vente/maison-de-ville-5-pieces-doudeville-76560,VM2592"])
    trouves = collecteur._liens_page(page, "https://immobiliersaintjoseph.com")
    assert trouves == [
        "https://immobiliersaintjoseph.com/vente/maison-de-ville-5-pieces-doudeville-76560,VM2592"]


def test_un_autre_site_reste_ecarte():
    """Le garde-fou : on suit les liens de l'agence, pas ceux de ses
    partenaires, de son portail d'annonces ou de son hébergeur."""
    page = PageFactice([
        "https://www.seloger.com/annonces/achat/maison-12345",
        "https://portail-partenaire.fr/vente/maison-999",
        "https://sous-domaine.immobiliersaintjoseph.com/vente/maison-77",
    ])
    assert collecteur._liens_page(page, "https://immobiliersaintjoseph.com") == []
