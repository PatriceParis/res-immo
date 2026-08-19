"""Rattacher une adresse à sa commune ne doit pas coûter le pays entier.

Le passage mandataires n'a rien rapporté du 17 au 19 août. J'ai cherché trois
fois au mauvais endroit — la rotation des réseaux, la lecture des sitemaps,
l'API des communes — avant que le déroulé consigné dans le passage ne dise
enfin où il mourait : entre la lecture du sitemap de Safti (28 184 adresses,
0,8 seconde) et le premier département, c'est-à-dire dans
`annonces_a_visiter`.

La cause est mon propre correctif du 17 août. Pour cesser de confondre
« plai**sance** » avec Sancé, j'avais exigé que le nom de commune soit délimité
par des tirets — une expression régulière compilée par essai, essayée contre
chaque commune. Seize mille communes fois vingt-huit mille adresses : quatre
cent cinquante millions de compilations. Mesuré : 37 ms par adresse, soit
17,5 minutes pour le seul Safti, qui dispose de 400 secondes. Correct, et
inutilisable.

Le remède énumère les suites de mots de l'adresse plutôt que les communes du
pays. Ces tests exigent les deux choses qui comptent, dans cet ordre :
d'abord que le résultat soit INCHANGÉ — un correctif de vitesse qui déplace
une annonce de département serait pire que le mal —, ensuite qu'il soit
rapide.
"""

import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import mandataires  # noqa: E402


def rattachement_d_avant(url: str, index: list) -> tuple[str, str] | None:
    """L'implémentation du 17 août, mot pour mot. C'est la référence : le
    correctif doit rendre exactement ses réponses, pas des réponses proches."""
    chemin = mandataires.normaliser(urlparse(url).path)
    for slug, commune, departement in index:
        if re.search(rf"(?:^|-){re.escape(slug)}(?:-|$)", chemin):
            return commune, departement
    return None


def index_realiste() -> list:
    """Des communes emboîtées et homonymes, celles qui font les faux pas."""
    communes = {
        "71": ["Saint-Bérain-sur-Dheune", "Sancé", "Le Creusot", "Chalon-sur-Saône",
               "Montchanin", "Péronne", "Château", "Bérain", "Autun"],
        "80": ["Péronne", "Amiens", "Albert"],
        "21": ["Montbard", "Saint-Rémy", "Beaune", "Dijon"],
        "36": ["Chasseneuil", "Saint-Gaultier", "Rivarennes", "Pellevoisin"],
        "45": ["Sancerre", "Orléans", "Montargis"],
    }
    return mandataires.index_des_communes(communes)


ADRESSES = [
    "https://www.iadfrance.fr/annonce/maison-vente-6-pieces-saint-berain-sur-dheune-245m2/r1949496",
    "https://www.safti.fr/annonces/maison-plaisance-du-touch-31830/12345",
    "https://www.safti.fr/annonces/maison-pontchateau-44160/12345",
    "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-sance-71000/r1",
    "https://www.iadfrance.fr/annonce/maison-vente-5-pieces-peronne-80200/r2",
    "https://www.capifrance.fr/annonces/maison-le-creusot-71200-abc",
    "https://www.safti.fr/annonces/appartement-chalon-sur-saone-71100/9",
    "https://www.safti.fr/annonces/terrain-montbard-21500/7",
    "https://www.iadfrance.fr/annonce/maison-vente-3-pieces-sancerre-18300/r3",
    "https://www.safti.fr/annonces/maison-saint-remy-21500/4",
    "https://www.safti.fr/annonces/maison-chasseneuil-36800/5",
    "https://www.safti.fr/annonces/bureau-nulle-part-99999/6",
    "https://www.safti.fr/annonces/maison-berain-71510/8",
    "https://www.safti.fr/annonces/maison-autun-71400-avec-jardin/11",
]


def test_les_reponses_sont_inchangees():
    """LE test. Un correctif de vitesse qui change une réponse est un bug."""
    index = index_realiste()
    for url in ADRESSES:
        assert mandataires.commune_de_l_adresse(url, index) == \
            rattachement_d_avant(url, index), f"réponse changée pour {url}"


def test_les_reponses_sont_inchangees_sur_un_corpus_tire_au_hasard():
    """Quatorze adresses choisies par moi prouvent surtout ce que j'ai pensé à
    éprouver. On en fabrique donc deux mille par tirage."""
    index = index_realiste()
    mots = ["maison", "vente", "5-pieces", "saint", "berain", "sur", "dheune",
            "sance", "peronne", "creusot", "montbard", "remy", "chalon",
            "saone", "plaisance", "touch", "pontchateau", "123m2", "r1949496",
            "chasseneuil", "sancerre", "autun", "beaune", "dijon", "amiens"]
    tirage = random.Random(19)
    for _ in range(2000):
        chemin = "-".join(tirage.choices(mots, k=tirage.randint(2, 12)))
        url = f"https://www.safti.fr/annonces/{chemin}/x"
        assert mandataires.commune_de_l_adresse(url, index) == \
            rattachement_d_avant(url, index), f"réponse changée pour {url}"


def test_la_frontiere_tient_toujours():
    """La raison d'être du correctif du 17 août ne doit pas être perdue en
    chemin : c'est elle qui a réparé 572 étiquettes fausses sur 1 023."""
    index = index_realiste()
    assert mandataires.commune_de_l_adresse(
        "https://x.fr/annonces/maison-plaisance-du-touch-31830/1", index) is None, \
        "« plaisance » redevient Sancé : la frontière a sauté"
    assert mandataires.commune_de_l_adresse(
        "https://x.fr/annonces/maison-pontchateau-44160/1", index) is None, \
        "« pontchateau » redevient Château"


def test_le_nom_le_plus_long_gagne():
    """L'autre raison d'être : Bérain ne doit pas battre Saint-Bérain-sur-Dheune."""
    index = index_realiste()
    commune, _ = mandataires.commune_de_l_adresse(
        "https://x.fr/annonce/maison-saint-berain-sur-dheune-245m2/r1", index)
    assert commune == "Saint-Bérain-sur-Dheune"


def _duree_du_tri(nombre_de_communes: int, urls: list) -> float:
    communes = {str(d).zfill(2): [f"Commune Numero {n}"
                                  for n in range(nombre_de_communes // 33)]
                for d in range(1, 34)}
    index = mandataires.index_des_communes(communes)
    reseau = {"motif_annonce": re.compile(r"/annonces/")}
    depart = time.monotonic()
    mandataires.annonces_a_visiter(urls, reseau, index)
    return time.monotonic() - depart


def test_le_cout_ne_depend_pas_du_nombre_de_communes():
    """LE test de la panne, et la propriété qui avait cassé.

    Safti publie 28 184 adresses et dispose de 400 secondes ; l'ancienne
    recherche en demandait 17,5 minutes, parce qu'elle essayait chaque commune
    du pays contre chaque adresse. Son coût grandissait donc avec l'index —
    seize mille communes, seize mille essais par adresse.

    On mesure ce rapport plutôt qu'un temps absolu : un seuil en secondes dans
    une suite de cinq cents tests dépend de la charge de la machine, et j'ai vu
    ce test passer en 0,3 s puis échouer à 10 s pour cette seule raison. Le
    rapport, lui, subit la même charge des deux côtés — et c'est exactement la
    propriété qui a coûté trois jours de collecte : trente-deux fois plus de
    communes ne doit pas coûter trente-deux fois plus cher.
    """
    urls = [f"https://www.safti.fr/annonces/maison-vente-5-pieces-lieu-{n}-123m2/r{n}"
            for n in range(1500)]
    petit = _duree_du_tri(500, urls)
    grand = _duree_du_tri(16500, urls)
    assert grand < max(petit, 0.01) * 6, (
        f"trente-trois fois plus de communes coûtent {grand / max(petit, 1e-9):.0f} "
        f"fois plus cher : le tri réessaie tout le pays à chaque adresse, et "
        f"le sitemap de Safti redemandera un quart d'heure")
