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


def test_un_nom_plus_long_ailleurs_en_france_n_est_plus_ouvert(tmp_path, monkeypatch):
    """Mesuré le 19 octobre 2026 au passage de 20 h 24 : 151 des 262 pages IAD
    ouvertes étaient « hors périmètre », d'abord par des noms tronqués. La
    vraie boucle, avec un index de toute la France : la page de
    Saint-Laurent-le-Minier, dans le Gard, n'est plus ouverte pour
    Saint-Laurent."""
    monkeypatch.setattr(COLLECTEUR, "DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(COLLECTEUR, "_deroule", [])
    monkeypatch.setattr(COLLECTEUR, "_depart", None)
    monkeypatch.setattr(COLLECTEUR, "JOURNAL", tmp_path / "mandataires_visites.json")
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "visites_tronquees.json")
    chez_nous = "https://www.iadfrance.fr/annonce/maison-vente-4-pieces-saint-laurent-90m2/r1"
    ailleurs = "https://www.iadfrance.fr/annonce/maison-vente-10-pieces-saint-laurent-le-minier-82m2/r2"
    monkeypatch.setattr(COLLECTEUR, "sitemaps_declares", lambda site: [f"{site}/sitemap.xml"])
    monkeypatch.setattr(COLLECTEUR, "adresses_du_sitemap", lambda *a, **k: ([chez_nous, ailleurs], True))
    monkeypatch.setattr(COLLECTEUR, "annonces_deja_connues", lambda: {})
    monkeypatch.setattr(COLLECTEUR.time, "sleep", lambda *_: None)
    ouvertes: list = []

    def enregistrer(conn, annonce, reseau, reaffectees):
        ouvertes.append(annonce["url"])
        return "garde", "titre"

    monkeypatch.setattr(COLLECTEUR, "enregistrer_une", enregistrer)
    france = {"21": ["Saint-Laurent"], "30": ["Saint-Laurent-le-Minier"]}
    index = mandataires.index_des_communes(france, COLLECTEUR.DEPARTEMENTS_CIBLES)
    args = SimpleNamespace(max_par_departement=50, delai=0, departements=None)
    COLLECTEUR.collecter_un_reseau(_Base(), "iad", mandataires.RESEAUX["iad"], index,
                                   COLLECTEUR.time.monotonic() + 600, args, set())
    assert ouvertes == [chez_nous]


def test_la_liste_des_communes_de_france_se_lit_par_departement(monkeypatch):
    """Un seul appel à l'API officielle, population comprise ; rien du tout si
    elle ne répond pas, pour que le passage revienne à nos seules communes."""
    reponse = json.dumps([{"nom": "Beaulieu", "codeDepartement": "21", "population": 312},
                          {"nom": "Saint-Laurent-le-Minier", "codeDepartement": "30",
                           "population": 380},
                          {"nom": "Beaulieu", "codeDepartement": "49"},
                          {"nom": "Quemigny-sur-Seine", "codeDepartement": "21",
                           "population": 118}]).encode()
    monkeypatch.setattr(COLLECTEUR, "lire", lambda url: reponse)
    par_dept, populations = COLLECTEUR.communes_de_france()
    assert par_dept == {
        "21": ["Beaulieu", "Quemigny-sur-Seine"], "30": ["Saint-Laurent-le-Minier"],
        "49": ["Beaulieu"]}
    assert populations[("21", "Beaulieu")] == 312
    assert populations[("49", "Beaulieu")] == 0, "population absente : zéro, pas d'erreur"
    monkeypatch.setattr(COLLECTEUR, "lire", lambda url: b"")
    assert COLLECTEUR.communes_de_france() == ({}, {})
    monkeypatch.setattr(COLLECTEUR, "lire", lambda url: b"<html>panne</html>")
    assert COLLECTEUR.communes_de_france() == ({}, {})


def test_les_anciennes_communes_se_lisent_dans_leur_fichier(monkeypatch, tmp_path):
    """Le fichier livré porte les cas mesurés, et pas les communes
    d'aujourd'hui. Absent ou abîmé, il ne rend rien : les adresses se lisent
    alors comme avant lui."""
    anciennes = COLLECTEUR.communes_anciennes()
    assert "Pierrefitte-sur-Seine" in anciennes["93"]
    assert "Saint-Denis-sur-Ouanne" in anciennes["89"]
    assert "Laduz" in anciennes["89"] and "Valravillon" not in anciennes["89"]
    fichier = tmp_path / "communes_anciennes.json"
    monkeypatch.setattr(COLLECTEUR, "ANCIENNES", fichier)
    assert COLLECTEUR.communes_anciennes() == {}
    for contenu in ("<html>panne</html>", '{"communes": ["Laduz"]}', '["Laduz"]'):
        fichier.write_text(contenu, encoding="utf-8")
        assert COLLECTEUR.communes_anciennes() == {}


# La fiche Safti d'Houlbec-Cocherel du 28 octobre 2026, réduite à l'essentiel :
# le titre lu ne porte pas de code postal, la page ne le dit qu'une fois, et
# les « biens similaires » répètent celui de Bennecourt. Pas de <title> : ce
# que le robot en reçoit ne confirmait rien (voir mandataires.code_postal_confirme).
FICHE_HOULBEC = (
    "<html><head>"
    '<meta property="og:title" content="Maison à vendre à HOULBEC-COCHEREL de 118m²">'
    "</head><body><h1>Maison à vendre à HOULBEC-COCHEREL de 118m²</h1>"
    "<p>189 000 €</p><p>Houlbec-Cocherel - 27120</p>"
    "<p>Surface habitable : 118m²</p><p>Terrain : 1 935m²</p>"
    "<p>Au calme d'une impasse, cette maison à rénover bénéficie d'un cadre "
    "verdoyant, sur un terrain boisé d'environ 2 000 m².</p>"
    "<h2>Ce bien vous est proposé par :</h2><p>Vernon (27200)</p>"
    "<h3>Maison - 5 pièces - 117m²</h3><p>Lommoye (78270)</p><p>203 000 €</p>"
    "<h3>Maison - 6 pièces - 126m²</h3><p>Bennecourt (78270)</p><p>200 000 €</p>"
    "<h3>Maison - 5 pièces - 79m²</h3><p>Bennecourt (78270)</p><p>195 000 €</p>"
    "</body></html>")


def test_le_code_postal_d_un_bien_voisin_n_ecarte_plus_une_maison_de_chez_nous(monkeypatch):
    """Le texte de la fiche cite plus souvent Bennecourt (78270) que la maison
    elle-même : elle était écartée comme hors de nos terroirs. L'adresse et le
    titre de la page disent tous deux 27120 — elle reste dans l'Eure."""
    url = "https://www.safti.fr/annonces/achat/maison/houlbec-cocherel-27120/1728334"
    gardees = []
    monkeypatch.setattr(COLLECTEUR, "lire", lambda adresse: FICHE_HOULBEC.encode())
    monkeypatch.setattr(COLLECTEUR.db, "upsert_annonce", lambda conn, a: gardees.append(a))
    monkeypatch.setattr(COLLECTEUR, "_geocoder", lambda *a: (49.04, 1.36, None, None, None))
    monkeypatch.setattr(COLLECTEUR, "_geocoder_cp", lambda *a: None)
    monkeypatch.setattr(COLLECTEUR, "_altitude", lambda *a: 120)
    monkeypatch.setattr(COLLECTEUR, "_densite", lambda *a: 40)
    annonce = {"url": url, "commune": "Houlbec-Cocherel", "departement": "27",
               "agence": "Safti (27)"}
    etat, _ = COLLECTEUR.enregistrer_une(None, annonce, mandataires.RESEAUX["safti"], set())
    assert etat == "garde"
    assert [(a["code_postal"], a["departement"], a["agence"]) for a in gardees] == [
        ("27120", "27", "Safti (27)")]


def test_la_memoire_des_mandataires_ne_touche_pas_celle_des_agences(passage, tmp_path):
    """Deux journaux : celui des agences est committé par la collecte, celui
    des réseaux par le passage des mandataires. Un passage n'écrit que le sien."""
    passage()
    assert (tmp_path / "pages_ecartees_mandataires.json").exists()
    assert not (tmp_path / "pages_ecartees.json").exists()
