"""Mémoire des annonces d'une collecte à l'autre.

Sans mémoire, chaque collecte repart de zéro : impossible de dire ce qui est
nouveau, de repérer une baisse de prix, ni de savoir qu'une annonce a disparu
du site de l'agence. Or c'est précisément ce qu'on attend d'un outil de veille :
être prévenu, plutôt que de tout relire chaque semaine.

L'historique ne peut pas vivre dans la base : elle est recréée à chaque
exécution (et remise à zéro à chaque démarrage sur l'hébergement). Il vit donc
dans le fichier exporté `data/annonces_reel.json`, qui est versionné — c'est
lui qui traverse le temps.

Trois informations sont conservées pour chaque bien :

    vue_le          première fois qu'on a vu cette annonce
    revue_le        dernière collecte où elle était encore en ligne
    prix_precedent  prix d'avant la dernière baisse (et `prix_baisse_le`)

Et une règle de sortie : une annonce que l'agence a retirée disparaît à son
tour — mais seulement si son SITE a bien été visité, sinon une collecte
écourtée ferait disparaître des biens parfaitement valides.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

# Une annonce absente de la dernière collecte de SON agence est considérée
# retirée. On tolère une absence (page en erreur, site momentanément lent) :
# c'est la deuxième qui l'élimine.
ABSENCES_TOLEREES = 1


def cle_agence(url: str) -> str:
    """Identifie une agence par son DOMAINE, jamais par son nom.

    « Century 21 » désigne douze sites distincts — Chalon, Compiègne, Amboise,
    Caen… La rotation de la collecte avait déjà appris cette leçon et s'indexe
    sur le domaine depuis. La règle de sortie ci-dessous, elle, comparait
    encore des noms : passer chez cinq Century 21 marquait les douze comme
    visitées, et les biens des sept autres étaient comptés absents « chez leur
    agence ». Cinquante et un ont ainsi été retirés du catalogue le 10 août
    alors que leurs pages étaient parfaitement en ligne.

    Une seule définition pour les deux usages, importée par le collecteur :
    deux copies de cette règle avaient déjà divergé une fois.
    """
    hote = urlparse(url or "").netloc.lower()
    return hote[4:] if hote.startswith("www.") else hote


JOURNAL_TRONQUEES = Path(__file__).resolve().parent.parent / "data" / "visites_tronquees.json"


def _ecrire_journal(chemin: Path, cibles: set) -> None:
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps(sorted([list(c) for c in cibles]), ensure_ascii=False,
                       indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass       # un journal indisponible ne doit pas arrêter la collecte


def _lire_journal(chemin: Path) -> set:
    try:
        return {tuple(c) for c in json.loads(chemin.read_text(encoding="utf-8"))}
    except (OSError, ValueError, TypeError):
        return set()


def noter_visite_tronquee(cibles: set) -> None:
    """Écrit les cibles dont la visite s'est arrêtée AVANT la fin de leur liste.

    Réécrit entièrement le fichier à chaque passage : il ne décrit jamais que
    le passage en cours. Un journal qui traînerait d'une collecte à l'autre
    ferait abstenir la règle de sortie sur des cibles qu'on vient pourtant de
    parcourir en entier — l'erreur inverse, et tout aussi silencieuse.
    """
    _ecrire_journal(JOURNAL_TRONQUEES, cibles)


def visites_tronquees() -> set:
    """Les cibles à ne PAS considérer comme parcourues, faute de les avoir vues
    en entier. Absent ou illisible, on ne retranche rien : l'ancien
    comportement, jamais pire."""
    return _lire_journal(JOURNAL_TRONQUEES)


def _journal_fermees() -> Path:
    """Le journal des sites qui nous ont fermé leur porte, à côté de celui des
    visites tronquées — y compris quand un test déplace celui-ci : un test qui
    écrit dans le dépôt n'est pas un test."""
    return JOURNAL_TRONQUEES.with_name("visites_fermees.json")


def noter_visites_fermees(cibles: set) -> None:
    """Écrit les cibles dont le site a fermé sa racine au robot (robots.txt)
    ce passage-ci. Réécrit entièrement, comme le journal des visites
    tronquées, et pour la même raison : il ne décrit que le passage en cours."""
    _ecrire_journal(_journal_fermees(), cibles)


def visites_fermees() -> set:
    """Les cibles fermées au robot ce passage-ci. Absent ou illisible : aucune
    — on ne retire rien de plus que l'ancien comportement."""
    return _lire_journal(_journal_fermees())


# --- Pages vendues : la mémoire qui rend son budget à la collecte ------------
#
# Mesuré aux déroulés des 14 et 15 octobre 2026 : 183 pages vendues sur 358
# ouvertes à 05 h 23, 134 sur 294 la veille au soir, 93 sur 296, 140 sur 310 —
# la moitié du budget de chaque passage, et les mêmes pages à chaque visite :
# Toutabitat 45 sur 45, Leforestier 45 sur 45, Pisani 8 sur 8, Notarianni 36
# sur 40. Ces agences gardent leurs ventes passées dans le sitemap, souvent
# datées du jour de la vente, donc en tête de l'ordre « les plus récentes
# d'abord ». Trier n'y suffisait pas ; il faut se souvenir.
#
# Une page lue vendue est notée avec le jour du constat, et n'est plus ouverte
# avant SURSIS_VENDUES jours. Une vente ne se défait pas, mais un compromis
# peut tomber et la règle peut se tromper : passé le sursis, on relit, et un
# nouveau constat la remet au journal pour autant. Le journal se taille
# lui-même à l'écriture.
#
# Ne pas rouvrir une page vendue ne change rien au catalogue : elle ne donnait
# aucun bien, et le bien qu'elle portait, s'il est encore au fichier, reste
# compté absent exactement comme avant — la collecte ne le revoit pas. Seules
# les pages ouvertes diminuent.
SURSIS_VENDUES = 30


def _journal_vendues() -> Path:
    """À côté des visites tronquées, et déplacé avec elles par les tests : un
    test qui écrit dans le dépôt n'est pas un test."""
    return JOURNAL_TRONQUEES.with_name("pages_vendues.json")


def pages_vendues() -> dict:
    """{adresse: jour du dernier constat « vendu »}. Absent ou illisible :
    rien à éviter — l'ancien comportement, jamais pire."""
    try:
        journal = json.loads(_journal_vendues().read_text(encoding="utf-8"))
        return {u: j for u, j in journal.items()
                if isinstance(u, str) and isinstance(j, str)}
    except (OSError, ValueError, AttributeError):
        return {}


def _encore_sous_sursis(journal: dict, aujourd_hui: str) -> dict:
    limite = (date.fromisoformat(aujourd_hui) - timedelta(days=SURSIS_VENDUES)).isoformat()
    return {u: j for u, j in journal.items() if j >= limite}


def vendues_a_eviter(journal: dict, aujourd_hui: str) -> set:
    """Les adresses lues vendues il y a moins de SURSIS_VENDUES jours."""
    return set(_encore_sous_sursis(journal, aujourd_hui))


def noter_pages_vendues(journal: dict, aujourd_hui: str) -> None:
    """Écrit le journal, taillé : ce qui a dépassé le sursis en sort — la page
    sera relue, et un nouveau constat la remettra. Un journal indisponible
    n'arrête pas la collecte."""
    try:
        chemin = _journal_vendues()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(_encore_sous_sursis(journal, aujourd_hui),
                                     ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")
    except OSError:
        pass


def cibles_qui_font_autorite(biens: list[dict]) -> set:
    """Les cibles sur lesquelles la règle de sortie peut conclure.

    Celles qui ont rendu des biens ce passage-ci ; plus celles qui ont fermé
    leur porte au robot — on ne publie pas ce qu'on n'a plus le droit de
    lire, et leurs biens sortent comme des biens disparus, c'est ce que la
    page /robot promet depuis le 3 octobre 2026 ; moins celles qu'on n'a pas
    vues en entier — compter l'absence d'un bien qu'on n'a pas cherché a déjà
    coûté cinquante-six annonces Century 21 et deux cent six IAD.

    Jusqu'au 11 octobre 2026, seule la première famille existait : un site
    fermé ne rend aucun bien, donc n'était jamais « visité », et ses biens
    restaient conservés indéfiniment. Trois sites fermés depuis une semaine
    servaient encore vingt biens.
    """
    return (({identite(b) for b in biens} | visites_fermees())
            - {("", "")} - visites_tronquees())


def identite(bien: dict) -> tuple:
    """L'unité RÉELLEMENT parcourue d'où vient un bien : le nom ET le domaine.

    Ni l'un ni l'autre ne suffit, et chacun a fait disparaître des annonces en
    ligne — le même jour, dans les deux sens :

    - le NOM seul est trop large quand une enseigne tient plusieurs sites.
      « Century 21 » en désigne douze ; en visiter cinq marquait les douze, et
      cinquante-six annonces des sept autres ont été retirées ;
    - le DOMAINE seul est trop large quand un site porte plusieurs cibles.
      Les mandataires IAD vivent tous sous `iadfrance.fr` mais sont parcourus
      département par département (`iad:37`, `iad:71`… — voir le journal
      data/mandataires_visites.json), et chacun devient une agence distincte,
      « IAD France (37) ». Basculer sur le domaine pour régler le cas
      Century 21 a fait disparaître deux cent six annonces IAD au passage
      suivant.

    La paire recouvre exactement ce que la collecte visite : un site pour une
    agence indépendante, un couple réseau-département pour un mandataire.
    """
    return (bien.get("agence") or "", cle_agence(bien.get("agence_url")))


def _index(annonces: list[dict]) -> dict:
    return {a["id"]: a for a in annonces or [] if a.get("id")}


def fusionner(precedentes: list[dict], nouvelles: list[dict],
              sites_visites: set | None = None, aujourd_hui: str = "") -> list[dict]:
    """Reporte l'historique des annonces précédentes sur la collecte du jour.

    `sites_visites` : les SITES réellement parcourus cette fois — voir
    `cle_agence`, un nom d'agence peut en couvrir douze. Les biens des autres
    sites sont conservés tels quels : ne pas les avoir revus ne prouve rien,
    la collecte s'est simplement arrêtée avant eux.
    """
    avant = _index(precedentes)
    gardees: list[dict] = []

    for bien in nouvelles:
        ancien = avant.get(bien.get("id"))
        enrichi = dict(bien)
        enrichi["revue_le"] = aujourd_hui
        enrichi["absences"] = 0
        if ancien is None:
            enrichi["vue_le"] = aujourd_hui          # annonce inédite
        else:
            enrichi["vue_le"] = ancien.get("vue_le") or aujourd_hui
            # Baisse de prix : le signal d'achat le plus parlant, et celui
            # qu'aucun portail n'affiche clairement.
            ancien_prix, nouveau_prix = ancien.get("prix"), bien.get("prix")
            if ancien_prix and nouveau_prix and nouveau_prix < ancien_prix:
                enrichi["prix_precedent"] = ancien_prix
                enrichi["prix_baisse_le"] = aujourd_hui
            elif ancien.get("prix_precedent") and nouveau_prix == ancien.get("prix"):
                enrichi["prix_precedent"] = ancien["prix_precedent"]
                enrichi["prix_baisse_le"] = ancien.get("prix_baisse_le")
            # Les risques officiels sont un acquis : Géorisques a répondu une
            # fois, le constat vaut encore. La fusion repartait de la ligne du
            # jour et les perdait dès que l'API ne répondait plus — mesuré du
            # 1er au 3 octobre 2026 : huit biens re-collectés sur huit enrichis
            # ont perdu leurs risques, et le compte d'enrichis baissait à chaque
            # passage sans qu'aucun bien ne soit sorti pour cette raison. Une
            # réponse fraîche de l'API, elle, l'emporte toujours.
            anciens_risques = ancien.get("risques") or {}
            nouveaux_risques = bien.get("risques") or {}
            if (anciens_risques.get("source") == "georisques"
                    and nouveaux_risques.get("source") != "georisques"):
                enrichi["risques"] = {**nouveaux_risques, **anciens_risques}
        gardees.append(enrichi)

    vus = {b.get("id") for b in nouvelles}
    for identifiant, ancien in avant.items():
        if identifiant in vus:
            continue
        # Site non visité cette fois : on n'a rien appris, on conserve.
        if sites_visites is not None and identite(ancien) not in sites_visites:
            gardees.append(ancien)
            continue
        absences = int(ancien.get("absences") or 0) + 1
        if absences > ABSENCES_TOLEREES:
            continue                                  # retirée par l'agence
        garde = dict(ancien)
        garde["absences"] = absences
        gardees.append(garde)
    return gardees


def est_nouveau(bien: dict, aujourd_hui: str, jours: int = 10) -> bool:
    """Vrai si l'annonce est apparue récemment (comparaison de dates ISO)."""
    vue = bien.get("vue_le")
    if not vue or not aujourd_hui:
        return False
    from datetime import date
    try:
        d1, d2 = date.fromisoformat(vue), date.fromisoformat(aujourd_hui)
    except ValueError:
        return False
    return 0 <= (d2 - d1).days <= jours
