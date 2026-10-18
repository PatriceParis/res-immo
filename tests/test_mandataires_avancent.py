"""Un département de mandataires doit avancer d'un passage à l'autre.

Mesuré le 17 octobre 2026 en Côte-d'Or, au journal du passage de 7 h 34 :
50 pages IAD ouvertes, 2 gardées, 9 vendues, 39 « hors périmètre » — des
maisons du Maine-et-Loire dont le nom de commune, Beaulieu, existe aussi en
Côte-d'Or. Le collecteur sert d'abord les adresses jamais vues, par ordre
alphabétique, et « vue » voulait dire « au catalogue » : les 48 pages
refusées restaient donc jamais vues, et repassaient en tête au passage
suivant. Le département n'avançait que des deux annonces gardées.

Dans le fichier, les biens IAD s'arrêtaient partout à une frontière
alphabétique — « maison-vente-4-pieces-binges » en Côte-d'Or — et une maison
de campagne de cinq pièces à Quemigny-sur-Seine, en ligne chez IAD depuis le
13 août, que l'utilisateur a trouvée sur Leboncoin, n'aurait jamais été
atteinte.

Ces tests font tourner la vraie boucle d'un réseau, sans réseau : le sitemap,
la lecture des pages et la base sont remplacés, la décision reste la sienne.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import historique, mandataires  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "collecteur_mandataires_avance", RACINE / "scripts" / "collecter_mandataires.py")
COLLECTEUR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(COLLECTEUR)

INDEX = mandataires.index_des_communes({"21": ["Beaulieu", "Quemigny-sur-Seine", "Binges"]})
# Six adresses de Côte-d'Or selon leur nom ; les quatre premières, dans l'ordre
# alphabétique, sont des pièges : vendues, ou d'une autre région.
ADRESSES = [
    "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-beaulieu-104m2/r1",
    "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-beaulieu-90m2/r2",
    "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-binges-88m2/r3",
    "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-binges-95m2/r4",
    "https://www.iadfrance.fr/annonce/maison-vente-5-pieces-quemigny-sur-seine-120m2/r2080165",
    "https://www.iadfrance.fr/annonce/maison-vente-6-pieces-binges-150m2/r6",
]
REFUSEES = {ADRESSES[0]: "ecarte:hors_perimetre", ADRESSES[1]: "ecarte:hors_perimetre",
            ADRESSES[2]: "vendu", ADRESSES[3]: "vendu"}


class _Base:
    def commit(self): pass


@pytest.fixture()
def passage(tmp_path, monkeypatch):
    """La boucle d'un réseau, journaux et catalogue dans tmp_path."""
    monkeypatch.setattr(COLLECTEUR, "DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(COLLECTEUR, "_deroule", [])
    monkeypatch.setattr(COLLECTEUR, "_depart", None)
    monkeypatch.setattr(COLLECTEUR, "JOURNAL", tmp_path / "mandataires_visites.json")
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "visites_tronquees.json")
    monkeypatch.setattr(COLLECTEUR, "sitemaps_declares", lambda site: [f"{site}/sitemap.xml"])
    monkeypatch.setattr(COLLECTEUR, "adresses_du_sitemap", lambda *a, **k: (list(ADRESSES), True))
    monkeypatch.setattr(COLLECTEUR, "annonces_deja_connues", lambda: dict(catalogue))
    monkeypatch.setattr(COLLECTEUR.time, "sleep", lambda *_: None)
    catalogue: dict = {}
    ouvertes: list = []

    def enregistrer(conn, annonce, reseau, reaffectees):
        ouvertes.append(annonce["url"])
        etat = REFUSEES.get(annonce["url"], "garde")
        if etat == "garde":
            catalogue[annonce["url"]] = COLLECTEUR.date.today().isoformat()
        return etat, "titre"

    monkeypatch.setattr(COLLECTEUR, "enregistrer_une", enregistrer)

    def lancer(par_departement=2):
        ouvertes.clear()
        args = SimpleNamespace(max_par_departement=par_departement, delai=0, departements=None)
        COLLECTEUR.collecter_un_reseau(_Base(), "iad", mandataires.RESEAUX["iad"], INDEX,
                                       COLLECTEUR.time.monotonic() + 600, args, set())
        return list(ouvertes)

    return lancer


def test_le_departement_avance_au_lieu_de_rouvrir_les_memes_pages_refusees(passage, tmp_path):
    premier = passage()
    assert premier == ADRESSES[:2], "les deux premières adresses jamais vues"
    second = passage()
    assert second == ADRESSES[2:4], "pas les mêmes : les refusées passent derrière"
    troisieme = passage()
    assert ADRESSES[4] in troisieme, "la maison de Quemigny-sur-Seine est atteinte au troisième passage"
    memoire = json.loads((tmp_path / "pages_ecartees_mandataires.json").read_text(encoding="utf-8"))
    assert {u: e["motif"] for u, e in memoire.items()} == {
        ADRESSES[0]: "hors_perimetre", ADRESSES[1]: "hors_perimetre",
        ADRESSES[2]: "vendu", ADRESSES[3]: "vendu"}


SAFTI_INDEX = mandataires.index_des_communes({"52": ["Aigremont", "Langres"]})
SAFTI_CHEZ_NOUS = [f"https://www.safti.fr/annonces/achat/maison/langres-52200/17000{n:02d}"
                   for n in range(3)]
SAFTI_AILLEURS = [f"https://www.safti.fr/annonces/achat/maison/aigremont-30350/16000{n:02d}"
                  for n in range(20)]


def test_safti_ne_consacre_plus_son_lot_aux_homonymes(tmp_path, monkeypatch):
    """Mesuré le 18 octobre 2026 au passage de 7 h 50 : 42 des 50 pages Safti
    ouvertes en Haute-Marne étaient des Aigremont du Gard. La vraie boucle,
    sans réseau : elle doit ouvrir les pages de chez nous, quelques homonymes
    seulement, et tenir le département pour non vu en entier."""
    monkeypatch.setattr(COLLECTEUR, "DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(COLLECTEUR, "_deroule", [])
    monkeypatch.setattr(COLLECTEUR, "_depart", None)
    monkeypatch.setattr(COLLECTEUR, "JOURNAL", tmp_path / "mandataires_visites.json")
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "visites_tronquees.json")
    monkeypatch.setattr(COLLECTEUR, "sitemaps_declares", lambda site: [f"{site}/sitemap.xml"])
    monkeypatch.setattr(COLLECTEUR, "adresses_du_sitemap",
                        lambda *a, **k: (SAFTI_CHEZ_NOUS + SAFTI_AILLEURS, True))
    monkeypatch.setattr(COLLECTEUR, "annonces_deja_connues", lambda: {})
    monkeypatch.setattr(COLLECTEUR.time, "sleep", lambda *_: None)
    ouvertes: list = []

    def enregistrer(conn, annonce, reseau, reaffectees):
        ouvertes.append(annonce["url"])
        return ("ecarte:hors_perimetre" if "-30350/" in annonce["url"] else "garde"), "titre"

    monkeypatch.setattr(COLLECTEUR, "enregistrer_une", enregistrer)
    args = SimpleNamespace(max_par_departement=50, delai=0, departements=None)
    safti = mandataires.RESEAUX["safti"]
    COLLECTEUR.collecter_un_reseau(_Base(), "safti", safti, SAFTI_INDEX,
                                   COLLECTEUR.time.monotonic() + 600, args, set())
    assert set(SAFTI_CHEZ_NOUS) <= set(ouvertes)
    assert sum("-30350/" in u for u in ouvertes) == mandataires.HORS_CIBLE_PAR_PASSAGE
    assert historique.identite({"agence": "Safti (52)", "agence_url": safti["site"]}) \
        in historique.visites_tronquees(), "les homonymes sautés laissent le département tronqué"


def test_la_memoire_des_mandataires_ne_touche_pas_celle_des_agences(passage, tmp_path):
    """Deux journaux : celui des agences est committé par la collecte, celui
    des réseaux par le passage des mandataires. Un passage n'écrit que le sien."""
    passage()
    assert (tmp_path / "pages_ecartees_mandataires.json").exists()
    assert not (tmp_path / "pages_ecartees.json").exists()
