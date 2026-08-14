"""Un lien qui promet l'annonce doit mener à l'annonce.

Un utilisateur a signalé qu'en cliquant depuis une fiche, il arrivait sur une
liste de plusieurs biens au lieu du sien. C'était exact, et général : le lien
« voir chez l'agence » pointait sur `agence_url`, qui n'est jamais que la
RACINE du site de l'agence — pour les 1143 fiches servies, sans une seule
exception. Le visiteur atterrissait sur une page d'accueil, donc une liste, et
devait y rechercher lui-même le bien qu'il venait de quitter.

L'adresse précise existait pourtant, dans `url`, et le lien qui l'utilise
était relégué sous la mention « Source : iad-france-27 » — notre identifiant
interne, qui ne dit rien à personne.

Ces tests lisent la source plutôt que de rendre la page, à l'image de
tests/test_affichage_nombres.py : ce qu'ils protègent, c'est qu'aucun lien ne
promette le bien en pointant ailleurs.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

APP_JS = RACINE / "app" / "static" / "app.js"
PAGES = RACINE / "app" / "pages.py"


def _fiche() -> str:
    """La section « L'annonce » de la fiche, sans les commentaires."""
    source = APP_JS.read_text(encoding="utf-8")
    debut = source.index("<h4>L'annonce</h4>")
    bloc = source[debut:source.index("</section>", debut)]
    return re.sub(r"/\*.*?\*/", "", bloc, flags=re.DOTALL)


def test_le_lien_de_l_annonce_pointe_sur_l_annonce():
    """`a.url` est l'adresse du bien ; c'est elle que le lien doit porter."""
    bloc = _fiche()
    assert "annonce d'origine" in bloc
    lien = re.search(r'<a href="\$\{echap\((a\.\w+)\)\}"[^>]*>voir l\'annonce', bloc)
    assert lien and lien.group(1) == "a.url", (
        "le lien vers l'annonce doit utiliser a.url, pas a.agence_url")


def test_aucun_lien_ne_promet_le_bien_en_pointant_sur_le_site():
    """LE défaut signalé. `agence_url` mène à la racine du site : tout libellé
    qui laisse croire qu'on y trouvera le bien est un mensonge."""
    bloc = _fiche()
    for lien in re.finditer(r'<a href="\$\{echap\(a\.agence_url\)\}"[^>]*>(.*?)</a>', bloc):
        libelle = lien.group(1).lower()
        assert "annonce" not in libelle, f"« {lien.group(1)} » promet le bien"
        assert "voir chez" not in libelle, f"« {lien.group(1)} » promet le bien"


def test_l_identifiant_interne_ne_s_affiche_plus():
    """« Source : iad-france-27 » ne veut rien dire pour un visiteur ; le nom
    de l'agence, si."""
    bloc = _fiche()
    assert "a.source" not in bloc, "l'identifiant interne reparaît sur la fiche"
    assert "a.agence" in bloc, "le nom de l'agence doit rester affiché"


def test_la_page_servie_par_le_serveur_lie_deja_bien():
    """Elle n'avait pas le défaut — ce test l'empêche de l'attraper. C'est
    aussi elle que suivent les robots d'indexation."""
    source = PAGES.read_text(encoding="utf-8")
    bouton = re.search(r'<a class="bouton" href="\{_e\(bien\.get\("(\w+)"\)\)\}"', source)
    assert bouton and bouton.group(1) == "url"
