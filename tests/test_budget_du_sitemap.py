"""Lire le sitemap doit être borné, et le dire quand il a été écourté.

Le 18 août, le passage mandataires de 15 h a écrit exactement une ligne :
`capifrance:*`, la marque de tentative posée la veille. Aucun département,
aucune annonce, et ni IAD ni Safti n'ont eu leur tour — leur marque à eux n'a
jamais été écrite, donc le processus a été tué avant de leur rendre la main.

La marque de tentative a fait son travail : elle a montré qui avait consommé
le passage. Reste la cause, visible dans `adresses_du_sitemap` : le parcours
de l'arbre de sitemaps n'était borné par RIEN. Des centaines de fichiers chez
les gros réseaux, lus hors budget, jusqu'au couperet de `timeout`.

Deux exigences, donc, et la seconde est la plus importante :

1. La lecture s'arrête à l'échéance qu'on lui donne.
2. Elle DIT qu'elle s'est arrêtée. Un arbre lu à moitié rend moins d'adresses,
   donc moins d'annonces par département — sans rien signaler. La règle de
   sortie prendrait cette liste écourtée pour la liste complète et retirerait
   des annonces jamais cherchées. C'est la faute qui a coûté cent
   soixante-quinze annonces, transposée à la lecture du sitemap.
"""

import importlib.util
import re
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "collecter_mandataires", RACINE / "scripts" / "collecter_mandataires.py")
COLLECTEUR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(COLLECTEUR)

MOTIF = re.compile(r"/annonce/")


def sitemap_xml(*urls: str) -> bytes:
    lignes = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    return f"<urlset>{lignes}</urlset>".encode("utf-8")


def test_la_lecture_s_arrete_a_l_echeance(monkeypatch):
    """LE test. Un arbre interminable ne doit pas manger le passage entier."""
    ouverts = []

    def lire_lentement(url):
        ouverts.append(url)
        # Chaque fichier « coûte » du temps : on avance l'horloge du module.
        COLLECTEUR.time.monotonic = lambda base=[time.monotonic()]: (
            base.__setitem__(0, base[0] + 10) or base[0])
        return sitemap_xml(f"https://x.fr/annonce/{len(ouverts)}")

    monkeypatch.setattr(COLLECTEUR, "lire", lire_lentement)
    depart = COLLECTEUR.time.monotonic()
    adresses, complet = COLLECTEUR.adresses_du_sitemap(
        [f"https://x.fr/s{n}.xml" for n in range(100)], MOTIF,
        fin_prevue=depart + 25)

    assert len(ouverts) < 100, (
        "la lecture a ouvert tout l'arbre malgré l'échéance : c'est ce qui a "
        "consommé le passage du 18 août")
    assert complet is False, "une lecture écourtée doit se déclarer telle"
    assert adresses, "ce qui a été lu avant l'échéance doit être conservé"


def test_un_arbre_entierement_lu_se_declare_complet(monkeypatch):
    """L'autre sens, sans lequel tout serait marqué tronqué en permanence et
    la règle de sortie ne retirerait plus jamais rien."""
    monkeypatch.setattr(COLLECTEUR, "lire",
                        lambda url: sitemap_xml("https://x.fr/annonce/1",
                                                "https://x.fr/annonce/2"))
    adresses, complet = COLLECTEUR.adresses_du_sitemap(
        ["https://x.fr/sitemap.xml"], MOTIF,
        fin_prevue=time.monotonic() + 600)
    assert complet is True
    assert len(adresses) == 2


def test_sans_echeance_le_comportement_est_inchange(monkeypatch):
    """Les appels qui ne passent pas d'échéance ne doivent pas s'arrêter."""
    monkeypatch.setattr(COLLECTEUR, "lire",
                        lambda url: sitemap_xml("https://x.fr/annonce/1"))
    adresses, complet = COLLECTEUR.adresses_du_sitemap(
        ["https://x.fr/sitemap.xml"], MOTIF)
    assert complet is True and len(adresses) == 1


def test_un_sitemap_ecourte_rend_tous_les_departements_tronques():
    """LE test de sûreté. Sans lui, un sitemap à moitié lu ferait retirer des
    annonces jamais cherchées — la faute des cent soixante-quinze annonces.

    On lit la règle telle qu'elle est écrite : la troncature d'un département
    ne doit plus dépendre du seul plafond de lot.
    """
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    corps = source[source.index("def collecter_un_reseau"):]
    regle = next(ligne for ligne in corps.splitlines()
                 if ligne.strip().startswith("tronquee ="))
    assert "sitemap_complet" in regle, (
        f"la troncature ignore l'état du sitemap : {regle.strip()!r} — un "
        f"arbre lu à moitié passerait pour une liste complète")


def test_la_lecture_du_sitemap_ne_prend_pas_tout_le_tour():
    """La moitié de la part pour découvrir, l'autre pour visiter. Sans ce
    partage, un réseau peut finir son tour sans ouvrir une seule annonce."""
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    corps = source[source.index("def collecter_un_reseau"):]
    assert "fin_sitemap" in corps, (
        "la lecture du sitemap n'a pas d'échéance propre : elle peut consommer "
        "la part entière du réseau")
    appel = corps[corps.index("adresses_du_sitemap("):]
    assert "fin_sitemap" in appel[:200], (
        "l'échéance calculée n'est pas passée à la lecture")
