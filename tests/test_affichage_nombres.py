"""Les milliers doivent être séparés partout où un nombre s'affiche.

`Intl.NumberFormat("fr-FR")` sépare les milliers par une ESPACE FINE
INSÉCABLE (U+202F), qui mesure un sixième de cadratin. C'est la bonne
typographie française, mais le glyphe manque à plusieurs polices système :
le navigateur la rend alors à largeur nulle. Sur la fiche, « 250 000 € » en
gros corps gardait son espace tandis que « 1479 €/m² », juste en dessous,
avait perdu le sien.

D'où deux fonctions, `euros()` et `nombre()`, qui substituent l'espace
insécable ordinaire (U+00A0). Elles ne valent que si TOUS les affichages
passent par elles : un seul `fmtEuros.format(...)` oublié quelque part, et
le défaut revient sur ce nombre-là seulement — donc de façon presque
invisible à la relecture.

Ce test ne rend pas la page ; il vérifie qu'aucun appel ne contourne les
deux fonctions. C'est exactement ce qui a manqué la première fois.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

APP_JS = RACINE / "app" / "static" / "app.js"
ESPACE_FINE = " "
ESPACE_INSECABLE = " "


def _source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_aucun_affichage_ne_contourne_les_deux_fonctions():
    """Les formateurs bruts ne servent qu'à l'intérieur de `euros` et `nombre`."""
    source = _source()
    appels = [(source[:pos].count("\n") + 1, m)
              for m in ("fmtEuros.format(", "fmtNombre.format(")
              for pos in [i for i in range(len(source))
                          if source.startswith(m, i)]]
    # Deux appels légitimes : le corps de chacune des deux fonctions.
    assert len(appels) == 2, (
        "un affichage de nombre contourne euros()/nombre() aux lignes "
        + ", ".join(f"{ligne} ({motif})" for ligne, motif in appels))


def test_les_deux_fonctions_remplacent_bien_l_espace_fine():
    source = _source()
    for fonction in ("function euros(valeur)", "function nombre(valeur)"):
        debut = source.index(fonction)
        corps = source[debut:source.index("}", debut)]
        assert ".replace(ESPACE_FINE," in corps, f"{fonction} ne substitue plus rien"
    assert f'const ESPACE_FINE = /{ESPACE_FINE}/g;' in source, \
        "ESPACE_FINE ne vise plus U+202F"
    assert f'ESPACE_FINE, "{ESPACE_INSECABLE}"' in source, \
        "la substitution ne produit plus une espace insécable U+00A0"


def test_la_fonction_nombre_ne_s_appelle_pas_elle_meme():
    """Une substitution automatique avait remplacé `fmtNombre.format(` jusque
    DANS le corps de `nombre()` : la fonction s'appelait elle-même, et toute
    fiche portant une surface plantait la page. Le diff se relisait pourtant
    très bien."""
    source = _source()
    debut = source.index("function nombre(valeur)")
    corps = source[debut:source.index("}", debut)]
    assert "return nombre(" not in corps


def test_toutes_les_valeurs_monetaires_de_la_page_sont_formatees():
    """Un prix inséré directement dans le HTML échapperait aux deux fonctions.

    On cherche les interpolations qui affichent un champ de prix sans passer
    par `euros()` — par exemple `${a.prix} €`.
    """
    source = _source()
    brut = re.findall(r"\$\{[^}]*\ba\.(prix|prix_precedent)\b[^}]*\}", source)
    fautifs = [x for x in
               re.findall(r"\$\{([^{}]*\ba\.(?:prix|prix_precedent)\b[^{}]*)\}", source)
               if "euros(" not in x and "?" not in x]
    assert not fautifs, f"prix affiché sans euros() : {fautifs}"
    assert brut, "le test ne trouve plus aucun prix : la page a changé de forme"
