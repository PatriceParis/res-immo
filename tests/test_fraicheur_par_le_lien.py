"""Un lien trouvé vivant est une reconstatation ; un lien douteux n'en est pas.

L'audit de fraîcheur ne regardait que `revue_le`, la date où la collecte a vu
le bien pour la dernière fois. Sur les gros départements, tronqués à chaque
passage, la collecte n'atteint plus les mêmes annonces : 336 biens servis
étaient revus pour la dernière fois le 17 août et, depuis la rotation du
vérificateur de liens, allaient être regardés un par un dans les jours
suivants. Sans cette règle, l'audit les aurait comptés périmés APRÈS que leur
page eut été trouvée vivante — contredisant le vérificateur sur 4 % du
catalogue, et criant à la péremption là où le projet venait de constater le
contraire.
"""

import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location("auditer", RACINE / "scripts" / "auditer.py")
auditer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(auditer)

FAMILLE = f"bien non reconstaté depuis plus de {auditer.JOURS_AVANT_PEREMPTION} jours"
URL = "https://www.iadfrance.fr/annonce/maison-x"


def _jours(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _perimes(biens, verifies, morts) -> list[str]:
    audit = auditer.Audit()
    auditer.verifier_fraicheur(biens, audit, verifies=verifies, morts=morts)
    return audit.anomalies.get(FAMILLE, [])


def test_un_lien_trouve_vivant_recemment_reconstate_le_bien():
    bien = {"url": URL, "agence": "IAD France (71)", "revue_le": _jours(60)}
    assert _perimes([bien], verifies={}, morts={}), "sans vérification, il est périmé"
    assert not _perimes([bien], verifies={URL: _jours(3)}, morts={}), (
        "sa page a été ouverte il y a trois jours et trouvée vivante : il est "
        "reconstaté, quoi qu'en dise la collecte")


def test_un_lien_au_journal_des_morts_ne_reconstate_rien():
    """Regardé, oui — mais ce qu'on y a vu est précisément le doute."""
    bien = {"url": URL, "agence": "IAD France (71)", "revue_le": _jours(60)}
    assert _perimes([bien], verifies={URL: _jours(3)},
                    morts={URL: {"constats": 1, "dernier": _jours(3)}})


def test_une_verification_plus_ancienne_que_la_collecte_ne_change_rien():
    bien = {"url": URL, "agence": "IAD France (71)", "revue_le": _jours(60)}
    assert _perimes([bien], verifies={URL: _jours(90)}, morts={})
    assert auditer.reconstate_le(bien, {URL: _jours(90)}, {}) == _jours(60)


def test_sans_journaux_la_regle_d_avant_est_intacte():
    """Les journaux manquent sur une machine neuve : on retombe exactement
    sur la règle précédente, ni plus sévère ni plus laxiste."""
    frais = {"url": URL, "revue_le": _jours(10)}
    vieux = {"url": URL + "-2", "revue_le": _jours(50)}
    assert _perimes([frais, vieux], verifies={}, morts={}) == ["1 bien(s) — ? (1)"]
