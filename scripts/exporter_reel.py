"""Exporte les annonces RÉELLES (hors démo) de la base vers data/annonces_reel.json.

L'application charge ce fichier au démarrage (y compris sur Vercel), en plus du
jeu de démonstration. C'est l'étape finale de la collecte automatisée
(voir .github/workflows/collecte.yml) : collecter → exporter → committer.

Usage :  python scripts/exporter_reel.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from datetime import date  # noqa: E402

from app import (caviardage, chargement, db, etat_du_bien, exclusions,  # noqa: E402
                 historique, liens, qualite, scoring)

# Champs « bruts » réinjectés dans l'app (elle recalcule score et distance).
# `risques` vient de Géorisques : on le conserve, l'app ne saurait pas le refaire
# sans réseau. Le train, lui, est recalculé au chargement (table locale des gares).
CHAMPS = [
    "id", "source", "url", "titre", "description", "type_bien", "prix",
    "surface_m2", "terrain_m2", "pieces", "commune", "code_postal",
    "departement", "region", "agence", "agence_url", "photo",
    # Ce qu'on a LU dans la page, et non la page. Jusqu'au 1er octobre le
    # fichier portait `texte` — la page entière, 3 000 caractères par bien —
    # pour que le chargement y relise cave, puits et poêle. Vingt-six méga-
    # octets dans un dépôt public, où quatre mille deux cents annonces
    # portaient le numéro de mobile d'un mandataire et quatre mille sept
    # cents un courriel nominatif : des données personnelles republiées sans
    # finalité, car personne ne cherche « cave » dans un numéro de téléphone.
    # Le constat voyage désormais seul ; la page reste chez l'agence.
    "features", "etat_declare", "vendu", "plusieurs_biens",
    "lat", "lon", "altitude", "densite_hab_km2", "dpe", "risques",
    # Les autres images de la page, en réserve : si la première se révèle
    # être du mobilier de site, la suivante prend sa place au chargement.
    "photos",
    # Mémoire d'une collecte à l'autre (voir app/historique.py) : c'est ce
    # fichier, versionné, qui traverse le temps — pas la base, recréée à
    # chaque exécution.
    "vue_le", "revue_le", "absences", "prix_precedent", "prix_baisse_le",
]


ETATS = ("sans_travaux", "travaux", "inconnu")


def _bien(row) -> dict:
    """Une ligne de base → dict exportable.

    `features` et `etat_declare` ont été constatés à la collecte, quand la page
    entière était sous les yeux (voir chargement.preparer_annonce) : la ligne
    les porte déjà. `vendu` et `plusieurs_biens` sont constatés ici, sur le
    texte brut de la ligne, pour que les filtres du chargement gardent leur
    garde-fou sans avoir à relire la page — qui ne sort plus.
    """
    bien = db._row_vers_dict(row)
    brut = dict(row)
    page = {"texte": brut.get("texte") or "", "description": brut.get("description") or ""}
    bien["vendu"] = qualite.est_vendu(page)
    bien["plusieurs_biens"] = qualite.enumere_plusieurs_biens(page)
    return {cle: bien.get(cle) for cle in CHAMPS}


def alleger(bien: dict) -> dict:
    """Un bien du fichier précédent, sans le texte de sa page.

    Les biens déjà publiés ne seront pas tous recollectés avant des semaines —
    une agence est revisitée tous les deux jours au mieux, et la règle de
    sortie garde ceux dont le site n'a pas été revu. Les laisser porter leur
    texte jusque-là, c'est garder vingt-six méga-octets de pages de tiers, et
    leurs numéros, dans le fichier public pendant tout ce temps.

    On constate donc ici, UNE dernière fois et sur la page entière, ce que le
    chargement y aurait lu — critères, état déclaré, bien vendu, page
    catalogue —, puis on retire le texte. Un bien exporté sous la forme
    nouvelle n'a plus de texte : pour lui, cette fonction n'est qu'une
    projection sur les champs publiés.
    """
    if not bien.get("texte"):
        return {cle: bien.get(cle) for cle in CHAMPS}
    allege = dict(bien)
    if not allege.get("features"):
        allege["features"] = scoring.extraire_criteres(
            allege.get("titre") or "",
            f"{allege.get('description') or ''} {allege['texte']}")
    if allege.get("etat_declare") not in ETATS:
        allege["etat_declare"] = etat_du_bien.etat_declare(allege)
    if allege.get("vendu") is None:
        allege["vendu"] = qualite.est_vendu(allege)
    if allege.get("plusieurs_biens") is None:
        allege["plusieurs_biens"] = qualite.enumere_plusieurs_biens(allege)
    return {cle: allege.get(cle) for cle in CHAMPS}


def sans_doublon_d_url(annonces: list[dict]) -> list[dict]:
    """Une page d'annonce = un bien. Garde le plus récemment revu.

    L'identifiant d'un bien est fabriqué à partir du nom de son agence ; si
    ce nom change, le même logement réapparaît sous un second identifiant et
    la liste le montre deux fois. C'est arrivé : une collecte ciblée avait
    nommé les agences d'après leur domaine (`ajc-immobilier-com-…` au lieu de
    `ajc-immobilier-…`), et neuf biens se sont dédoublés.

    L'historique finit par écarter la version périmée — mais seulement après
    deux passages sur l'agence, soit plusieurs jours d'affichage fautif. On
    tranche donc ici, sur le seul critère qui ne dépend d'aucun nom : deux
    annonces qui pointent la même page sont le même bien.
    """
    par_url: dict[str, dict] = {}
    ordre: list[str] = []
    for bien in annonces:
        url = bien.get("url")
        if not url:                                  # sans URL, on ne compare rien
            ordre.append(id(bien))
            par_url[id(bien)] = bien
            continue
        garde = par_url.get(url)
        if garde is None:
            ordre.append(url)
            par_url[url] = bien
        elif (bien.get("revue_le") or "") > (garde.get("revue_le") or ""):
            # La plus fraîche gagne, mais elle hérite de la date de première
            # vue la plus ancienne : c'est bien le même bien depuis ce jour-là.
            fusion = dict(bien)
            anciennes = [d for d in (bien.get("vue_le"), garde.get("vue_le")) if d]
            if anciennes:
                fusion["vue_le"] = min(anciennes)
            par_url[url] = fusion
        elif garde.get("vue_le") and bien.get("vue_le"):
            garde["vue_le"] = min(garde["vue_le"], bien["vue_le"])
    return [par_url[cle] for cle in ordre]


def _photo_publiee_egale_photo_affichee(annonces: list[dict]) -> list[dict]:
    """Publie, pour chaque bien, la photo que le chargement retiendra vraiment.

    Le fichier annonçait autre chose que ce que le visiteur voit, dans les
    deux sens : une photo qui ne s'affichera jamais, ou aucune alors qu'une
    s'affiche. Deux causes, aucune fautive en soi :

    - `photo` est choisie à la COLLECTE, bien par bien. Or « c'est du mobilier
      de site » est un constat de CORPUS — on ne le sait qu'en voyant la même
      image sur plusieurs annonces, donc plus tard, quand la voisine existe.
      Chez LOR Immobilier, une image sert à neuf biens ; chez Bonnabelle, deux
      annonces en double se partagent la leur.
    - à l'inverse, un bien sans `photo` retenue en a souvent une parfaitement
      affichable plus loin dans ses candidates : le chargement la trouve, le
      fichier n'en disait rien.

    L'écart n'était pas visible à l'écran — le chargement tranchait déjà bien.
    Il faussait le décompte : le catalogue se disait illustré là où il ne
    l'était pas, et l'inverse. On aligne donc le fichier sur l'affichage, en
    appelant la fonction du chargement plutôt qu'en réécrivant sa règle.
    """
    mobilier = chargement._photos_de_mobilier(annonces)
    return [dict(bien, photo=chargement.photo_retenue(bien, mobilier))
            for bien in annonces]


def main() -> None:
    conn = db.connexion()
    rows = conn.execute(
        "SELECT * FROM annonces WHERE source IS NOT NULL AND source <> 'démo' "
        "ORDER BY score_total DESC"
    ).fetchall()
    biens = [_bien(r) for r in rows]
    conn.close()

    sortie = RACINE / "data" / "annonces_reel.json"
    sortie.parent.mkdir(exist_ok=True)

    # On reporte l'historique du fichier précédent : date de première vue,
    # baisses de prix, et retrait des annonces que l'agence a enlevées.
    precedentes = []
    if sortie.exists():
        try:
            precedentes = json.loads(sortie.read_text(encoding="utf-8"))
        except ValueError:
            precedentes = []
    # Seules les cibles réellement parcourues cette fois font autorité : une
    # collecte écourtée ne doit pas faire disparaître les biens des autres.
    # Une cible = un nom ET un domaine (voir historique.identite) : ni l'un ni
    # l'autre pris seul ne décrit ce que la collecte visite vraiment.
    #
    # Et une cible dont la visite s'est ARRÊTÉE AVANT LA FIN de sa liste ne
    # fait pas autorité non plus : le plafond de biens, celui de pages, le
    # budget de temps ou la réserve d'adresses ont pu couper le parcours avant
    # qu'on n'atteigne l'annonce en question. Compter son absence, c'est
    # conclure de ce qu'on n'a pas cherché — la faute qui a déjà coûté
    # cinquante-six annonces Century 21 et deux cent six IAD, sous deux formes
    # différentes. Ici la visite a bien eu lieu, mais tronquée : deux cent
    # quarante et une annonces étaient en sursis pour cette raison, et le
    # catalogue perdait une vingtaine de biens par jour.
    visites = ({historique.identite(b) for b in biens}
               - {("", "")} - historique.visites_tronquees())
    fusionnees = historique.fusionner(precedentes, biens, visites,
                                      date.today().isoformat())
    # Les annonces dont le LIEN est mort — vérifié deux fois, à deux passages
    # distincts (scripts/verifier_liens.py) — sortent du catalogue, quelle que
    # soit la règle de sortie : sur les gros départements tronqués à chaque
    # passage, elle s'abstient, et un bien vendu resterait sinon pour toujours.
    chemin_morts = RACINE / "data" / "liens_morts.json"
    try:
        journal_morts = json.loads(chemin_morts.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        journal_morts = {}
    fusionnees, liens_morts = liens.sans_liens_morts(fusionnees, journal_morts)
    if liens_morts:
        print(f"  {liens_morts} annonce(s) retirée(s) — lien mort confirmé")
    # Les agences qui ont demandé leur retrait (data/agences_exclues.json) :
    # leurs biens sortent du fichier publié, quel que soit l'état de leur page.
    fusionnees, exclues = exclusions.sans_exclues(fusionnees)
    if exclues:
        print(f"  {exclues} annonce(s) retirée(s) — agence exclue à sa demande")
    fusionnees = sans_doublon_d_url(fusionnees)
    fusionnees = _photo_publiee_egale_photo_affichee(fusionnees)

    # Dernier filet : aucun identifiant de tiers ne doit atteindre le dépôt.
    # Le caviardage à l'entrée devrait suffire ; s'il a laissé passer quelque
    # chose, mieux vaut écarter le bien et le dire que faire refuser le dépôt
    # entier — ou publier la clé de quelqu'un.
    propres, allegees, abandonnes = [], 0, []
    for bien in fusionnees:
        bien, retires = caviardage.preparer_pour_publication(bien)
        if retires:
            allegees += 1
        champs = caviardage.identifiants_restants(bien)
        if champs:
            abandonnes.append((bien.get("id"), champs))
            continue
        propres.append(bien)
    if allegees:
        print(f"  {allegees} bien(s) allégé(s) d'une adresse signée par un jeton")
    if abandonnes:
        print(f"  {len(abandonnes)} bien(s) abandonné(s) — identifiant de tiers "
              f"irréductible : {sorted({c for _, cs in abandonnes for c in cs})}")
        for identifiant, champs in abandonnes[:5]:
            print(f"    {identifiant} → {champs}")
    # Après le caviardage, qui a encore besoin du texte pour le nettoyer, et
    # avant l'écriture : le texte de la page ne franchit jamais cette ligne.
    allegees_du_texte = sum(1 for b in propres if b.get("texte"))
    fusionnees = [alleger(b) for b in propres]
    if allegees_du_texte:
        print(f"  {allegees_du_texte} bien(s) délesté(s) du texte de leur page")

    # Ordre STABLE, par identifiant. Le fichier est committé six fois par jour
    # et pèse un méga-octet : sans ordre fixe, chaque export réécrit tout et
    # git stocke une copie entière à chaque fois — plus de deux gigaoctets par
    # an pour un catalogue qui bouge à la marge. Trié, seules les lignes des
    # biens réellement modifiés changent, et le dépôt ne grossit que de ce
    # qui a bougé.
    fusionnees.sort(key=lambda b: b.get("id") or "")
    sortie.write_text(json.dumps(fusionnees, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    nouveaux = sum(1 for b in fusionnees if b.get("vue_le") == date.today().isoformat()
                   and b.get("revue_le") == date.today().isoformat()
                   and b.get("id") in {x.get("id") for x in biens}
                   and b.get("id") not in {x.get("id") for x in precedentes})
    baisses = sum(1 for b in fusionnees
                  if b.get("prix_baisse_le") == date.today().isoformat())
    retirees = len(precedentes) + len(biens) - len(fusionnees) - (len(biens) - nouveaux)
    print(f"{len(fusionnees)} annonce(s) exportée(s) vers {sortie}")
    print(f"  dont {nouveaux} nouvelle(s), {baisses} baisse(s) de prix, "
          f"{max(retirees, 0)} retirée(s) par l'agence")


if __name__ == "__main__":
    main()
