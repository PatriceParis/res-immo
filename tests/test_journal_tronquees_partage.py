"""Le journal des tronquées doit décrire le passage ENTIER, pas son dernier réseau.

Le 25 août, « IAD France (71) » est retombé de 464 annonces à 5. Le déroulé
montre pourtant le département visité ET marqué :

    iad 71  vis=50 gard=4 tronquee=True

La marque a bien été posée. Elle a été effacée douze minutes plus tard.

`noter_visite_tronquee` réécrit tout le fichier à chaque appel — c'est voulu :
un journal qui traînerait d'un passage à l'autre ferait s'abstenir la règle de
sortie sur des cibles qu'on vient de parcourir en entier. Mais l'ensemble qu'on
lui passait était LOCAL à un réseau. Safti repartait donc d'un ensemble vide et
sa première écriture effaçait les marques d'IAD, posées quelques minutes plus
tôt dans le même passage. L'export, lancé ensuite, a trouvé « IAD France (71) »
absent du journal, l'a cru parcouru en entier, et a retiré les 463 annonces
qu'il n'avait pas revues parmi les cinquante visitées.

Troisième incident de la même famille en trois jours, et le troisième mécanisme
distinct : la cible tronquée non marquée (sitemap écourté), la cible fortuite
atteinte par ricochet, et maintenant la marque posée puis effacée. Le point
commun n'est pas le code, c'est la question : « avons-nous vraiment regardé
là ? » — et chaque fois la réponse était non, sans que rien ne le dise.

Le journal ne décrit qu'un passage. Il doit en décrire la TOTALITÉ.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

SOURCE = (RACINE / "scripts" / "collecter_mandataires.py").read_text(encoding="utf-8")


def corps(nom: str) -> str:
    debut = SOURCE.index(f"def {nom}(")
    reste = SOURCE[debut:]
    fin = reste.index("\ndef ", 1) if "\ndef " in reste[1:] else len(reste)
    return reste[:fin]


def test_l_ensemble_des_tronquees_vient_de_l_appelant():
    """LE test. Créé dans `collecter_un_reseau`, il repart vide à chaque
    réseau — et la première écriture du suivant efface le précédent."""
    reseau = corps("collecter_un_reseau")
    signature = reseau[:reseau.index(":\n")]
    assert "tronquees" in signature, (
        "collecter_un_reseau doit RECEVOIR l'ensemble des tronquées, pas le "
        "fabriquer : fabriqué, il repart vide à chaque réseau")
    assert "tronquees: set = set()" not in reseau, (
        "l'ensemble est recréé dans collecter_un_reseau : le réseau suivant "
        "effacera les marques du précédent, comme Safti a effacé IAD 71")


def test_le_passage_partage_un_seul_ensemble():
    """`main` doit le créer une fois et le passer à chaque réseau."""
    principal = corps("main")
    assert "tronquees: set = set()" in principal, (
        "aucun ensemble partagé n'est créé pour le passage")
    appel = principal[principal.index("collecter_un_reseau("):]
    assert "tronquees" in appel[:appel.index("\n\n") if "\n\n" in appel else 200], (
        "l'ensemble partagé n'est pas transmis au réseau")


def test_la_marque_est_ecrite_apres_avoir_ete_completee():
    """Écrire avant d'ajouter les cibles fortuites laisserait la marque
    incomplète — c'est la faute d'avant-hier, qu'il ne faut pas rouvrir."""
    reseau = corps("collecter_un_reseau")
    fusion = reseau.index("tronquees |= reaffectees")
    ecriture = reseau.index("historique.noter_visite_tronquee(tronquees)")
    assert fusion < ecriture


def test_le_journal_ne_traine_pas_d_un_passage_a_l_autre():
    """L'excès inverse, tout aussi silencieux : un journal cumulatif ferait
    s'abstenir la règle de sortie sur des cibles réellement parcourues, et
    plus aucune annonce vendue ne quitterait jamais le catalogue."""
    from app import historique
    assert "Réécrit entièrement" in (historique.noter_visite_tronquee.__doc__ or ""), (
        "la réécriture intégrale à chaque passage doit rester documentée : "
        "c'est elle qui empêche le journal de devenir cumulatif")
