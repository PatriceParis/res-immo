"""Un constat Géorisques ne se perd pas parce que l'API n'a pas répondu.

Mesuré du 1er au 3 octobre 2026 sur le fichier publié : 427 biens
re-collectés, dont 8 portaient des risques officiels ; les 8 les ont perdus.
La fusion (app/historique.py) repartait de la ligne du jour, et l'étape
d'enrichissement — sans une réponse de l'API depuis fin septembre — n'avait
rien remis. Le compte de biens enrichis baissait donc à chaque passage
(3 596 le 1er octobre, 3 576 le 3) alors qu'aucun n'était sorti du catalogue
pour cette raison. Et un bien sans risques est noté comme un bien sans
risque : la perte remontait sa note.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.historique import fusionner  # noqa: E402

AGENCES = {("Agence A", "")}
OFFICIELS = {"inondation_commune": True, "argile": 2, "portee": "commune",
             "source": "georisques", "nucleaire_km": 42.0, "nucleaire_nom": "Belleville"}
LOCAUX = {"nucleaire_km": 42.0, "nucleaire_nom": "Belleville"}   # calculés à la collecte


def _bien(**champs):
    return {"id": "x", "agence": "Agence A", "prix": 200000, **champs}


def test_un_bien_recollecte_garde_ses_risques_officiels():
    avant = [_bien(vue_le="2026-09-01", risques=OFFICIELS)]
    res = fusionner(avant, [_bien(risques=LOCAUX)], AGENCES, "2026-10-03")
    assert res[0]["risques"]["source"] == "georisques"
    assert res[0]["risques"]["argile"] == 2 and res[0]["risques"]["inondation_commune"]
    assert res[0]["revue_le"] == "2026-10-03", "le bien est bien compté revu"


def test_une_reponse_fraiche_de_l_api_l_emporte():
    """La carte des argiles a été révisée en juillet : quand l'API répond,
    c'est sa réponse du jour qu'on garde, pas l'ancienne."""
    avant = [_bien(vue_le="2026-09-01", risques=OFFICIELS)]
    fraiche = {**OFFICIELS, "argile": 3}
    res = fusionner(avant, [_bien(risques=fraiche)], AGENCES, "2026-10-03")
    assert res[0]["risques"]["argile"] == 3


def test_sans_risques_anciens_rien_n_est_invente():
    avant = [_bien(vue_le="2026-09-01")]                   # jamais enrichi
    res = fusionner(avant, [_bien(risques=LOCAUX)], AGENCES, "2026-10-03")
    assert res[0]["risques"] == LOCAUX


def test_les_valeurs_locales_du_jour_restent_quand_l_ancien_ne_les_avait_pas():
    """L'ancien enrichissement date d'avant le calcul local de la centrale la
    plus proche : on garde ses risques officiels ET la distance du jour."""
    anciens = {k: v for k, v in OFFICIELS.items() if not k.startswith("nucleaire")}
    avant = [_bien(vue_le="2026-09-01", risques=anciens)]
    res = fusionner(avant, [_bien(risques=LOCAUX)], AGENCES, "2026-10-03")
    assert res[0]["risques"]["nucleaire_km"] == 42.0
    assert res[0]["risques"]["source"] == "georisques"
