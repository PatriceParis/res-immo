"""Se replacer sur la version distante ne doit jamais l'écraser.

Le 17 août, la collecte de 7 h 46 a effacé les 175 annonces IAD de
Saône-et-Loire que le passage mandataires venait d'ajouter trente minutes plus
tôt : le département est passé de 199 à 24, exactement la valeur d'avant.

La cause n'était pas dans le code Python mais dans le script de publication.
Quand un autre passage avait poussé pendant la collecte, celle-ci mettait son
propre `annonces_reel.json` de côté, se calait sur la version distante, puis
**recopiait le sien par-dessus**. Ce n'était pas se replacer, c'était écraser
— et sans rien signaler : le fichier avait l'air normal, il était seulement en
retard d'un passage.

La seule fusion correcte est de REFAIRE l'export : `historique.fusionner`
prend alors le fichier distant comme « précédent » et notre base comme
« nouveau », et sa règle de sortie ne touche qu'aux cibles réellement
visitées. Ce qu'un autre collecteur a rapporté est conservé par construction.

Ces tests lisent les scripts des trois publications. Ils ne remplacent pas un
passage réel, mais ils tiennent l'invariant qui a coûté cent soixante-quinze
annonces, et le tiennent pour les trois — la même faute existait sous deux
formes : l'écrasement ici, l'abandon pur et simple là-bas.
"""


import re
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

PUBLICATIONS = ("collecte.yml", "mandataires.yml", "rattrapage.yml",
                "verifier-liens.yml")


def script_de_publication(fichier: str) -> str:
    """Le script shell de l'étape qui committe, tel qu'il sera exécuté."""
    plan = yaml.safe_load((RACINE / ".github" / "workflows" / fichier)
                          .read_text(encoding="utf-8"))
    scripts = [etape["run"] for travail in plan["jobs"].values()
               for etape in travail["steps"]
               if "run" in etape and "git push" in etape["run"]]
    assert len(scripts) == 1, f"{fichier} : une seule étape doit pousser"
    return scripts[0]


def bloc_de_reprise(script: str) -> str:
    """Ce qui suit le « reset --hard » : la reconstruction d'après conflit."""
    depart = script.index("git reset --hard origin/main")
    return script[depart:]


def avant_la_refusion(reprise: str) -> str:
    """Ce qui se passe entre le « reset --hard » et l'export refait.

    On découpe plutôt que de chercher une ligne `cp` précise : le nom du
    fichier écrasé ne figurait pas sur la ligne `cp` mais dans la liste d'une
    boucle `for f in …`, et un test qui visait la ligne passait à côté de la
    faute qu'il était censé décrire.
    """
    if "scripts/exporter_reel.py" in reprise:
        return reprise[:reprise.index("scripts/exporter_reel.py")]
    return reprise


def test_le_catalogue_n_est_jamais_recopie_sur_la_version_distante():
    """LE test. Remettre notre `annonces_reel.json` après s'être calé sur la
    version distante l'écrase : c'est ce qui a effacé les 175 annonces.

    Entre le reset et l'export refait, le catalogue ne doit être ni restauré,
    ni nommé — il n'a qu'une façon correcte de revenir, et c'est l'export.
    """
    for fichier in PUBLICATIONS:
        reprise = bloc_de_reprise(script_de_publication(fichier))
        assert "annonces_reel.json" not in avant_la_refusion(reprise), (
            f"{fichier} : le catalogue est remis en place à la main après le "
            f"reset, au lieu d'être refusionné par l'export")


def test_l_export_est_refait_apres_s_etre_replace():
    """Sans lui, le passage repart sur le fichier distant sans y verser sa
    propre récolte : elle est perdue en silence."""
    for fichier in PUBLICATIONS:
        reprise = bloc_de_reprise(script_de_publication(fichier))
        assert "scripts/exporter_reel.py" in reprise, (
            f"{fichier} : l'export doit être refait après le reset, "
            f"sinon la récolte du passage est abandonnée")


def test_le_nombre_du_message_est_recalcule():
    """Le commit annonce un nombre d'annonces. Après refusion il change :
    garder l'ancien ferait mentir le journal, seul signal de surveillance."""
    for fichier in PUBLICATIONS:
        reprise = bloc_de_reprise(script_de_publication(fichier))
        assert reprise.index("N=$(python") < reprise.index("git commit"), (
            f"{fichier} : le compte doit être refait avant le message")


def test_le_deroule_du_passage_survit_a_la_reprise():
    """Ce que le passage a MESURÉ doit survivre comme ce qu'il a récolté.

    Le 21 août, le passage mandataires de 15 h a collecté quatre-vingts
    annonces et mesuré, pour la première fois, quel fragment de règle refusait
    les pages Safti. Son push a été rejeté ; la reprise a remis les deux
    journaux qu'elle connaissait, et le « reset --hard » a rendu au déroulé sa
    version PRÉCÉDENTE. La mesure était faite, elle a été jetée.

    J'ai alors lu ce déroulé périmé à deux points d'étape de suite en concluant
    « le passage vient de démarrer » — deux fois faux, et une journée perdue à
    attendre un chiffre déjà obtenu. `collecte.yml` remet bien son propre
    `deroule_collecte.json` ; j'ai ajouté celui des mandataires sans toucher à
    sa reprise.

    Le nom du fichier est lu dans le SCRIPT et non écrit ici : une constante
    renommée d'un côté et pas de l'autre est la faute que ce projet a déjà
    payée quatre fois.
    """
    for fichier, script in (("mandataires.yml", "collecter_mandataires.py"),):
        source = (RACINE / "scripts" / script).read_text(encoding="utf-8")
        deroules = set(re.findall(r'"(deroule_[a-z_]+\.json)"', source))
        assert deroules, f"{script} : aucun déroulé trouvé, le test ne mesure rien"
        reprise = bloc_de_reprise(script_de_publication(fichier))
        for deroule in deroules:
            assert deroule in reprise, (
                f"{fichier} : {deroule} est écrit par le passage mais n'est pas "
                f"remis après le reset — sa mesure est jetée en silence")


def test_les_journaux_du_passage_sont_bien_remis():
    """L'excès inverse : ne rien restaurer perdrait la rotation. Le journal
    des visites dit où reprendre, celui des visites tronquées sur quoi
    s'abstenir — et l'export LIT le second."""
    for fichier, journaux in (
            ("collecte.yml", ("agences_visitees.json", "visites_tronquees.json")),
            ("mandataires.yml", ("mandataires_visites.json", "visites_tronquees.json")),
            ("rattrapage.yml", ("mandataires_visites.json",)),
            ("verifier-liens.yml", ("liens_morts.json", "liens_verifies.json"))):
        reprise = bloc_de_reprise(script_de_publication(fichier))
        avant_export = reprise[:reprise.index("scripts/exporter_reel.py")]
        for journal in journaux:
            assert journal in avant_export, (
                f"{fichier} : {journal} doit être remis AVANT l'export")


def test_le_recensement_est_fusionne_et_non_recopie():
    """`sites.yml` ne publie pas le catalogue : il complète le recensement,
    que `recensement.yml` écrit aussi. Recopier le nôtre par-dessus effacerait
    ce que l'autre passage vient d'y ajouter — la faute du 17 août, transposée
    à un autre fichier. On ne reporte donc que NOS sites, sur les entrées de la
    version distante.
    """
    reprise = bloc_de_reprise(script_de_publication("sites.yml"))
    avant_commit = reprise[:reprise.index("git commit")]
    assert 'cp "$RUNNER_TEMP/' not in avant_commit, (
        "sites.yml recopie ses fichiers sur la version distante au lieu de "
        "les fusionner")
    assert "nos_sites" in avant_commit and "reportes" in avant_commit, (
        "la fusion doit reporter nos sites sur les entrées distantes")
