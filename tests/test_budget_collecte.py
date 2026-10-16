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

from app import historique, qualite  # noqa: E402
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
    # Depuis le 3 octobre la boucle lit robots.txt sur le réseau avant chaque
    # site. Ici : un site sans fichier (404), donc tout permis — ces tests
    # mesurent le budget, pas la permission, et ne doivent rien attendre du
    # réseau (un vrai appel passerait par le mandataire, dix secondes par site).
    monkeypatch.setattr(collecteur, "_chercher_robots", lambda url: (404, None))
    # Sans cela, chaque test qui exécute main() écrit le VRAI journal de
    # déroulé — et un `git add -A` a committé « Bloquée / Saine » par-dessus
    # le déroulé d'une collecte réelle. Un test qui touche au dépôt n'est pas
    # un test, c'est un effet de bord avec un nom rassurant.
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES",
                        tmp_path / "tronquees.json")
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

    def urls(page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None):
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
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES",
                        tmp_path / "tronquees.json")
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

    def urls(page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None):
        visitees.append(cible["nom"])
        if cible["nom"] == "Bloquée":
            horloge_reelle.sleep(30)     # le réveil doit sonner bien avant
        return []

    monkeypatch.setattr(collecteur, "_urls_a_visiter", urls)
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur, "_noter_visite", lambda *a, **k: None)
    # Depuis le 3 octobre la boucle lit robots.txt sur le réseau avant chaque
    # site. Ici : un site sans fichier (404), donc tout permis — ces tests
    # mesurent le budget, pas la permission, et ne doivent rien attendre du
    # réseau (un vrai appel passerait par le mandataire, dix secondes par site).
    monkeypatch.setattr(collecteur, "_chercher_robots", lambda url: (404, None))
    monkeypatch.setattr(collecteur.db, "connexion", lambda: _FausseBase())
    # On garde la VRAIE fonction, avec un délai d'une seconde : c'est le
    # mécanisme qu'on veut éprouver, pas une imitation.
    vrai_borner = collecteur.borner
    monkeypatch.setattr(collecteur, "borner", lambda _: vrai_borner(1))
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", tmp_path / "deroule.json")
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES",
                        tmp_path / "tronquees.json")
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
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES",
                        tmp_path / "tronquees.json")
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
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES",
                        tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [
        {"nom": "Bloquée", "site": "https://bloquee.fr"}])

    def urls(page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None):
        horloge_reelle.sleep(30)
        return []

    monkeypatch.setattr(collecteur, "_urls_a_visiter", urls)
    monkeypatch.setattr(collecteur, "sync_playwright", lambda: _FauxPlaywright())
    monkeypatch.setattr(collecteur, "_noter_visite", lambda *a, **k: None)
    # Depuis le 3 octobre la boucle lit robots.txt sur le réseau avant chaque
    # site. Ici : un site sans fichier (404), donc tout permis — ces tests
    # mesurent le budget, pas la permission, et ne doivent rien attendre du
    # réseau (un vrai appel passerait par le mandataire, dix secondes par site).
    monkeypatch.setattr(collecteur, "_chercher_robots", lambda url: (404, None))
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
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES",
                        tmp_path / "tronquees.json")

    visitees = _lancer(monkeypatch, collecte, agences=["A"],
                       secondes_par_page={"A": 1})
    assert visitees == ["A"], "la collecte doit aboutir malgré le journal perdu"


def test_le_deroule_montre_la_premiere_page_illisible(collecte, monkeypatch, tmp_path):
    """Cent neuf pages « illisibles » en deux jours chez quatre agences, et le
    déroulé n'en disait que le nombre : rien pour distinguer un mur anti-robot
    d'un gabarit inconnu de l'extracteur. On garde la première — adresse,
    cause, <title> servi, taille — et seulement la première."""
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur, "_cibles",
                        lambda *a, **k: [{"nom": "Agence X", "site": "https://agence-x.fr"}])
    monkeypatch.setattr(
        collecteur, "_urls_a_visiter",
        lambda page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None:
        [f"{base}/bien-{i}" for i in range(3)])
    monkeypatch.setattr(_FaussePage, "content", lambda self: (
        "<html><head><title>\n  Agence X — accueil </title></head>"
        "<body>Vérification de votre navigateur…</body></html>"))
    # L'extracteur ne lit qu'un titre, et c'est le nom du site : illisible.
    monkeypatch.setattr(collecteur, "extraire_annonce",
                        lambda html, url, **k: {"titre": "Agence X"})
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()

    agence = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert agence["illisibles"] == 3 and agence["gardes"] == 0
    exemple = agence["illisible_exemple"]
    assert exemple["url"] == "https://agence-x.fr/bien-0", "la première, pas la dernière"
    assert exemple["cause"] == "titre = nom du site"
    assert exemple["titre"] == "Agence X — accueil", "le <title> servi, nettoyé"
    assert exemple["octets"] > 0


def test_le_deroule_compte_les_vendus_que_l_adresse_annoncait(collecte, monkeypatch, tmp_path):
    """Les biens déjà vendus sont le premier gaspillage du budget — 162 pages
    sur 468 le 4 octobre, 81 sur 295 le 5 — et on ne sait pas s'il fallait
    ouvrir la page pour l'apprendre. On compte ceux dont l'adresse le disait,
    avant de décider si une règle d'adresse en vaut la peine : une mesure, pas
    une règle."""
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur, "_cibles",
                        lambda *a, **k: [{"nom": "Agence X", "site": "https://agence-x.fr"}])
    monkeypatch.setattr(
        collecteur, "_urls_a_visiter",
        lambda page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None: [
            f"{base}/biens-vendus/maison-de-ville-12",     # la rubrique le dit
            f"{base}/vente/maison-vendue-caen-7",           # le slug le dit
            f"{base}/vente/maison-de-bourg-3",              # rien ne le disait
            f"{base}/vente/vendeuvre-sur-barse-maison-9",   # une commune, pas un verdict
        ])
    monkeypatch.setattr(collecteur, "extraire_annonce",
                        lambda html, url, **k: {"titre": "Maison de ville avec jardin", "vendu": True})
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()

    agence = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert agence["vendus"] == 4 and agence["gardes"] == 0
    assert agence["vendus_dans_l_adresse"] == 2, "deux adresses sur quatre le disaient d'avance"


# --- Une agence en erreur ne tue pas le passage ----------------------------
#
# Le 8 octobre 2026, le passage de 17 h 26 s'est arrêté à sa troisième agence
# sur « Execution context was destroyed, most likely because of a navigation » :
# la page d'index s'était rechargée pendant qu'on lisait ses liens. Deux
# agences visitées, dix biens, le collecteur sorti en erreur, et l'export
# publié par-dessus comme un passage normal. Rien dans le déroulé ne le disait.


class _PageQuiBouge(_FaussePage):
    """Un index qui se recharge pendant qu'on lit ses liens, puis se pose."""

    def __init__(self, pannes):
        self.pannes, self.appels = pannes, 0

    def eval_on_selector_all(self, *a, **k):
        self.appels += 1
        if self.appels <= self.pannes:
            raise RuntimeError("Execution context was destroyed, most likely because of a navigation")
        return ["/vente/maison-1", "/vente/maison-2"]


def test_un_index_qui_se_recharge_se_relit_une_fois():
    page = _PageQuiBouge(pannes=1)
    assert collecteur._liens_page(page, "https://agence-x.fr") == [
        "https://agence-x.fr/vente/maison-1", "https://agence-x.fr/vente/maison-2"]
    assert page.appels == 2


def test_un_index_qui_bouge_encore_rend_une_liste_vide_sans_lever():
    page = _PageQuiBouge(pannes=5)
    assert collecteur._liens_page(page, "https://agence-x.fr") == []


def test_une_agence_en_erreur_ne_tue_pas_le_passage(collecte, monkeypatch, tmp_path):
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [
        {"nom": "Fragile", "site": "https://fragile.fr"},
        {"nom": "Saine", "site": "https://saine.fr"}])
    visitees = []

    def urls(page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None):
        visitees.append(cible["nom"])
        if cible["nom"] == "Fragile":
            raise RuntimeError("Execution context was destroyed")
        return [f"{base}/vente/maison-{i}" for i in range(3)]

    monkeypatch.setattr(collecteur, "_urls_a_visiter", urls)
    monkeypatch.setattr(collecteur, "extraire_annonce", lambda html, url, **k: None)
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()                        # ne doit pas lever

    assert visitees == ["Fragile", "Saine"], "la suivante est visitée"
    ecrit = json.loads(journal.read_text(encoding="utf-8"))
    fins = {a["agence"]: a["fin"] for a in ecrit["agences"]}
    assert "ERREUR RuntimeError" in fins["Fragile"], "le déroulé nomme l'erreur"
    assert fins["Saine"] == "terminée"
    tronquees = json.loads((tmp_path / "tronquees.json").read_text(encoding="utf-8"))
    assert any("Fragile" in t for t in tronquees), \
        "l'agence en erreur est tronquée : ses biens ne sont pas comptés absents"


def test_le_deroule_dit_pourquoi_les_pages_sont_ecartees(collecte, monkeypatch, tmp_path):
    """Le 11 octobre 2026, Agence du Terroir — Perche vendômois, en plein dans
    la cible — a rendu 0 bien sur 60 pages, dont 40 « hors cible » ; Creil
    Immo 22 sur 22, Habitat Immobilier 20 sur 20. Le déroulé disait combien,
    jamais pourquoi : il fallait rouvrir les pages pour le savoir, et le poste
    n'a pas le réseau. On compte les motifs, tels que la règle les nomme."""
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur, "_cibles",
                        lambda *a, **k: [{"nom": "Agence X", "site": "https://agence-x.fr"}])
    pages = {
        "https://agence-x.fr/bien-1": {"titre": "Appartement T2 centre-ville", "surface_m2": 45, "prix": 95000},
        "https://agence-x.fr/bien-2": {"titre": "Appartement T3 avec balcon", "surface_m2": 65, "prix": 120000},
        "https://agence-x.fr/bien-3": {"titre": "Terrain à bâtir viabilisé", "surface_m2": None, "prix": 40000},
        "https://agence-x.fr/bien-4": {"titre": "Maison à louer Savonnières", "surface_m2": 120},
    }
    monkeypatch.setattr(
        collecteur, "_urls_a_visiter",
        lambda page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None: list(pages))
    monkeypatch.setattr(collecteur, "extraire_annonce", lambda html, url, **k: dict(pages[url]))
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()

    agence = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert agence["ecartes"] == 4 and agence["gardes"] == 0
    attendus = {}
    for p in pages.values():
        motif = qualite.motif_de_rejet(dict(p))
        attendus[motif] = attendus.get(motif, 0) + 1
    assert agence["motifs"] == attendus, "chaque page écartée compte sous le motif que la règle lui donne"
    assert agence["motifs"]["location"] == 1
    assert sum(n for m, n in agence["motifs"].items() if m.startswith("titre_hors_cible:appartement")) == 2


def test_le_deroule_montre_une_page_par_motif(collecte, monkeypatch, tmp_path):
    """Le 14 octobre 2026, Agence du Terroir — Perche vendômois, en plein dans
    la cible — : 60 pages ouvertes, 0 gardé, 20 vendues, 40 écartées
    « page_catalogue », 124 adresses datées au sitemap, et pas un bien au
    fichier depuis le 4 août. Le motif dit quelle règle refuse ; il ne dit pas
    si ces quarante pages sont des listes par commune, qu'une règle d'adresse
    écarterait avant de les ouvrir, ou de vraies annonces dont le gabarit cite
    les références de trois biens voisins — que la règle prend pour un
    catalogue. La première page écartée sous chaque motif, adresse et titre,
    tranche sans rouvrir le site : le poste n'a pas le réseau."""
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur, "_cibles",
                        lambda *a, **k: [{"nom": "Agence X", "site": "https://agence-x.fr"}])
    pages = {
        "https://agence-x.fr/bien-1": {"titre": "Appartement T2 centre-ville", "surface_m2": 45, "prix": 95000},
        "https://agence-x.fr/bien-2": {"titre": "Appartement T3 avec balcon", "surface_m2": 65, "prix": 120000},
        # Une vraie maison, dont la page cite trois références : un catalogue
        # pour la règle. C'est précisément ce qu'on veut pouvoir aller vérifier.
        "https://agence-x.fr/bien-3": {"titre": "Maison de bourg avec jardin", "surface_m2": 120,
                                       "prix": 180000, "texte": "Réf. 101 … Réf. 102 … Réf. 103"},
        "https://agence-x.fr/bien-4": {"titre": "Maison à louer Savonnières", "surface_m2": 120},
    }
    monkeypatch.setattr(
        collecteur, "_urls_a_visiter",
        lambda page, cible, base, maxi, fin_prevue=0.0, permission=None, diag=None: list(pages))
    monkeypatch.setattr(collecteur, "extraire_annonce", lambda html, url, **k: dict(pages[url]))
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    collecteur.main()

    agence = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert agence["ecartes"] == 4 and agence["gardes"] == 0
    assert qualite.motif_de_rejet(dict(pages["https://agence-x.fr/bien-3"])) == "page_catalogue"
    exemples = agence["ecartes_exemples"]
    assert exemples["page_catalogue"] == {"url": "https://agence-x.fr/bien-3",
                                          "titre": "Maison de bourg avec jardin"}
    assert exemples["location"] == {"url": "https://agence-x.fr/bien-4",
                                    "titre": "Maison à louer Savonnières"}
    assert exemples["titre_hors_cible:appartement"]["url"] == "https://agence-x.fr/bien-1", \
        "la PREMIÈRE page écartée sous ce motif, pas la dernière"
    assert set(exemples) == set(agence["motifs"]), "un exemple par motif compté, ni plus ni moins"


# --- Les pages écartées ne se rouvrent pas -----------------------------------

class _Reponse:
    def __init__(self, status_code, text=""):
        self.status_code, self.text = status_code, text


def _agence_au_sitemap(monkeypatch, tmp_path, pages: dict, base="https://agence-x.fr"):
    """Une agence dont le sitemap liste `pages` ; chaque page rend ce qu'on
    lui a mis. Journaux et déroulé dans tmp_path, jamais dans le dépôt."""
    journal = tmp_path / "deroule.json"
    monkeypatch.setattr(collecteur, "JOURNAL_DEROULE", journal)
    monkeypatch.setattr(historique, "JOURNAL_TRONQUEES", tmp_path / "tronquees.json")
    monkeypatch.setattr(collecteur, "_cibles", lambda *a, **k: [{"nom": "Agence X", "site": base}])
    sitemap = "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in pages) + "</urlset>"

    class FauxRequests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return _Reponse(200, sitemap) if url == f"{base}/sitemap.xml" else _Reponse(404, "")

    monkeypatch.setattr(collecteur, "requests", FauxRequests)
    monkeypatch.setattr(collecteur, "extraire_annonce", lambda html, url, **k: dict(pages[url]))
    monkeypatch.setattr(sys, "argv", ["collecter_navigateur.py"])
    return journal


def test_une_page_lue_vendue_n_est_pas_rouverte_au_passage_suivant(collecte, monkeypatch, tmp_path):
    """Mesuré aux déroulés des 14 et 15 octobre 2026 : 183 pages vendues sur
    358 ouvertes à 05 h 23, 134 sur 294 la veille au soir — la moitié du
    budget de chaque passage, et les mêmes pages à chaque visite : Toutabitat
    45 sur 45, Leforestier 45 sur 45, Pisani 8 sur 8. Ces agences gardent
    leurs ventes dans le sitemap, datées du jour de la vente, donc en tête du
    tri par fraîcheur. Trier n'y suffisait pas ; il faut se souvenir. Une page
    lue vendue est notée ; au passage suivant, on ne l'ouvre pas, et le budget
    va aux autres."""
    base = "https://agence-x.fr"
    pages = {
        f"{base}/vente/maison-vendue-belleme-1": {"titre": "Maison de bourg à Bellême", "vendu": True,
                                                 "surface_m2": 120, "prix": 180000},
        f"{base}/vente/maison-sous-compromis-2": {"titre": "Longère sous compromis", "surface_m2": 100,
                                                  "prix": 150000, "texte": "Ce bien est sous compromis."},
        # Ni prix ni surface : un refus de MESURE, qu'on relit à chaque visite.
        f"{base}/vente/maison-de-ville-centre-3": {"titre": "Maison de ville en centre-ville",
                                                   "type_bien": "maison"},
    }
    journal = _agence_au_sitemap(monkeypatch, tmp_path, pages)

    collecteur.main()
    premier = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert (premier["pages"], premier["vendus"], premier["ecartes"]) == (3, 2, 1)
    assert "deja_ecartees" not in premier
    memoire = json.loads((tmp_path / "pages_ecartees.json").read_text(encoding="utf-8"))
    assert memoire == {f"{base}/vente/maison-vendue-belleme-1": {"jour": collecteur.date.today().isoformat(),
                                                                "motif": "vendu"},
                       f"{base}/vente/maison-sous-compromis-2": {"jour": collecteur.date.today().isoformat(),
                                                                 "motif": "vendu"}}, \
        "les deux pages vendues sont notées avec leur motif, pas la page sans prix"

    collecteur.main()
    second = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert (second["pages"], second["vendus"]) == (1, 0), "les pages vendues ne sont pas rouvertes"
    assert second["deja_ecartees"] == 2
    assert second["sitemap"] == "ok 3", "le sitemap compte toujours ses trois pages de biens"


def test_une_page_ecartee_pour_ce_qu_elle_est_n_est_pas_rouverte_non_plus(collecte, monkeypatch, tmp_path):
    """Mesuré le 16 octobre 2026, les ventes déjà en mémoire : 93 pages sur 284
    refusées APRÈS ouverture pour ce qu'elles sont — Human Immobilier 33
    appartements sur 45, Homeloop 35 fois la même page de catalogue « 153
    biens à vendre ». Un appartement ne devient pas une maison : ce refus-là
    est aussi stable qu'une vente, et se retient de la même façon. Un refus de
    mesure (prix, surface absente) ne se retient pas. Et quand une règle
    change, on purge son motif : le correctif n'attend pas le sursis."""
    base = "https://agence-x.fr"
    pages = {
        f"{base}/vente/maison-de-ville-centre-1": {"titre": "Appartement T2 en centre-ville",
                                                   "surface_m2": 45, "prix": 95000},
        f"{base}/vente/maison-oullins-83567": {"titre": "153 biens à vendre", "surface_m2": 100,
                                               "prix": 200000},
        f"{base}/vente/maison-de-bourg-belleme-5": {"titre": "Maison de bourg à Bellême",
                                                    "type_bien": "maison"},
    }
    journal = _agence_au_sitemap(monkeypatch, tmp_path, pages)
    assert [historique.motif_stable(qualite.motif_de_rejet(dict(p))) for p in pages.values()] == \
        [True, True, False], "appartement et catalogue sont stables, l'absence de prix ne l'est pas"

    collecteur.main()
    premier = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert (premier["pages"], premier["ecartes"]) == (3, 3)
    memoire = historique.pages_ecartees()
    assert {u: e["motif"] for u, e in memoire.items()} == {
        f"{base}/vente/maison-de-ville-centre-1": "titre_hors_cible:appartement",
        f"{base}/vente/maison-oullins-83567": "titre_hors_cible:153 biens"}

    collecteur.main()
    second = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert (second["pages"], second["deja_ecartees"]) == (1, 2), "seule la page sans prix est relue"

    # La règle des appartements change : on purge son motif, la page se relit.
    memoire = historique.pages_ecartees()
    assert historique.oublier_motif(memoire, "titre_hors_cible:appartement") == 1
    historique.noter_pages_ecartees(memoire, collecteur.date.today().isoformat())
    collecteur.main()
    troisieme = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert (troisieme["pages"], troisieme["deja_ecartees"]) == (2, 1)


def test_le_sursis_des_pages_ecartees_expire_et_le_journal_se_taille(collecte, monkeypatch, tmp_path):
    """Une vente ne se défait pas, mais un compromis peut tomber et la règle
    peut se tromper : passé le sursis, la page est relue, et un nouveau
    constat la remet au journal. Ce qui a dépassé le sursis sans être relu en
    sort, sinon le journal grossirait à jamais. La forme d'avant le 16 octobre
    — la date seule — se lit encore, comme une vente."""
    from datetime import date, timedelta
    base = "https://agence-x.fr"
    pages = {
        f"{base}/vente/maison-vendue-1": {"titre": "Maison vendue à Mortagne", "vendu": True,
                                         "surface_m2": 120, "prix": 180000},
        f"{base}/vente/maison-vendue-2": {"titre": "Maison vendue à Bellême", "vendu": True,
                                         "surface_m2": 110, "prix": 170000},
    }
    journal = _agence_au_sitemap(monkeypatch, tmp_path, pages)
    perime = (date.today() - timedelta(days=historique.SURSIS_ECARTEES + 1)).isoformat()
    recent = (date.today() - timedelta(days=2)).isoformat()
    (tmp_path / "pages_ecartees.json").write_text(json.dumps({
        f"{base}/vente/maison-vendue-1": {"jour": perime, "motif": "vendu"},   # au sitemap : à relire
        f"{base}/vente/maison-vendue-2": recent,                              # forme d'avant : pas rouverte
        f"{base}/vente/maison-disparue-9": {"jour": perime, "motif": "vendu"},  # plus au sitemap : sort
    }), encoding="utf-8")

    collecteur.main()
    agence = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert (agence["pages"], agence["vendus"], agence["deja_ecartees"]) == (1, 1, 1)
    memoire = json.loads((tmp_path / "pages_ecartees.json").read_text(encoding="utf-8"))
    assert memoire == {f"{base}/vente/maison-vendue-1": {"jour": date.today().isoformat(), "motif": "vendu"},
                       f"{base}/vente/maison-vendue-2": {"jour": recent, "motif": "vendu"}}, \
        "relue et renotée du jour ; l'autre attend son sursis, récrite à la forme nouvelle ; la disparue est sortie"


def test_tout_vendu_connu_ne_renvoie_pas_vers_l_index(collecte, monkeypatch, tmp_path):
    """Pisani : huit adresses au sitemap, huit vendues. Le passage suivant ne
    doit pas se replier sur la page d'index — elle ne listerait que les mêmes
    adresses, pour le prix d'une navigation de plus — ni compter l'agence
    comme privée de sitemap."""
    from datetime import date
    base = "https://agence-x.fr"
    pages = {f"{base}/vente/maison-vendue-{i}": {"titre": f"Maison vendue n° {i}", "vendu": True,
                                                 "surface_m2": 100, "prix": 150000} for i in range(3)}
    journal = _agence_au_sitemap(monkeypatch, tmp_path, pages)
    (tmp_path / "pages_ecartees.json").write_text(
        json.dumps({u: {"jour": date.today().isoformat(), "motif": "vendu"} for u in pages}), encoding="utf-8")
    index_ouvert = []
    monkeypatch.setattr(collecteur, "_liens_page", lambda page, base: index_ouvert.append(base) or [])

    collecteur.main()
    agence = json.loads(journal.read_text(encoding="utf-8"))["agences"][0]
    assert (agence["pages"], agence["deja_ecartees"], agence["sitemap"]) == (0, 3, "ok 3")
    assert index_ouvert == [], "le sitemap lu fait autorité : pas de repli sur l'index"
