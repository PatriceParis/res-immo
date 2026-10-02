"""Le vérificateur de liens regarde d'abord ce que le site montre.

Le fichier exporté compte un bien sur neuf que le site ne sert pas — hors
terroir, sans département, trop cher, écarté au chargement. Le vérificateur
travaillait sur le fichier entier. Mesuré le 2 octobre, premier lot du palier
des absents : 126 biens regardés, 73 que personne ne verra jamais — pendant
que 199 biens servis attendaient. La famille « non reconstaté depuis 45 jours »
n'a baissé que de 189 à 155 là où le lot aurait pu la ramener bien plus bas.

Un lien de bien non servi n'est pas inutile à vérifier : sa mort confirmée le
sort du fichier. Mais il passe APRÈS, et l'ordre promis — suspects, palier,
rotation — vaut à l'intérieur de chaque moitié.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import liens  # noqa: E402


def _bien(n: int, domaine: str = "iadfrance.fr", **extra) -> dict:
    return {"id": f"{domaine}-{n}", "url": f"https://www.{domaine}/annonce/{n}", **extra}


def test_les_servis_passent_devant_dans_l_ordre_recu():
    annonces = [_bien(1), _bien(2), _bien(3), _bien(4)]
    servis = {"iadfrance.fr-2", "iadfrance.fr-4"}
    montres, autres = liens.servis_d_abord(annonces, servis)
    assert [a["id"] for a in montres] == ["iadfrance.fr-2", "iadfrance.fr-4"]
    assert [a["id"] for a in autres] == ["iadfrance.fr-1", "iadfrance.fr-3"]


def test_rien_n_est_perdu_ni_double():
    annonces = [_bien(n) for n in range(50)]
    montres, autres = liens.servis_d_abord(annonces, {f"iadfrance.fr-{n}" for n in range(0, 50, 3)})
    assert len(montres) + len(autres) == 50
    assert {a["id"] for a in montres} | {a["id"] for a in autres} == {a["id"] for a in annonces}


def test_un_suspect_non_servi_passe_apres_un_bien_servi_ordinaire():
    """Le cas qui gaspillait le budget : un constat de mort en attente sur un
    bien que personne ne voit passait devant toute la rotation des biens
    servis. Il passe désormais après eux — sa confirmation attendra que les
    biens visibles aient eu leur tour."""
    servi, non_servi = _bien(1), _bien(2)
    journal = {non_servi["url"]: {"constats": 1, "dernier": "2026-10-01"}}
    montres, autres = liens.servis_d_abord([servi, non_servi], {servi["id"]})
    ordre = (liens.ordre_de_verification(montres, {}, journal)
             + liens.ordre_de_verification(autres, {}, journal))
    assert [a["id"] for a in ordre] == [servi["id"], non_servi["id"]]


def test_le_script_compose_son_lot_servis_d_abord():
    """Le script lui-même, pas seulement l'aide : c'est lui qui a le budget."""
    spec = importlib.util.spec_from_file_location(
        "verifier_liens", RACINE / "scripts" / "verifier_liens.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    annonces = [_bien(n) for n in range(10)]
    servis = {f"iadfrance.fr-{n}" for n in (7, 8, 9)}
    lot = module.candidats_dans_l_ordre(annonces, {}, {}, servis)
    assert [a["id"] for a in lot[:3]] == ["iadfrance.fr-7", "iadfrance.fr-8", "iadfrance.fr-9"]
    assert len(lot) == 10, "les non servis suivent, ils ne disparaissent pas"
