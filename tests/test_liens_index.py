"""Les liens d'une page d'agence ne doivent pas se perdre sur un « www. ».

Un utilisateur a signalé qu'une maison vue chez son agence manquait au site.
En cherchant pourquoi, on a trouvé que l'Agence Saint-Joseph — comme cent
trente-quatre autres sur deux cent trente-cinq — est déclarée sans le
préfixe `www.` alors que ses pages vivent avec : le site redirige.

Le filtre des liens compare les hôtes à l'identique. Les liens écrits en
ABSOLU par ces sites (`https://www.agence.fr/vente/maison-123`) ne
correspondent donc à rien et sont tous jetés. La panne est silencieuse parce
que les liens RELATIFS, eux, passent : `urljoin` les reconstruit sur
l'adresse déclarée. Une agence ne livre que ce que son sitemap veut bien
donner — et rien du tout si elle n'en a pas.

Assouplir la comparaison paraissait évident. Ça ne l'était pas : essayé le
11 août, le passage suivant a été tué au bout de son temps, dix-huit annonces
au lieu de cent. Ces tests gardent donc l'état actuel — y compris ce qu'il a
de fautif, dit comme tel — plutôt qu'un état souhaité. Le remède attend une
mesure que la sandbox, sans réseau, ne peut pas faire.
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


def test_un_lien_absolu_vers_www_est_encore_jete():
    """L'état ACTUEL, et il est insatisfaisant — ce test décrit une limite
    connue, pas une intention.

    La comparaison a été assouplie le 11 août pour régler ce cas, puis remise
    en l'état le soir même : le passage suivant a été tué au bout de ses
    trente-quatre minutes, dix-huit annonces au lieu de cent. Sur un site sans
    sitemap, l'index passait de zéro lien à quatre-vingts, dont la plupart ne
    mènent à aucun bien, et chaque navigation perdue coûte jusqu'à vingt-cinq
    secondes.

    Le remède demande de savoir ce que contiennent ces adresses, donc
    d'ouvrir les sites : une sonde GitHub Actions, pas une intuition. En
    attendant, on déclare l'agence AVEC son « www. » dans la configuration,
    ce qui ne touche qu'elle.
    """
    page = PageFactice([
        "https://www.immobiliersaintjoseph.com/vente/maison-4-pieces-doudeville-76560,VM2599",
    ])
    assert collecteur._liens_page(page, "https://immobiliersaintjoseph.com") == []
    # Déclarée avec son www, la même agence retrouve ses liens.
    assert len(collecteur._liens_page(
        page, "https://www.immobiliersaintjoseph.com")) == 1


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
