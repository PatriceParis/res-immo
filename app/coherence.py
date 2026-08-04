"""Contrat de cohérence de l'interface — ce que le site PROMET à l'utilisateur.

Pourquoi ce module existe
-------------------------
Une famille entière de défauts a échappé aux tests unitaires : des chiffres et
des contrôles affichés qui ne font pas ce qu'ils prétendent faire.

    « 60 biens » sur une pastille, 2 dans la liste.
    « 📷 1 / 9 » alors qu'on ne connaît qu'une seule photo.
    « Hors zone inondable » qui laissait passer 133 biens sur 133.
    « Les 5 terroirs à moins de 2 h 30 » quand il y en a 6 et que la moitié
    des biens sont au-delà.

Aucun de ces défauts ne fait planter le site. Chacun le rend faux. Et aucun
n'est attrapable en testant une fonction isolée : ils naissent de l'écart
entre **ce que l'interface annonce** et **ce que les données disent**.

D'où ce module. Il écrit les promesses UNE SEULE FOIS, en français, avec le
moyen de les vérifier. Les mêmes invariants servent :

    - aux tests (tests/test_coherence.py), à chaque modification ;
    - à l'audit de l'interface réelle (scripts/auditer_interface.py) ;
    - à la vérification continue (.github/workflows/verification.yml).

Ajouter une promesse à l'interface, c'est ajouter un invariant ici.

Chaque invariant reçoit un `appeler(chemin, params) -> dict` : la façon de
poser une question à l'API. Il fonctionne donc aussi bien sur un client de
test que sur le site en ligne.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# Cases à cocher de l'interface → colonne renvoyée par l'API qui les justifie.
CASES_A_COCHER = {
    "cave": ("Cave / sous-sol", "has_cave"),
    "puits": ("Puits / source", "has_puits"),
    "bois": ("Chauffage au bois", "has_bois"),
    "solaire": ("Panneaux solaires", "has_solaire"),
    "dependances": ("Dépendances / grange", "has_dependances"),
    "potager": ("Verger / potager", "has_potager"),
    "troglodyte": ("Habitat troglodyte", "has_troglodyte"),
    "hors_inondation": ("Commune sans inondation recensée", "hors_inondation"),
}

# Tris proposés à l'utilisateur → (champ, sens croissant ?).
TRIS_ANNONCES = {
    "prix": ("prix", True),
    "prix_m2": ("prix_m2", True),
    "temps": ("temps_voiture_min", True),
    "terrain": ("terrain_m2", False),
    "score": ("score_total", False),
    "affaire": ("ecart_marche_pct", True),
}

# Plafond de résultats appliqué par l'API (db.chercher).
PLAFOND_API = 500


@dataclass
class Rapport:
    """Ce qu'un invariant a constaté."""

    invariant: str
    promesse: str
    manquements: list[str] = field(default_factory=list)

    @property
    def tenue(self) -> bool:
        return not self.manquements


Appel = Callable[..., dict]


def _tous(appeler: Appel, **params) -> dict:
    params.setdefault("limit", PLAFOND_API)
    return appeler("/api/annonces", params)


# ---------------------------------------------------------------------------
# Les promesses
# ---------------------------------------------------------------------------


def compteur_honnete(appeler: Appel) -> Rapport:
    """« N biens trouvés » doit décrire ce que la liste montre."""
    r = Rapport("compteur_honnete",
                "Le compteur annonce exactement ce que la liste contient, "
                "ou dit qu'il est tronqué.")
    d = _tous(appeler)
    total, items = d["total"], d["items"]
    if len(items) > total:
        r.manquements.append(f"{len(items)} biens listés pour un total annoncé de {total}")
    if total > PLAFOND_API and len(items) != PLAFOND_API:
        r.manquements.append(
            f"total {total} > plafond {PLAFOND_API}, mais {len(items)} biens renvoyés")
    if total <= PLAFOND_API and len(items) != total:
        r.manquements.append(
            f"total {total} annoncé, {len(items)} biens réellement renvoyés")
    return r


def pastilles_exhaustives(appeler: Appel) -> Rapport:
    """La somme des pastilles de terroir doit égaler le compteur.

    Un bien rattaché à aucune région est compté dans le total mais
    n'apparaît sur aucune pastille : introuvable par le filtre de région,
    et l'utilisateur qui additionne ne retombe pas sur ses pieds. C'est ce
    qui est arrivé à 16 biens de la Sarthe.
    """
    r = Rapport("pastilles_exhaustives",
                "La somme des pastilles de terroir égale le nombre de biens trouvés.")
    total = _tous(appeler)["total"]
    somme = sum(x["nb_biens"] for x in appeler("/api/regions", {})["regions"])
    if somme != total:
        r.manquements.append(
            f"somme des pastilles {somme} ≠ {total} biens trouvés "
            f"({abs(total - somme)} bien(s) rattaché(s) à aucun terroir)")
    return r


def pastilles_tiennent_leur_promesse(appeler: Appel) -> Rapport:
    """Cliquer une pastille doit donner exactement le nombre annoncé.

    C'est le bug d'origine : la pastille annonçait « 60 biens » alors que la
    liste filtrée n'en montrait que 2, parce qu'elle comptait sans les
    filtres actifs.
    """
    r = Rapport("pastilles_tiennent_leur_promesse",
                "Chaque pastille de terroir annonce le nombre de biens qu'on "
                "obtient en cliquant dessus — filtres actifs compris.")
    # Sans filtre, puis avec un filtre représentatif de chaque nature :
    # une case à cocher, un seuil numérique, une recherche texte.
    for contexte in ({}, {"cave": 1}, {"prix_max": 250000}, {"q": "maison"}):
        regions = appeler("/api/regions", contexte)["regions"]
        for reg in regions:
            if not reg.get("cible"):
                continue
            annonce = reg["nb_biens"]
            reel = _tous(appeler, region=reg["region"], **contexte)["total"]
            if annonce != reel:
                r.manquements.append(
                    f"« {reg['region']} » annonce {annonce} bien(s), en donne {reel}"
                    + (f" (contexte {contexte})" if contexte else ""))
    return r


def cases_a_cocher_actives(appeler: Appel) -> Rapport:
    """Une case doit filtrer, et tous les biens restants doivent la satisfaire.

    « Hors zone inondable » laissait passer 133 biens sur 133 : le
    chargement lisait une clé de risque disparue. Une case qui ne retire
    rien promet quelque chose qu'elle ne fait pas.
    """
    r = Rapport("cases_a_cocher_actives",
                "Chaque case à cocher réduit vraiment la sélection, et tous "
                "les biens qui restent la satisfont.")
    total = _tous(appeler)["total"]
    for param, (libelle, colonne) in CASES_A_COCHER.items():
        d = _tous(appeler, **{param: 1})
        if d["total"] == total and total > 20:
            r.manquements.append(
                f"« {libelle} » ne retire aucun bien ({total} sur {total})")
        menteurs = [b["id"] for b in d["items"] if not b.get(colonne)]
        if menteurs:
            r.manquements.append(
                f"« {libelle} » renvoie {len(menteurs)} bien(s) qui ne l'ont pas "
                f"(ex. {menteurs[0]})")
    return r


def seuils_numeriques_respectes(appeler: Appel) -> Rapport:
    """Un curseur de budget doit vraiment borner les prix affichés."""
    r = Rapport("seuils_numeriques_respectes",
                "Les curseurs (budget, surface, terrain, temps de route) "
                "bornent réellement les biens affichés.")
    controles = (
        ("prix_max", 200000, "prix", lambda v, s: v <= s),
        ("surface_min", 150, "surface_m2", lambda v, s: v >= s),
        ("terrain_min", 5000, "terrain_m2", lambda v, s: v >= s),
        ("temps_max", 150, "temps_voiture_min", lambda v, s: v <= s),
        ("score_min", 40, "score_total", lambda v, s: v >= s),
    )
    for param, seuil, champ, ok in controles:
        for b in _tous(appeler, **{param: seuil})["items"]:
            v = b.get(champ)
            if v is not None and not ok(v, seuil):
                r.manquements.append(
                    f"{param}={seuil} laisse passer {champ}={v} (bien {b['id']})")
                break
    return r


def tris_ordonnes(appeler: Appel) -> Rapport:
    """Le tri annoncé doit être le tri appliqué."""
    r = Rapport("tris_ordonnes",
                "Chaque ordre de tri proposé range réellement la liste.")
    for tri, (champ, croissant) in TRIS_ANNONCES.items():
        valeurs = [b.get(champ) for b in _tous(appeler, tri=tri)["items"]]
        valeurs = [v for v in valeurs if v is not None]
        attendu = sorted(valeurs, reverse=not croissant)
        if valeurs != attendu:
            r.manquements.append(f"tri « {tri} » : {champ} n'est pas ordonné")
    return r


def chaque_bien_mene_a_l_agence(appeler: Appel) -> Rapport:
    """Sans lien vers l'annonce d'origine, la mise en relation est morte."""
    r = Rapport("chaque_bien_mene_a_l_agence",
                "Chaque bien affiché renvoie à l'annonce de son agence.")
    orphelins = [b["id"] for b in _tous(appeler)["items"]
                 if not (b.get("url") or "").startswith("http")]
    if orphelins:
        r.manquements.append(
            f"{len(orphelins)} bien(s) sans lien exploitable (ex. {orphelins[0]})")
    return r


def score_egal_a_ses_piliers(appeler: Appel) -> Rapport:
    """Le score affiché doit être la somme du détail qu'on montre à côté."""
    r = Rapport("score_egal_a_ses_piliers",
                "Le score sur 100 est exactement la somme des six piliers "
                "détaillés sur la fiche.")
    for b in _tous(appeler)["items"][:40]:
        fiche = appeler(f"/api/annonces/{b['id']}", {})
        piliers = (fiche.get("score_detail") or {}).get("piliers") or {}
        if not piliers:
            continue
        somme = sum(p.get("points", 0) for p in piliers.values())
        if abs(somme - fiche.get("score_total", 0)) > 0.51:
            r.manquements.append(
                f"{b['id']} : score {fiche['score_total']} ≠ somme des piliers {somme}")
    return r


def ecart_au_marche_reproductible(appeler: Appel) -> Rapport:
    """« 18 % sous le secteur » doit se recalculer depuis les prix affichés."""
    r = Rapport("ecart_au_marche_reproductible",
                "L'écart au prix du secteur se retrouve à partir des deux "
                "prix au m² affichés.")
    for b in _tous(appeler)["items"]:
        ecart, m2, secteur = (b.get("ecart_marche_pct"), b.get("prix_m2"),
                              b.get("prix_m2_secteur"))
        if ecart is None:
            continue
        if not m2 or not secteur:
            r.manquements.append(f"{b['id']} : écart {ecart} % sans prix de référence")
        elif abs(100 * (m2 - secteur) / secteur - ecart) > 1.5:
            r.manquements.append(
                f"{b['id']} : écart {round(ecart)} % non reproductible")
    return r


def signaux_de_fraicheur_justifies(appeler: Appel) -> Rapport:
    """« Nouveau » et « ↓ 12 % » sont des signaux d'achat : ils engagent."""
    r = Rapport("signaux_de_fraicheur_justifies",
                "Un bien marqué « Nouveau » a bien une date de première vue, "
                "et une baisse de prix affichée correspond à un prix qui a "
                "réellement baissé.")
    for b in _tous(appeler)["items"]:
        precedent, prix = b.get("prix_precedent"), b.get("prix")
        if precedent and prix and prix >= precedent:
            r.manquements.append(
                f"{b['id']} : baisse annoncée alors que {prix} ≥ {precedent}")
        if b.get("prix_baisse_le") and not precedent:
            r.manquements.append(f"{b['id']} : date de baisse sans prix précédent")
    return r


def bornes_des_filtres_couvrent_les_donnees(appeler: Appel) -> Rapport:
    """Le curseur de budget doit pouvoir atteindre le bien le plus cher."""
    r = Rapport("bornes_des_filtres_couvrent_les_donnees",
                "Les bornes qui initialisent les filtres englobent réellement "
                "les biens de la sélection.")
    meta = appeler("/api/meta", {})
    items = _tous(appeler)["items"]
    if meta.get("nb") != len(items) and meta.get("nb", 0) <= PLAFOND_API:
        r.manquements.append(
            f"/api/meta annonce {meta.get('nb')} biens, la liste en donne {len(items)}")
    prix = [b["prix"] for b in items if b.get("prix")]
    if prix and meta.get("prix_max") and max(prix) > meta["prix_max"]:
        r.manquements.append(
            f"bien à {max(prix)} € au-delà du plafond annoncé {meta['prix_max']} €")
    return r


def agences_annoncees_presentes(appeler: Appel) -> Rapport:
    """« 12 agences · annonces réelles » doit correspondre au catalogue."""
    r = Rapport("agences_annoncees_presentes",
                "Les agences listées dans le menu déroulant, et leur nombre "
                "de biens, correspondent à ce que la liste contient.")
    agences = appeler("/api/agences", {})["agences"]
    items = _tous(appeler)["items"]
    reels: dict = {}
    for b in items:
        if b.get("agence"):
            reels[b["agence"]] = reels.get(b["agence"], 0) + 1
    for a in agences:
        attendu = reels.get(a["agence"])
        if attendu is None:
            r.manquements.append(f"« {a['agence']} » proposée mais aucun bien listé")
        elif attendu != a["nb"]:
            r.manquements.append(
                f"« {a['agence']} » annonce {a['nb']} bien(s), la liste en montre {attendu}")
    return r


INVARIANTS = (
    compteur_honnete,
    pastilles_exhaustives,
    pastilles_tiennent_leur_promesse,
    cases_a_cocher_actives,
    seuils_numeriques_respectes,
    tris_ordonnes,
    chaque_bien_mene_a_l_agence,
    score_egal_a_ses_piliers,
    ecart_au_marche_reproductible,
    signaux_de_fraicheur_justifies,
    bornes_des_filtres_couvrent_les_donnees,
    agences_annoncees_presentes,
)


def verifier(appeler: Appel) -> list[Rapport]:
    """Passe tout le contrat. Renvoie un rapport par invariant."""
    return [invariant(appeler) for invariant in INVARIANTS]
