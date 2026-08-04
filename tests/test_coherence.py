"""Le contrat de cohérence de l'interface (app/coherence.py), et sa garantie.

Deux niveaux :

1. **Le contrat passe** sur un jeu de données de test — l'interface tient ses
   promesses.
2. **Chaque invariant attrape le défaut qu'il est censé attraper.** C'est le
   plus important : un contrôle qui ne détecte rien donne une fausse
   assurance, exactement le travers qu'on cherche à éliminer. On lui présente
   donc une API délibérément menteuse et on exige qu'il le voie.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import coherence  # noqa: E402

BIENS = [
    {
        "id": "c-1", "source": "test", "url": "https://agence.fr/bien/1",
        "titre": "Fermette avec cave et puits", "type_bien": "fermette",
        "description": "Cave voûtée, puits, poêle à bois, verger, grange.",
        "prix": 200000, "surface_m2": 120, "terrain_m2": 6000, "pieces": 6,
        "commune": "Bellême", "code_postal": "61130",
        "lat": 48.373, "lon": 0.560, "altitude": 220,
        "densite_hab_km2": 50, "dpe": "D", "agence": "Terres du Perche",
        "risques": {},
    },
    {
        "id": "c-2", "source": "test", "url": "https://agence.fr/bien/2",
        "titre": "Maison de bourg", "type_bien": "maison",
        "description": "Maison de bourg avec petite cour.",
        "prix": 145000, "surface_m2": 90, "terrain_m2": 200, "pieces": 4,
        "commune": "Beauvais", "code_postal": "60000",
        "lat": 49.430, "lon": 2.081, "altitude": 130,
        "densite_hab_km2": 300, "dpe": "F", "agence": "Oise Immobilier",
        "risques": {"inondation_commune": True},
    },
    {
        "id": "c-3", "source": "test", "url": "https://agence.fr/bien/3",
        "titre": "Longère avec dépendances", "type_bien": "longère",
        "description": "Longère, grange, verger, chauffage au bois.",
        "prix": 265000, "surface_m2": 160, "terrain_m2": 9000, "pieces": 7,
        "commune": "Le Mans", "code_postal": "72000",
        "lat": 47.995, "lon": 0.192, "altitude": 60,
        "densite_hab_km2": 200, "dpe": "E", "agence": "Sarthe Immo",
        "risques": {},
    },
]


@pytest.fixture()
def appeler(tmp_path, monkeypatch):
    """Une façon de poser une question à l'API, sur une base temporaire."""
    monkeypatch.setenv("REFUGE_DB", str(tmp_path / "coherence.db"))

    from fastapi.testclient import TestClient
    from app import db
    from app.chargement import charger_annonces_json
    from app.main import app

    fichier = tmp_path / "biens.json"
    fichier.write_text(json.dumps(BIENS), encoding="utf-8")
    conn = db.connexion()
    charger_annonces_json(conn, fichier)
    conn.close()

    with TestClient(app) as client:
        def _appeler(chemin: str, params: dict) -> dict:
            reponse = client.get(chemin, params=params or None)
            reponse.raise_for_status()
            return reponse.json()
        yield _appeler


# --- 1. Le contrat passe ----------------------------------------------------


def test_toutes_les_promesses_sont_tenues(appeler):
    manquements = []
    for rapport in coherence.verifier(appeler):
        manquements += [f"{rapport.invariant} : {m}" for m in rapport.manquements]
    assert not manquements, "\n".join(manquements)


def test_le_contrat_couvre_chaque_case_a_cocher(appeler):
    """Ajouter une case à l'interface sans l'ajouter au contrat la laisserait
    sans surveillance — c'est ainsi que « hors zone inondable » a pu tomber
    en panne sans que rien ne le signale."""
    index = Path(__file__).resolve().parent.parent / "app" / "static" / "index.html"
    html = index.read_text(encoding="utf-8")
    import re
    cases = set(re.findall(r'type="checkbox" id="f-([\w-]+)"', html))
    couvertes = {p.replace("_", "-") for p in coherence.CASES_A_COCHER}
    assert cases <= couvertes, f"cases non couvertes par le contrat : {cases - couvertes}"


def test_le_contrat_couvre_chaque_tri_propose(appeler):
    index = Path(__file__).resolve().parent.parent / "app" / "static" / "index.html"
    html = index.read_text(encoding="utf-8")
    import re
    bloc = re.search(r'<select id="f-tri".*?</select>', html, re.S)
    proposes = set(re.findall(r'value="(\w+)"', bloc.group(0))) if bloc else set()
    # « nouveauté » se vérifie par une date, pas par un ordre numérique :
    # il est couvert par signaux_de_fraicheur_justifies.
    proposes -= {"nouveaute"}
    assert proposes <= set(coherence.TRIS_ANNONCES), (
        f"tris non couverts : {proposes - set(coherence.TRIS_ANNONCES)}")


# --- 2. Chaque invariant attrape bien son défaut ----------------------------


def _menteur(appeler, transformer):
    """Enveloppe l'API pour lui faire dire une contre-vérité précise."""
    def _appeler(chemin: str, params: dict) -> dict:
        return transformer(chemin, dict(params or {}), appeler(chemin, params))
    return _appeler


def test_detecte_une_pastille_qui_ignore_les_filtres(appeler):
    """LE bug d'origine : « 60 biens » annoncés, 2 dans la liste."""
    def sans_filtres(chemin, params, reponse):
        if chemin == "/api/regions" and params:
            return appeler("/api/regions", {})       # compte sans les filtres
        return reponse

    r = coherence.pastilles_tiennent_leur_promesse(_menteur(appeler, sans_filtres))
    assert not r.tenue, "une pastille qui ignore les filtres doit être détectée"


def test_detecte_un_bien_rattache_a_aucun_terroir(appeler):
    def region_perdue(chemin, params, reponse):
        if chemin == "/api/regions":
            for x in reponse["regions"]:
                x["nb_biens"] = 0
        return reponse

    r = coherence.pastilles_exhaustives(_menteur(appeler, region_perdue))
    assert not r.tenue


def test_detecte_un_compteur_qui_ne_decrit_pas_la_liste(appeler):
    def total_gonfle(chemin, params, reponse):
        if chemin == "/api/annonces" and "total" in reponse:
            reponse["total"] += 40
        return reponse

    r = coherence.compteur_honnete(_menteur(appeler, total_gonfle))
    assert not r.tenue


def test_detecte_une_case_a_cocher_inerte(appeler):
    """« Hors zone inondable » laissait passer 133 biens sur 133."""
    def case_sans_effet(chemin, params, reponse):
        if chemin == "/api/annonces" and params.get("hors_inondation"):
            return appeler("/api/annonces", {"limit": coherence.PLAFOND_API})
        return reponse

    faux = _menteur(appeler, case_sans_effet)
    r = coherence.cases_a_cocher_actives(faux)
    # Le jeu de test est petit : on vérifie le second volet de la promesse —
    # les biens renvoyés doivent tous porter l'atout annoncé.
    assert not r.tenue, "une case qui renvoie des biens sans l'atout doit être détectée"


def test_detecte_un_seuil_numerique_ignore(appeler):
    def budget_ignore(chemin, params, reponse):
        if chemin == "/api/annonces" and params.get("prix_max"):
            return appeler("/api/annonces", {"limit": coherence.PLAFOND_API})
        return reponse

    r = coherence.seuils_numeriques_respectes(_menteur(appeler, budget_ignore))
    assert not r.tenue


def test_detecte_un_tri_qui_ne_trie_pas(appeler):
    def tri_inverse(chemin, params, reponse):
        if chemin == "/api/annonces" and params.get("tri") == "prix":
            reponse["items"] = list(reversed(reponse["items"]))
        return reponse

    r = coherence.tris_ordonnes(_menteur(appeler, tri_inverse))
    assert not r.tenue


def test_detecte_un_bien_sans_lien_vers_l_agence(appeler):
    def lien_perdu(chemin, params, reponse):
        if chemin == "/api/annonces":
            for b in reponse.get("items", []):
                b["url"] = ""
        return reponse

    r = coherence.chaque_bien_mene_a_l_agence(_menteur(appeler, lien_perdu))
    assert not r.tenue


def test_detecte_un_score_qui_n_est_pas_la_somme_de_ses_piliers(appeler):
    def score_gonfle(chemin, params, reponse):
        if chemin.startswith("/api/annonces/"):
            reponse["score_total"] = (reponse.get("score_total") or 0) + 25
        return reponse

    r = coherence.score_egal_a_ses_piliers(_menteur(appeler, score_gonfle))
    assert not r.tenue


def test_detecte_un_ecart_au_marche_invente(appeler):
    def ecart_invente(chemin, params, reponse):
        if chemin == "/api/annonces":
            for b in reponse.get("items", []):
                b["ecart_marche_pct"] = -42
                b["prix_m2"] = 1500
                b["prix_m2_secteur"] = 1500
        return reponse

    r = coherence.ecart_au_marche_reproductible(_menteur(appeler, ecart_invente))
    assert not r.tenue


def test_detecte_une_baisse_de_prix_qui_n_en_est_pas_une(appeler):
    def fausse_baisse(chemin, params, reponse):
        if chemin == "/api/annonces":
            for b in reponse.get("items", []):
                b["prix_precedent"] = 1000       # inférieur au prix courant
        return reponse

    r = coherence.signaux_de_fraicheur_justifies(_menteur(appeler, fausse_baisse))
    assert not r.tenue


def test_detecte_une_agence_annoncee_a_tort(appeler):
    def agence_fantome(chemin, params, reponse):
        if chemin == "/api/agences":
            reponse["agences"].append({"agence": "Agence Fantôme", "nb": 12})
        return reponse

    r = coherence.agences_annoncees_presentes(_menteur(appeler, agence_fantome))
    assert not r.tenue


def test_detecte_des_bornes_de_filtre_trop_etroites(appeler):
    def plafond_trop_bas(chemin, params, reponse):
        if chemin == "/api/meta":
            reponse["prix_max"] = 1000
        return reponse

    r = coherence.bornes_des_filtres_couvrent_les_donnees(
        _menteur(appeler, plafond_trop_bas))
    assert not r.tenue


def test_chaque_invariant_a_sa_preuve_de_detection():
    """Un invariant sans test de détection est un invariant qu'on croit sur
    parole. On exige que chacun ait le sien."""
    couverts = {
        "compteur_honnete", "pastilles_exhaustives",
        "pastilles_tiennent_leur_promesse", "cases_a_cocher_actives",
        "seuils_numeriques_respectes", "tris_ordonnes",
        "chaque_bien_mene_a_l_agence", "score_egal_a_ses_piliers",
        "ecart_au_marche_reproductible", "signaux_de_fraicheur_justifies",
        "bornes_des_filtres_couvrent_les_donnees", "agences_annoncees_presentes",
    }
    declares = {inv.__name__ for inv in coherence.INVARIANTS}
    assert declares == couverts, (
        f"invariant(s) sans preuve de détection : {declares - couverts}")
