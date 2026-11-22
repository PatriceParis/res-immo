"""Les finitions : ce qu'une relecture trait par trait a trouvé.

Passe menée le 22 novembre 2026 avec la skill « unslop » (Damir Sokolovsky,
CC BY 4.0), en mode retouche : le site avait déjà sa charte, il ne s'agissait
pas de le redessiner mais de relever ce qui restait de travers. Chaque test
ci-dessous tient un de ces relevés.

Le plus sérieux n'était pas un défaut de style. La carte disait « excellent »
là où le reste du site dit « très bien noté » — or ce second libellé a été
choisi exprès (voir scoring.classe_score) : la note classe les biens entre
eux, elle ne juge pas la maison. Deux vocabulaires sur un même écran, dont
l'un contredit une précaution que le site s'était donnée.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import scoring  # noqa: E402

STATIQUE = RACINE / "app" / "static"
SCRIPT = (STATIQUE / "app.js").read_text(encoding="utf-8")
ACCUEIL = (STATIQUE / "index.html").read_text(encoding="utf-8")
STYLE = (STATIQUE / "style.css").read_text(encoding="utf-8")


def _sans_commentaires(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", source)


# --- Un seul vocabulaire pour la note ---------------------------------------

def test_la_carte_et_les_filtres_nomment_les_niveaux_comme_la_note():
    """Les quatre libellés viennent de scoring.classe_score, et de lui seul."""
    libelles = [scoring.classe_score(n).lower() for n in (85, 60, 45, 10)]
    assert libelles == ["très bien noté", "bien noté", "moyennement noté", "faiblement noté"]
    legende_carte = SCRIPT[SCRIPT.index('L.DomUtil.create("div", "legende-carte")'):][:700]
    for libelle in libelles:
        assert libelle in legende_carte, f"la carte ne dit pas « {libelle} »"
        assert libelle in ACCUEIL, f"les filtres ne disent pas « {libelle} »"


def test_la_note_n_est_jamais_dite_excellente():
    """« Excellent » qualifie la maison ; la note ne fait que la classer."""
    for nom, source in (("app.js", SCRIPT), ("index.html", ACCUEIL)):
        assert "excellent" not in _sans_commentaires(source).lower(), nom


# --- Les icônes : un seul jeu, y compris pour les petits signes ---------------

def test_plus_de_caractere_en_guise_d_icone():
    """ⓘ, ✕, ▾, ←, →, ↓ : chacun venait de la police du visiteur, donc d'un
    dessin différent sur chaque appareil, à côté d'icônes au trait."""
    for nom, source in (("app.js", SCRIPT), ("index.html", ACCUEIL), ("style.css", STYLE)):
        propre = _sans_commentaires(source)
        # la flèche des projections climatiques (« 11,3 → 13,3 °C ») est du
        # texte : elle se lit « devient », ce n'est pas une icône
        propre = propre.replace('<span class="v-ref">${echap(l.reference)}</span> → ', "")
        for signe in "ⓘ✕▾←→↓":
            assert signe not in propre, f"« {signe} » sert encore d'icône dans {nom}"


def test_les_icones_de_l_accueil_viennent_du_meme_jeu():
    """index.html est statique : ses icônes sont recopiées. Elles doivent être
    celles de TRACES, au tracé près."""
    bloc = SCRIPT[SCRIPT.index("const TRACES = {"):]
    traces = dict(re.findall(r"^\s+(\w+): '(.*)',$", bloc[:bloc.index("\n};")], flags=re.MULTILINE))
    dessins = re.findall(r'<svg class="ico"[^>]*>(.*?)</svg>', ACCUEIL)
    assert len(dessins) >= 4, "l'accueil n'a plus d'icône : le test ne compare rien"
    for dessin in dessins:
        assert dessin in traces.values(), f"icône inconnue du jeu : {dessin[:50]}"


# --- Couleurs, ombres, mouvement ------------------------------------------------

def test_les_ombres_sont_neutres():
    """Celle des vignettes était teintée du vert de la marque."""
    for ombre in re.findall(r"box-shadow:\s*([^;}]+)", _sans_commentaires(STYLE)):
        for r, v, b in re.findall(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", ombre):
            assert max(int(r), int(v), int(b)) - min(int(r), int(v), int(b)) <= 12, (
                f"ombre colorée : {ombre.strip()}")


def test_le_gris_hors_gamme_a_disparu():
    """#6b7663 tombait à 4,4:1 sur le fond crème, sous le seuil du petit
    texte. Le texte secondaire n'a qu'une couleur : --encre-2."""
    assert "#6b7663" not in STYLE.lower()


def test_une_seule_courbe_pour_le_mouvement():
    transitions = re.findall(r"transition:\s*([^;}]+)", _sans_commentaires(STYLE))
    assert transitions, "plus aucune transition : le test ne lit rien"
    for transition in transitions:
        assert "var(--courbe)" in transition and "var(--duree)" in transition, transition
        assert "all" not in transition.split(), "pas de « transition: all »"


# --- Alignements ------------------------------------------------------------

def test_le_pied_de_page_tient_dans_la_colonne_du_contenu():
    """Il partait du bord de la fenêtre : son texte commençait 80 px à gauche
    de l'en-tête et des filtres."""
    pied = re.search(r"\n\.pied \{(.*?)\}", STYLE, flags=re.DOTALL).group(1)
    assert "justify-content: center" in pied and "1232px" in pied


def test_l_enseigne_se_pose_au_pied_de_la_vignette():
    corps = re.search(r"\.fiche-corps \{(.*?)\}", STYLE).group(1)
    enseigne = re.search(r"\.agence-ligne \{(.*?)\}", STYLE, flags=re.DOTALL).group(1)
    assert "flex: 1" in corps and "margin-top: auto" in enseigne


def test_les_deux_curseurs_de_trajet_se_repondent():
    """« Temps de route depuis Paris » tenait sur deux lignes à côté de
    « Paris en train » sur une. La fiche dit déjà « Paris en voiture »."""
    assert "<span>Paris en voiture <output" in ACCUEIL
    assert "<span>Paris en train <output" in ACCUEIL
