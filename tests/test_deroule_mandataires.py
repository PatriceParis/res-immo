"""Le passage doit dire où part son temps, sans qu'on ait à le deviner.

Trois jours que ce passage ne rapporte rien. J'ai posé deux diagnostics — la
rotation qui affamait IAD, puis la lecture de sitemap sans borne — et corrigé
les deux. L'un et l'autre étaient réels ; aucun n'a suffi.

Le passage du 19 août à 3 h a tourné plus de quarante minutes et n'a même pas
réécrit sa marque de tentative : il meurt donc AVANT le premier réseau, dans
une zone que je ne fais que supposer — les trente-trois appels à l'API des
communes, dont l'échec provoque une sortie silencieuse, sont le suspect le
plus probable, et « probable » est exactement le mot de trop.

Deviner une troisième fois serait répéter la faute qui traverse ce projet :
conclure de ce qu'on n'a pas cherché. Le passage consigne donc son déroulé à
mesure, et c'est lui qui dira où il meurt.

Ces tests exigent deux choses : que le déroulé soit écrit à CHAQUE étape (un
processus tué n'écrit rien à la fin), et que la sortie silencieuse — celle qui
ne laisse aujourd'hui aucune trace — soit précisément celle qu'on consigne.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "collecter_mandataires", RACINE / "scripts" / "collecter_mandataires.py")
COLLECTEUR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(COLLECTEUR)


@pytest.fixture(autouse=True)
def deroule_jetable(tmp_path, monkeypatch):
    """Un test n'écrit jamais dans le dépôt."""
    monkeypatch.setattr(COLLECTEUR, "DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(COLLECTEUR, "_deroule", [])
    monkeypatch.setattr(COLLECTEUR, "_depart", None)
    return tmp_path / "deroule.json"


def test_chaque_etape_est_ecrite_immediatement(deroule_jetable):
    """LE test. Écrire à la fin ne servirait à rien : c'est précisément quand
    le passage est tué qu'on a besoin de savoir où il en était."""
    COLLECTEUR.etape("demarrage", minutes=20)
    assert deroule_jetable.exists(), (
        "rien sur le disque après la première étape : un passage tué ne dirait "
        "toujours rien")
    COLLECTEUR.etape("communes", departements=33)
    consigne = json.loads(deroule_jetable.read_text(encoding="utf-8"))
    assert [e["etape"] for e in consigne] == ["demarrage", "communes"]
    assert consigne[1]["departements"] == 33


def test_la_sortie_silencieuse_est_consignee():
    """L'abstention faute de communes quitte le script en SystemExit(1), que le
    `|| true` du workflow avale. C'est le seul chemin qui laisse aujourd'hui
    exactement zéro trace — donc celui qu'il faut consigner en premier."""
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    corps = source[source.index("def main("):]
    sortie = corps.index("raise SystemExit(1)")
    marque = corps.index("communes_indisponibles")
    assert marque < sortie, (
        "le script s'arrête sans avoir consigné pourquoi : le journal git "
        "restera muet, comme les trois derniers jours")


def test_le_deroule_couvre_les_deux_diagnostics_precedents():
    """Les deux endroits déjà suspectés doivent être mesurés, pour qu'on cesse
    d'en débattre : la lecture du sitemap et le tour de chaque réseau."""
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    for attendu in ("demarrage", "communes", "ordre_des_reseaux",
                    "reseau_debut", "sitemaps_declares", "adresses_du_sitemap",
                    "tentative_notee", "departement", "fin"):
        assert f'etape("{attendu}"' in source, (
            f"l'étape « {attendu} » n'est pas consignée")


def test_un_departement_sans_recolte_dit_pourquoi():
    """Le 20 août, Safti a visité 180 pages et n'en a gardé aucune — 270
    secondes de budget et 180 requêtes chez un tiers pour rien.

    « Illisible » (la page ne s'extrait pas, c'est notre défaut) et « écarté »
    (le bien ne nous convient pas, c'est le fonctionnement normal) appellent
    des réponses opposées. Le total gardé ne les distingue pas ; le détail des
    états, si. Sans lui je devinerais, ce qui m'a déjà coûté trois diagnostics
    faux cette semaine.
    """
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    appel = source[source.index('etape("departement"'):]
    appel = appel[:appel.index(")\n")]
    assert "etats=" in appel, (
        "un département qui ne rapporte rien ne dit pas si les pages étaient "
        "illisibles ou simplement hors cible")


def test_un_motif_garde_un_exemple_de_titre():
    """Le fragment de règle dit quelle alternative refuse ; il ne dit pas si
    elle a RAISON. Safti pourrait publier de vraies pages catalogue, auquel cas
    le filtre fonctionne et il n'y a rien à corriger.

    Sans exemple, trancher demanderait un tour de plus — et chaque tour coûte
    une demi-journée. Trois tours y sont déjà passés.
    """
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    appel = source[source.index('etape("departement"'):]
    assert "exemples=" in appel[:appel.index(")\n")], (
        "aucun exemple de titre n'est conservé : on saura quelle règle refuse, "
        "pas si elle a raison de refuser")
    assert "exemples.setdefault(motif, titre)" in source, (
        "l'exemple doit être le PREMIER titre vu pour ce motif, pas le dernier")


def test_le_deroule_horodate_chaque_etape(deroule_jetable, monkeypatch):
    """Sans les secondes écoulées, on saurait où le passage meurt mais pas ce
    qui a mangé le temps — la question posée depuis trois jours."""
    horloge = [1000.0]
    monkeypatch.setattr(COLLECTEUR.time, "monotonic", lambda: horloge[0])
    monkeypatch.setattr(COLLECTEUR, "_depart", 1000.0)
    horloge[0] = 1042.5
    COLLECTEUR.etape("communes", departements=33)
    consigne = json.loads(deroule_jetable.read_text(encoding="utf-8"))
    assert consigne[0]["seconde"] == 42.5


def test_un_disque_plein_ne_tue_pas_la_collecte(deroule_jetable, monkeypatch):
    """La consigne est un outil de mesure : elle ne doit jamais faire échouer
    le travail qu'elle observe."""
    def refuser(*args, **kwargs):
        raise OSError("disque plein")
    monkeypatch.setattr(Path, "write_text", refuser)
    COLLECTEUR.etape("demarrage")   # ne doit pas lever
