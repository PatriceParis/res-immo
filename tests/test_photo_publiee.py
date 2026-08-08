"""La photo publiée doit être exactement celle que le site affichera.

Trois signalements de suite sur les images ne venaient pas de l'extraction,
mais d'un désaccord entre deux étapes de la chaîne :

    extraction → vérification (ouvre les images, tranche) → export
                                                          → CHARGEMENT (rechoisit)

Le chargement a le dernier mot, puisque c'est lui qui sert le site. Tant
qu'il pouvait défaire le verdict de la vérification, une fiche publiée avec
une photo vérifiée pouvait s'afficher avec une autre, morte : vingt et une
fiches servies, chez cinq agences, étaient dans ce cas.

Le compte se fait sur les fiches SERVIES, et non sur le fichier d'export —
celui-ci en contient trois cents de plus, que le chargement écarte de toute
façon. Les confondre gonfle le chiffre et fait crier la règle sur des fiches
que personne ne voit.

Ces tests fixent l'accord entre les deux bouts. Chacun échoue sur le code
d'avant — c'est leur seule raison d'exister.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.chargement import _candidates, _photos_de_mobilier, photo_retenue  # noqa: E402

# Le cas réel : Groupe 123 Immo annonce sa vignette en /600xauto/images/…
# (adresse morte, 404) et sert ses vraies photos en /1200xauto/images/biens/….
MORTE = "https://cdn.exemple.com/600xauto/images/1/abc/photo_1.jpg"
VIVANTE = "https://cdn.exemple.com/1200xauto/images/biens/1/abc/photo_1.jpg"
AUTRE = "https://cdn.exemple.com/1600xauto/images/biens/1/abc/photo_2.jpg"


def _annonce(photo, photos, agence="Groupe123immo", n=1):
    return {"id": f"a{n}", "agence": agence, "url": f"https://agence.fr/bien/{n}",
            "photo": photo, "photos": list(photos)}


def _annonce_servie(photo, photos, agence="Agence du Terroir", n=1):
    """Une annonce que le site montrera vraiment.

    L'audit ne juge que celles-là : le fichier d'export contient trois cents
    entrées de plus que le site n'en sert. Un cas de test bâclé passerait donc
    au travers de la règle sans rien prouver — d'où une fiche complète, avec
    sa commune, son département de terroir et une surface plausible.
    """
    return dict(_annonce(photo, photos, agence, n),
                url=f"https://agence.fr/maison-a-vendre-belleme-{n}.html",
                titre=f"Maison en pierre de 120 m² à Bellême ({n})",
                type_bien="maison", prix=250000 + n, surface_m2=120 + n,
                terrain_m2=800, pieces=5, commune="Bellême",
                code_postal="61130", departement="61", lat=48.376, lon=0.565)


def test_la_photo_verifiee_passe_devant_les_autres_candidates():
    """Le défaut exact : la vérification retenait VIVANTE, puis le chargement
    reprenait MORTE parce qu'elle venait en tête de `photos`."""
    annonce = _annonce(VIVANTE, [MORTE, VIVANTE, AUTRE])
    assert _candidates(annonce)[0] == VIVANTE


def test_la_photo_verifiee_ne_parait_qu_une_fois():
    """La mettre en tête ne doit pas la laisser aussi à son rang d'origine :
    la vérification n'ouvre que les six premières candidates, un doublon
    gaspillerait un essai."""
    annonce = _annonce(VIVANTE, [MORTE, VIVANTE, AUTRE])
    assert _candidates(annonce).count(VIVANTE) == 1
    assert _candidates(annonce) == [VIVANTE, MORTE, AUTRE]


def test_charger_ne_change_pas_la_photo_retenue():
    """L'invariant, dit simplement : recharger le catalogue ne doit jamais
    modifier ce qu'il montre."""
    annonce = _annonce(VIVANTE, [MORTE, VIVANTE, AUTRE])
    mobilier = _photos_de_mobilier([annonce])
    assert photo_retenue(annonce, mobilier) == VIVANTE


def test_une_annonce_jamais_verifiee_garde_son_ordre_de_page():
    """Sans photo retenue, rien ne change : on suit l'ordre de la page."""
    annonce = _annonce(None, [MORTE, VIVANTE, AUTRE])
    assert _candidates(annonce) == [MORTE, VIVANTE, AUTRE]


def test_le_mobilier_de_site_reste_ecarte_meme_s_il_a_ete_retenu():
    """Faire passer la photo retenue devant ne doit pas la rendre intouchable :
    dix maisons de l'Agence du Terroir partageaient un même cliché, et c'est
    bien du mobilier — le site a raison de ne pas l'afficher."""
    partagee = "https://agence.fr/photos/926/gran-maison.jpg"
    annonces = [_annonce(partagee, [partagee], agence="Agence du Terroir", n=n)
                for n in range(3)]
    mobilier = _photos_de_mobilier(annonces)
    assert partagee in mobilier
    assert photo_retenue(annonces[0], mobilier) is None


def _auditeur():
    chemin = RACINE / "scripts" / "auditer.py"
    spec = importlib.util.spec_from_file_location("auditer_photo", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_l_audit_signale_une_photo_annoncee_mais_jamais_affichee():
    """Le filet global : même si un futur correctif rouvre l'écart ailleurs
    dans la chaîne, l'audit de chaque collecte le verra."""
    auditeur = _auditeur()
    partagee = "https://agence.fr/photos/926/gran-maison.jpg"
    biens = [_annonce_servie(partagee, [partagee], n=n) for n in range(3)]
    audit = auditeur.Audit()
    auditeur.verifier_photo_publiee_egale_photo_affichee(biens, audit)
    assert audit.anomalies["photo annoncée mais jamais affichée"], \
        "trois maisons illustrées par le même cliché doivent être signalées"


def test_l_audit_se_tait_quand_la_chaine_est_d_accord():
    """Une règle qui crie sur des données saines ne serait pas lue longtemps."""
    auditeur = _auditeur()
    biens = [_annonce_servie(f"https://agence.fr/photos/maison-{n}.jpg",
                             [f"https://agence.fr/photos/maison-{n}.jpg"], n=n)
             for n in range(3)]
    audit = auditeur.Audit()
    auditeur.verifier_photo_publiee_egale_photo_affichee(biens, audit)
    assert audit.total == 0
