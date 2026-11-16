"""Ce que l'interface doit à qui ne la lit pas comme nous.

Ces règles sont nées d'un audit mené avec la skill Hallmark (novembre 2026)
sur la page réelle, rendue dans un navigateur. Les tics de style, on les a
jugés ; ces cinq-là ne sont pas des questions de goût, et c'est pourquoi ils
sont ici plutôt que dans une note : un test les tient, une note s'oublie.

Le projet se savait déjà tenu au contraste — la gamme de score a été validée
daltonisme et contraste. L'audit a montré que l'étiquette DPE, elle, ne
l'avait jamais été.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

STYLE = (RACINE / "app" / "static" / "style.css").read_text(encoding="utf-8")
SCRIPT = (RACINE / "app" / "static" / "app.js").read_text(encoding="utf-8")


def _luminance(couleur: str) -> float:
    couleur = couleur.lstrip("#")
    if len(couleur) == 3:
        couleur = "".join(c * 2 for c in couleur)
    canaux = [int(couleur[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canaux = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in canaux]
    return 0.2126 * canaux[0] + 0.7152 * canaux[1] + 0.0722 * canaux[2]


def contraste(a: str, b: str) -> float:
    haut, bas = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (haut + 0.05) / (bas + 0.05)


def _regle_dpe() -> dict[str, tuple[str, str]]:
    """{« B »: (fond, texte)} lu dans la feuille de style, pas recopié ici."""
    trouve = {}
    for lettre, fond, texte in re.findall(
            r"\.dpe-([A-G])\s*\{\s*background:\s*(#[0-9a-fA-F]{3,6});"
            r"\s*color:\s*(#[0-9a-fA-F]{3,6});", STYLE):
        trouve[lettre] = (fond, texte)
    return trouve


@pytest.mark.parametrize("lettre", list("ABCDEFG"))
def test_l_etiquette_dpe_est_lisible(lettre):
    """Un DPE est un petit texte : le seuil est 4,5:1, pas 3:1.

    B tombait à 3,12:1 et F à 3,36:1 — du blanc sur un vert et un orange trop
    clairs. Les deux fonds ont été assombris en gardant leur teinte, pour que
    l'étiquette reste reconnaissable sur l'échelle officielle.
    """
    regles = _regle_dpe()
    assert lettre in regles, f"la classe .dpe-{lettre} a disparu de la feuille"
    fond, texte = regles[lettre]
    mesure = contraste(fond, texte)
    assert mesure >= 4.5, f"DPE {lettre} : {mesure:.2f}:1 sur {fond}"


def test_les_sept_lettres_sont_bien_toutes_verifiees():
    """Garde-fou du test précédent : s'il ne lisait plus rien, il passerait
    sans rien vérifier. C'est l'erreur commise ailleurs dans ce dépôt."""
    assert len(_regle_dpe()) == 7


def test_le_focus_au_clavier_se_voit():
    """Sans souris, l'anneau de focus EST la position du curseur. Celui du
    navigateur tombait à 1,7:1 sur le vert de l'en-tête, là même où se
    trouvent les premiers liens rencontrés au clavier."""
    assert ":focus-visible" in STYLE
    assert "--focus:" in STYLE and "--focus-clair:" in STYLE


def test_l_anneau_de_focus_tient_le_seuil_sur_les_deux_fonds():
    jetons = dict(re.findall(r"--(focus|focus-clair|marque|fond|carte-fond):\s*(#[0-9a-fA-F]{6})", STYLE))
    # sur les surfaces claires, l'anneau sombre ; sur le vert de marque, le clair
    assert contraste(jetons["focus"], jetons["fond"]) >= 3
    assert contraste(jetons["focus"], jetons["carte-fond"]) >= 3
    assert contraste(jetons["focus-clair"], jetons["marque"]) >= 3


def test_le_mouvement_peut_etre_coupe():
    """Le vertige et la migraine vestibulaire ne négocient pas."""
    assert "prefers-reduced-motion: reduce" in STYLE


def test_le_nom_des_agences_n_est_pas_deforme():
    """« IAD France » s'affichait « IAD FRANCE », « Delafosse & Associée »
    en « DELAFOSSE & ASSOCIÉE ». Sur un site bâti sur l'attribution honnête à
    l'agence, c'est le nom de celui qu'on cite qu'on écrivait de travers."""
    assert "text-transform: uppercase" not in STYLE


def test_la_recherche_dit_quand_elle_echoue():
    """Le défaut le plus grave trouvé par l'audit : la liste restait sur
    « Chargement… » indéfiniment, sans un mot, pendant que le bandeau des
    terroirs s'affichait de son côté. La page n'avait pas l'air cassée, elle
    avait l'air vide — on croit la réponse et on s'en va."""
    assert "signalerPanne" in SCRIPT
    assert "La recherche n'a pas répondu" in SCRIPT
    assert "reessayer" in SCRIPT, "sans bouton, le message est un cul-de-sac"
    # et la panne doit être attrapée là où elle se produit
    bloc = SCRIPT[SCRIPT.index("async function rafraichir()"):]
    bloc = bloc[:bloc.index("\n}")]
    assert "catch" in bloc and "signalerPanne()" in bloc
