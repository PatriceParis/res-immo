"""Une agence lente ne doit pas prendre le tour des autres.

Un passage de trente-quatre minutes n'a visité que TROIS agences pour dix-huit
biens : le budget global disait quand s'arrêter, jamais comment répartir. Le
budget par agence a été écrit pour cela — mais écrit sans pouvoir être
exécuté, le poste de développement n'ayant pas le réseau. Deux passages
programmés n'ont rien poussé ensuite, et rien ne permettait de dire si la
cause était là ou ailleurs.

Ces tests font tourner la vraie boucle de collecte sur un faux navigateur :
pas de réseau, pas de Chromium, mais le code qui décide, lui, est bien le
sien. C'est ce qui manquait pour ne plus corriger à l'aveugle.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

collecteur = pytest.importorskip(
    "scripts.collecter_navigateur",
    reason="Playwright absent : le module de collecte ne s'importe pas")


class _FausseHorloge:
    """Le temps n'avance que quand on le lui demande — les tests sont donc
    instantanés, et la lenteur d'une agence se décrète au lieu de s'attendre."""

    def __init__(self):
        self.maintenant = 1000.0

    def __call__(self):
        return self.maintenant

    def avancer(self, secondes):
        self.maintenant += secondes


class _FaussePage:
    def goto(self, *a, **k): pass
    def wait_for_timeout(self, *a, **k): pass
    def content(self): return "<html></html>"
    def eval_on_selector_all(self, *a, **k): return []
    def set_default_timeout(self, ms): pass
    def set_default_navigation_timeout(self, ms): pass

    @property
    def mouse(self):
        return self

    def wheel(self, *a, **k): pass


class _FauxNavigateur:
    def new_context(self, **k): return self
    def new_page(self): return _FaussePage()
    def close(self): pass


class _FauxPlaywright:
    def __enter__(self): return self
    def __exit__(self, *a): return False

    @property
    def chromium(self):
        return self

    def launch(self, **k): return _FauxNavigateur()


@pytest.fixture()
def collecte(tmp_path, monkeypatch):
    """La vraie boucle de `main()`, sans réseau ni base réelle."""
    (tmp_path / "data").mkdir()
    horloge = _FausseHorloge()
    monkeypatch.setattr(collecteur.time, "monotonic", horloge)
    monkeypatch.setattr(collecteur.time, "sleep", lambda *_: None)
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur, "_noter_visite", lambda *a, **k: None)
    # Sans cela, chaque test qui exécute main() écrit le VRAI journal de
    # déroulé — et un `git add -A` a committé « Bloquée / Saine » par-dessus
    # le déroulé d'une collecte réelle. Un test qui touche au dépôt n'est pas
    # un test, c'est un effet de bord avec un nom rassurant.
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(collecteur.db, "connexion",
                        lambda: collecteur.db.connexion.__wrapped__()
                        if hasattr(collecteur.db.connexion, "__wrapped__") else _FausseBase())
    return horloge


class _FausseBase:
    def execute(self, *a, **k): return self
    def fetchone(self): return None
    def fetchall(self): return []
    def commit(self): pass
    def close(self): pass


def _lancer(monkeypatch, horloge, agences, secondes_par_page, minutes_par_agence=4.0,
            minutes_max=28.0):
    """Fait tourner la collecte et renvoie les agences réellement visitées."""
    visitees = []

    monkeypatch.setattr(collecteur, "_cibles",
                        lambda *a, **k: [{"nom": n, "site": f"https://{n}.fr"}
                                         for n in agences])

    def urls(page, cible, base, maxi, fin_prevue=0.0):
        visitees.append(cible["nom"])
        return [f"{base}/bien-{i}" for i in range(30)]

    monkeypatch.setattr(collecteur, "_urls_a_visiter", urls)

    def extraire(html, url, **k):
        # Chaque page coûte son temps : c'est le seul point où l'horloge avance.
        horloge.avancer(secondes_par_page[k.get("agence")])
        return None       # aucun bien retenu : on ne mesure que le temps

    monkeypatch.setattr(collecteur, "extraire_annonce", extraire)
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    monkeypatch.setattr(sys, "argv",
                        ["collecter_navigateur.py",
                         "--minutes-par-agence", str(minutes_par_agence),
                         "--minutes-max", str(minutes_max)])
    collecteur.main()
    return visitees


def test_une_agence_lente_ne_confisque_pas_le_budget(collecte, monkeypatch):
    """Le cas mesuré en production : trente pages à vingt secondes chez la
    première agence, et les suivantes n'étaient jamais atteintes."""
    visitees = _lancer(monkeypatch, collecte,
                       agences=["Lente", "Rapide 1", "Rapide 2"],
                       secondes_par_page={"Lente": 60, "Rapide 1": 1, "Rapide 2": 1},
                       minutes_par_agence=4.0, minutes_max=12.0)
    # Sans le budget par agence, « Lente » consommerait trente pages à une
    # minute pièce et serait seule visitée — c'est exactement ce qui s'est
    # produit en production.
    assert visitees == ["Lente", "Rapide 1", "Rapide 2"], \
        "les agences suivantes doivent avoir leur tour"


def test_le_budget_global_reste_la_borne_ultime(collecte, monkeypatch):
    """Le budget par agence ne doit pas permettre de dépasser le budget total :
    c'est lui qui garantit que l'export et le commit auront lieu."""
    visitees = _lancer(monkeypatch, collecte,
                       agences=[f"Agence {n}" for n in range(20)],
                       secondes_par_page={f"Agence {n}": 20 for n in range(20)},
                       minutes_par_agence=4.0, minutes_max=12.0)
    assert len(visitees) <= 4, \
        "douze minutes de budget global, quatre par agence : trois ou quatre tours"
    assert len(visitees) >= 3


def test_la_collecte_va_jusqu_au_bout_sans_lever(collecte, monkeypatch):
    """Le workflow masque l'échec du collecteur derrière `|| true` : une
    exception ici ne se verrait qu'à l'absence de commit, des heures plus
    tard. C'est arrivé — d'où ce test, qui exige simplement que la boucle
    complète se termine."""
    visitees = _lancer(monkeypatch, collecte,
                       agences=["A", "B"],
                       secondes_par_page={"A": 1, "B": 1})
    assert visitees == ["A", "B"]


# --- La recherche des pages de biens a désormais son échéance --------------
#
# Un passage de trente-quatre minutes s'est terminé sans qu'UNE SEULE agence
# soit menée à son terme : `data/dernier_passage.json` a rapporté le code 124
# (tué par le garde-fou) et « aucun fichier modifié ». Or `_noter_visite`
# s'exécute même pour une agence écourtée — donc le collecteur n'était jamais
# ressorti de la première.
#
# Le budget par agence ne se vérifiait que dans la boucle des BIENS. La boucle
# de repli qui cherche les pages « nos biens », elle, n'avait aucune échéance :
# une agence déclarant plusieurs index pouvait y passer tout le temps de la
# collecte, trente secondes de navigation chacune.


class _PageLente:
    """Un navigateur dont chaque navigation coûte cher."""

    def __init__(self, horloge, secondes=30):
        self.horloge, self.secondes, self.visites = horloge, secondes, []

    def goto(self, url, **k):
        self.visites.append(url)
        self.horloge.avancer(self.secondes)

    def wait_for_timeout(self, ms): self.horloge.avancer(ms / 1000)
    def content(self): return "<html></html>"
    def eval_on_selector_all(self, *a, **k): return []
    def set_default_timeout(self, ms): pass
    def set_default_navigation_timeout(self, ms): pass

    @property
    def mouse(self): return self

    def wheel(self, *a, **k): pass


def test_la_recherche_des_pages_de_biens_s_arrete_au_budget(monkeypatch):
    """Vingt pages d'index à trente secondes : sans échéance, dix minutes
    partent avant même d'avoir ouvert une annonce."""
    horloge = _FausseHorloge()
    monkeypatch.setattr(collecteur.time, "monotonic", horloge)
    monkeypatch.setattr(collecteur, "_sitemap_urls", lambda *a, **k: [])
    page = _PageLente(horloge)

    cible = {"nom": "Agence lente", "site": "https://lente.fr",
             "index": [f"https://lente.fr/nos-biens/{n}" for n in range(20)]}
    fin = horloge.maintenant + 4 * 60          # quatre minutes d'échéance

    collecteur._urls_a_visiter(page, cible, "https://lente.fr", 8, fin)

    assert len(page.visites) < 20, "la recherche doit s'interrompre"
    assert horloge.maintenant <= fin + 35, \
        "elle ne doit pas dépasser son échéance de plus d'une navigation"


def test_sans_echeance_la_recherche_va_jusqu_au_bout(monkeypatch):
    """Le comportement reste inchangé quand aucun budget n'est imposé —
    c'est le cas d'une collecte lancée à la main sur un seul site."""
    horloge = _FausseHorloge()
    monkeypatch.setattr(collecteur.time, "monotonic", horloge)
    monkeypatch.setattr(collecteur, "_sitemap_urls", lambda *a, **k: [])
    page = _PageLente(horloge)
    cible = {"nom": "A", "site": "https://a.fr",
             "index": [f"https://a.fr/{n}" for n in range(5)]}

    collecteur._urls_a_visiter(page, cible, "https://a.fr", 8, 0.0)
    assert len(page.visites) == 5


def test_le_navigateur_recoit_un_plafond_de_temps(monkeypatch, tmp_path):
    """`page.content()` et `eval_on_selector_all()` ne prennent pas de délai
    en paramètre : seul un défaut posé sur la page les borne."""
    poses = {}

    class _PageTemoin(_FaussePage):
        def set_default_timeout(self, ms): poses["appel"] = ms
        def set_default_navigation_timeout(self, ms): poses["navigation"] = ms
        def eval_on_selector_all(self, *a, **k): return []

    class _Navigateur(_FauxNavigateur):
        def new_page(self): return _PageTemoin()

    class _Playwright(_FauxPlaywright):
        def launch(self, **k): return _Navigateur()

    horloge = _FausseHorloge()
    monkeypatch.setattr(collecteur.time, "monotonic", horloge)
    monkeypatch.setattr(collecteur.time, "sleep", lambda *_: None)
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _Playwright())
    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [])
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()

    assert poses.get("appel"), "aucun plafond posé sur les appels au navigateur"
    assert poses.get("navigation"), "aucun plafond posé sur les navigations"


# --- Le garde-fou qui ne demande la coopération de personne -----------------
#
# Trois correctifs successifs ont énuméré les appels à borner : budget global,
# budget par agence, délais posés sur le navigateur. Le passage suivant est
# reparti pour trente-quatre minutes sans mener UNE SEULE agence à son terme,
# code 124 et « aucun fichier modifié ».
#
# Il restait toujours un appel non couvert, et il en restera toujours un : le
# `timeout=` de `requests` s'applique à chaque LECTURE et non au total — un
# serveur qui distille ses octets une seconde à la fois ne le déclenche
# jamais. D'où `SIGALRM`, qui interrompt jusque dans un appel système
# bloquant, donc y compris dans celui qu'on aura oublié.
#
# Ces tests bloquent POUR DE VRAI, sur une horloge réelle : une fausse horloge
# ne prouverait rien ici, puisque tout l'enjeu est d'interrompre du code qui
# ne consulte aucune horloge.


def test_une_agence_qui_ne_rend_jamais_la_main_est_interrompue(monkeypatch, capsys,
                                                              tmp_path):
    """Le cas que trois correctifs successifs n'attrapaient pas."""
    import time as horloge_reelle
    visitees = []

    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [
        {"nom": "Bloquée", "site": "https://bloquee.fr"},
        {"nom": "Saine", "site": "https://saine.fr"}])

    def urls(page, cible, base, maxi, fin_prevue=0.0):
        visitees.append(cible["nom"])
        if cible["nom"] == "Bloquée":
            horloge_reelle.sleep(30)     # le réveil doit sonner bien avant
        return []

    monkeypatch.setattr(collecteur, "_urls_a_visiter", urls)
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur, "_noter_visite", lambda *a, **k: None)
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    # On garde la VRAIE fonction, avec un délai d'une seconde : c'est le
    # mécanisme qu'on veut éprouver, pas une imitation.
    vrai_borner = collecteur.borner
    monkeypatch.setattr(collecteur, "borner", lambda _: vrai_borner(1))
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])

    depart = horloge_reelle.monotonic()
    collecteur.main()
    ecoule = horloge_reelle.monotonic() - depart

    assert visitees == ["Bloquée", "Saine"], "l'agence suivante doit avoir son tour"
    assert ecoule < 20, f"le blocage a duré {ecoule:.0f} s : rien ne l'a interrompu"
    assert "arrêt forcé" in capsys.readouterr().out


def test_le_reveil_est_desarme_quand_tout_se_passe_bien(monkeypatch):
    """Un réveil oublié sonnerait au milieu de l'agence SUIVANTE, et ferait
    passer une agence saine pour bloquée."""
    import signal as sig
    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [])
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    desarmer = collecteur.borner(300)
    desarmer()
    assert sig.alarm(0) == 0, "une alarme est restée armée"


def test_borner_reste_inoffensif_sans_sigalrm(monkeypatch):
    """Sous Windows le mécanisme n'existe pas : il doit s'effacer, pas planter."""
    import signal as sig
    monkeypatch.delattr(sig, "SIGALRM", raising=False)
    collecteur.borner(5)()          # ne doit rien lever


# --- Le déroulé, consigné dans le dépôt et pas seulement au journal ---------
#
# Le journal du run n'est lisible que depuis l'onglet Actions. La surveillance
# quotidienne, elle, n'a que git — et quatre passages de suite sont restés
# inexplicables faute d'une trace committée. `data/deroule_collecte.json` dit
# ce que chaque agence a coûté et COMMENT son tour s'est terminé : rendue
# d'elle-même, budget épuisé, ou interrompue. Trois causes, trois remèdes
# opposés, et le fichier est la seule chose qui les distingue depuis git.


def test_le_deroule_dit_comment_chaque_agence_a_fini(collecte, monkeypatch, tmp_path):
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    _lancer(monkeypatch, collecte,
            agences=["Rapide", "Lente"],
            secondes_par_page={"Rapide": 1, "Lente": 60},
            minutes_par_agence=4.0, minutes_max=28.0)

    ecrit = json.loads(journal.read_text(encoding="utf-8"))
    assert [a["agence"] for a in ecrit["agences"]] == ["Rapide", "Lente"]
    fins = {a["agence"]: a["fin"] for a in ecrit["agences"]}
    assert fins["Rapide"] == "terminée", "une agence qui rend la main le dit"
    assert "temps de l'agence épuisé" in fins["Lente"]
    assert ecrit["agences"][1]["secondes"] >= 200, "le temps passé est consigné"


def test_le_deroule_nomme_l_agence_interrompue(monkeypatch, tmp_path):
    """Le cas qu'aucun autre signal ne distingue : une agence qui ne rend pas
    la main ressemble, vue de git, à une agence simplement lente."""
    import time as horloge_reelle
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [
        {"nom": "Bloquée", "site": "https://bloquee.fr"}])

    def urls(page, cible, base, maxi, fin_prevue=0.0):
        horloge_reelle.sleep(30)
        return []

    monkeypatch.setattr(collecteur, "_urls_a_visiter", urls)
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur, "_noter_visite", lambda *a, **k: None)
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    vrai_borner = collecteur.borner
    monkeypatch.setattr(collecteur, "borner", lambda _: vrai_borner(1))
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()

    ecrit = json.loads(journal.read_text(encoding="utf-8"))
    assert "INTERROMPUE" in ecrit["agences"][0]["fin"]


def test_un_journal_indisponible_ne_perd_pas_la_collecte(collecte, monkeypatch,
                                                         tmp_path):
    """Le fichier est un confort de diagnostic : il ne doit jamais coûter une
    collecte. On rend son écriture impossible en plaçant son dossier parent
    là où se trouve déjà un FICHIER — le système refusera de créer le
    dossier, comme le ferait un disque plein."""
    obstacle = tmp_path / "obstacle"
    obstacle.write_text("je ne suis pas un dossier", encoding="utf-8")
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", obstacle / "sous" / "x.json")

    visitees = _lancer(monkeypatch, collecte, agences=["A"],
                       secondes_par_page={"A": 1})
    assert visitees == ["A"], "la collecte doit aboutir malgré le journal perdu"
