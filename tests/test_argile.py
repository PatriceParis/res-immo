"""Le retrait-gonflement des argiles ne triait rien.

Mesuré sur le catalogue : sur 1 311 biens enrichis par Géorisques, 1 298
portent `argile: 1` et 13 portent 0. Aucun ne porte 2 ni 3. Deux conséquences,
toutes deux silencieuses :

- le barème retire un point à 99 % des biens — un critère qui ne discrimine
  personne coûte du calcul et n'apporte rien ;
- la branche `argile >= 2` du barème, et l'alerte « Sols argileux » qui en
  dépend, sont du CODE MORT. L'alerte n'a jamais été affichée à quiconque.

La cause est en amont : le point d'accès interrogé dit seulement qu'un risque
est documenté sur la commune, et le client traduisait ce booléen en « niveau
moyen (1) par prudence ». Or presque toute commune française a de l'argile
quelque part. Géorisques publie un point d'accès dédié qui rend le NIVEAU réel
d'exposition — c'est celui de la carte du BRGM, révisée au 1er juillet 2026
pour intégrer les projections climatiques.

Ces tests décrivent la lecture du niveau. Ils ne peuvent pas prouver la forme
exacte de la réponse — cette session n'a pas de réseau — donc le parseur
encaisse plusieurs écritures plausibles, et une sonde ira relever la vraie.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import georisques  # noqa: E402


def test_les_niveaux_nommes_sont_traduits():
    """Les intitulés du BRGM, tels qu'ils se lisent sur la carte."""
    for libelle, attendu in (("Fort", 3), ("Moyen", 2), ("Faible", 1),
                             ("Nul", 0), ("Très faible", 0)):
        assert georisques.niveau_argile({"exposition": libelle}) == attendu, libelle


def test_les_accents_et_la_casse_ne_changent_rien():
    for ecriture in ("fort", "FORT", "Fort ", "Exposition forte"):
        assert georisques.niveau_argile({"exposition": ecriture}) == 3, ecriture


def test_un_code_numerique_est_accepte():
    """Certaines réponses portent un code plutôt qu'un libellé."""
    assert georisques.niveau_argile({"codeExposition": "3"}) == 3
    assert georisques.niveau_argile({"code_exposition": 2}) == 2


def test_une_reponse_enveloppee_dans_une_liste_est_lue():
    """L'API rend souvent `{"data": [ … ]}` : ne lire que la racine
    renverrait « inconnu » sur une réponse pourtant valide."""
    assert georisques.niveau_argile({"data": [{"exposition": "Moyen"}]}) == 2
    assert georisques.niveau_argile([{"exposition": "Fort"}]) == 3


def test_une_reponse_illisible_ne_devient_pas_un_zero():
    """LE garde-fou. Traduire l'ignorance en « aucun risque » rassurerait à
    tort sur des biens que personne n'a vérifiés — c'est exactement la faute
    qu'on est en train de corriger, dans l'autre sens."""
    for illisible in ({}, None, {"exposition": "?"}, {"autre": 1}, []):
        assert georisques.niveau_argile(illisible) is None, illisible


def test_le_niveau_inconnu_ne_penalise_pas():
    """Un bien dont on ignore l'exposition ne doit être ni puni ni blanchi."""
    from app import scoring
    sans = scoring._pilier_risques({})
    inconnu = scoring._pilier_risques({"argile": None})
    assert sans == inconnu


def test_le_bareme_distingue_enfin_les_niveaux():
    """La raison d'être de tout ce travail : que le critère TRIE."""
    from app import scoring
    fort = scoring._pilier_risques({"argile": 3})
    moyen = scoring._pilier_risques({"argile": 2})
    faible = scoring._pilier_risques({"argile": 1})
    nul = scoring._pilier_risques({"argile": 0})
    assert fort < moyen < faible <= nul


def test_l_alerte_argile_finit_par_s_afficher():
    """Elle n'avait jamais été montrée à personne, faute d'un niveau >= 2."""
    from app import scoring
    fiche = scoring.calculer_score(
        {"features": {}, "risques": {"argile": 3, "portee": "commune"}})
    assert any("argile" in a.lower() for a in fiche["alertes"])
