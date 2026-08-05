"""Audit de cohérence des données servies par le site.

Pourquoi ce script existe
-------------------------
Un bug signalé par un utilisateur — la pastille d'un terroir annonçait
« 60 biens » quand la liste filtrée n'en montrait que 2 — a révélé une
famille entière d'anomalies : des **chiffres affichés qui ne décrivent pas
ce qu'ils prétendent décrire**. Compte de photos inventé à partir d'un
hachage, surface de piscine prise pour la surface habitable, prix au m²
absurde, biens comptés dans un total mais dans aucune région…

Ces défauts ne font pas planter le site : ils le rendent faux. Aucun test
unitaire ne les attrape, parce qu'ils naissent des vraies données. D'où cet
audit, qui rejoue les règles de cohérence sur la base réellement servie.

Usage :
    python scripts/auditer.py                # audite data/refuge.db
    python scripts/auditer.py --json fichier # audite un export JSON
    python scripts/auditer.py --strict       # code de sortie 1 s'il reste
                                             # des anomalies (pour la CI)
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, regions  # noqa: E402
from app.extraction import PRIX_M2_MAX, PRIX_M2_MIN  # noqa: E402
from app.marche import ECART_SIGNIFICATIF  # noqa: E402
from app.qualite import est_vendu  # noqa: E402

# Bornes de bon sens pour une maison de campagne. Au-delà, ce n'est plus la
# surface habitable qu'on a lue (terrain, dépendances, coquille de saisie).
SURFACE_MIN, SURFACE_MAX = 8, 800

# Distance maximale au-delà de laquelle un bien n'a rien à faire dans la
# sélection (même valeur que le chargement).
DISTANCE_MAX_KM = 350


class Audit:
    """Collecte les anomalies, groupées par famille."""

    def __init__(self) -> None:
        self.anomalies: dict[str, list[str]] = defaultdict(list)

    def signaler(self, famille: str, detail: str) -> None:
        self.anomalies[famille].append(detail)

    @property
    def total(self) -> int:
        return sum(len(v) for v in self.anomalies.values())


def _biens_depuis_db() -> list[dict]:
    conn = db.connexion()
    try:
        lignes = conn.execute("SELECT * FROM annonces").fetchall()
    finally:
        conn.close()
    biens = []
    for row in lignes:
        bien = dict(row)
        for champ, cle in db.CHAMPS_JSON.items():
            try:
                bien[cle] = json.loads(bien.pop(champ) or "{}")
            except (ValueError, TypeError):
                bien[cle] = {}
        biens.append(bien)
    return biens


def _etiquette(bien: dict) -> str:
    return f"{(bien.get('titre') or '?')[:52]} [{bien.get('agence') or bien.get('source')}]"


# --- Les règles ------------------------------------------------------------


def verifier_prix_au_m2(biens: list[dict], audit: Audit) -> None:
    """Le prix au m² est le révélateur le plus sûr d'une extraction ratée.

    C'est ce contrôle qui a mis au jour la propriété à 950 000 € ressortie
    à 50 m² : la première surface du texte était celle de la piscine.
    """
    for b in biens:
        prix, surface = b.get("prix"), b.get("surface_m2")
        if not prix or not surface:
            continue
        m2 = prix / surface
        if not (PRIX_M2_MIN <= m2 <= PRIX_M2_MAX):
            audit.signaler(
                "prix au m² invraisemblable",
                f"{round(m2):>6} €/m²  ({prix} € / {surface} m²)  {_etiquette(b)}")


def verifier_surfaces(biens: list[dict], audit: Audit) -> None:
    for b in biens:
        s = b.get("surface_m2")
        if s is not None and not (SURFACE_MIN <= s <= SURFACE_MAX):
            audit.signaler("surface hors bornes habitables",
                           f"{s} m²  {_etiquette(b)}")
        # « Terrain plus petit que l'habitable » paraît suspect, mais c'est le
        # cas normal d'une maison de ville : les six cas relevés (Tours,
        # quartier des Prébendes) étaient tous exacts, l'agence annonçant
        # elle-même « Terrain 70 m² ». Une règle qui crie au loup six fois sur
        # six est pire que pas de règle. On ne garde donc que ce qui est
        # réellement impossible.
        terrain = b.get("terrain_m2")
        if terrain is not None and s and terrain == s:
            audit.signaler("terrain identique à l'habitable (recopie ?)",
                           f"{terrain} m²  {_etiquette(b)}")
        if terrain is not None and terrain > 500_000:  # plus de 50 hectares
            audit.signaler("terrain démesuré",
                           f"{terrain} m²  {_etiquette(b)}")


def verifier_pieces(biens: list[dict], audit: Audit) -> None:
    """Le nombre de pièces doit être plausible pour la surface annoncée.

    Repéré à l'œil sur la première fiche du site, une fois le prix et les
    caractéristiques mis en avant : « Maison · 520 m² · 1 pièce ». Personne
    ne vend 520 m² d'une seule pièce — le chiffre vient d'une lecture ratée,
    et il s'affichait sans que rien ne le questionne.
    """
    for b in biens:
        pieces, surface = b.get("pieces"), b.get("surface_m2")
        if not pieces or not surface:
            continue
        if pieces > 30:
            audit.signaler("nombre de pièces invraisemblable",
                           f"{pieces} pièces  {_etiquette(b)}")
        elif surface / pieces > 120:      # plus de 120 m² par pièce
            audit.signaler(
                "pièces trop peu nombreuses pour la surface",
                f"{surface} m² pour {pieces} pièce(s) — "
                f"{round(surface / pieces)} m²/pièce  {_etiquette(b)}")


def verifier_geographie(biens: list[dict], audit: Audit) -> None:
    """Département, région et coordonnées doivent se confirmer entre eux."""
    for b in biens:
        cp, dept = b.get("code_postal"), b.get("departement")
        # Le département est un code à deux caractères ('61', '2A'). S'il porte
        # autre chose, c'est une base d'une version antérieure : rien à auditer.
        if dept and len(str(dept)) != 2:
            continue
        if cp and dept and not cp.startswith(dept):
            audit.signaler("département en désaccord avec le code postal",
                           f"CP {cp} → dept {dept}  {_etiquette(b)}")
        if dept:
            attendue = regions.REGION_PAR_DEPT.get(dept)
            if attendue and b.get("region") and b["region"] != attendue:
                audit.signaler("région en désaccord avec le département",
                               f"dept {dept} → {b['region']} (attendu {attendue})  "
                               f"{_etiquette(b)}")
        lat, lon = b.get("lat"), b.get("lon")
        if lat is not None and lon is not None:
            if not (41 <= lat <= 51.5 and -5.5 <= lon <= 9.8):
                audit.signaler("coordonnées hors de France métropolitaine",
                               f"{lat}, {lon}  {_etiquette(b)}")
        d = b.get("distance_km")
        if d is not None and d > DISTANCE_MAX_KM:
            audit.signaler("hors du périmètre de 350 km",
                           f"{round(d)} km  {_etiquette(b)}")


def verifier_couverture_des_pastilles(biens: list[dict], audit: Audit) -> None:
    """La somme des pastilles doit égaler le total annoncé.

    Un bien sans région est compté dans « N biens trouvés » mais dans aucun
    terroir : l'utilisateur qui additionne les pastilles ne retombe pas sur
    ses pieds, et ce bien n'est atteignable par aucun filtre de région.
    """
    sans_region = [b for b in biens if not b.get("region")]
    for b in sans_region:
        audit.signaler(
            "bien hors de toute pastille de terroir",
            f"dept {b.get('departement') or '?'}  {_etiquette(b)}")


def verifier_score(biens: list[dict], audit: Audit) -> None:
    """Le score affiché doit être la somme de son propre détail."""
    for b in biens:
        total = b.get("score_total")
        if total is None:
            continue
        if not (0 <= total <= 100):
            audit.signaler("score hors de l'échelle /100",
                           f"{total}  {_etiquette(b)}")
        piliers = (b.get("score_detail") or {}).get("piliers") or {}
        if piliers:
            somme = sum(p.get("points", 0) for p in piliers.values())
            if abs(somme - total) > 0.51:
                audit.signaler("score total ≠ somme des piliers",
                               f"affiché {round(total)} vs détail {round(somme)}  "
                               f"{_etiquette(b)}")


def verifier_comparaison_au_marche(biens: list[dict], audit: Audit) -> None:
    """L'écart au marché doit se recalculer depuis les deux prix au m²."""
    for b in biens:
        ecart, m2, secteur = (b.get("ecart_marche_pct"), b.get("prix_m2"),
                              b.get("prix_m2_secteur"))
        if ecart is None:
            continue
        if not m2 or not secteur:
            audit.signaler("écart au marché sans prix de référence",
                           f"écart {ecart} %  {_etiquette(b)}")
            continue
        recalcule = 100 * (m2 - secteur) / secteur
        if abs(recalcule - ecart) > 1.5:
            audit.signaler("écart au marché non reproductible",
                           f"stocké {round(ecart)} % vs recalculé "
                           f"{round(recalcule)} %  {_etiquette(b)}")
        if abs(ecart) >= ECART_SIGNIFICATIF and not b.get("prix"):
            audit.signaler("écart au marché sur un bien sans prix",
                           _etiquette(b))


def verifier_biens_vendus(biens: list[dict], audit: Audit) -> None:
    """Un bien vendu encore listé, c'est la confiance perdue d'un coup."""
    for b in biens:
        if est_vendu(b):
            audit.signaler("bien vendu toujours listé", _etiquette(b))


def verifier_doublons(biens: list[dict], audit: Audit) -> None:
    """Deux fois le même bien, c'est deux fois la même déception."""
    par_url = Counter(b["url"] for b in biens if b.get("url"))
    for url, n in par_url.items():
        if n > 1:
            audit.signaler("URL présente plusieurs fois", f"{n}×  {url}")

    signatures = defaultdict(list)
    for b in biens:
        if b.get("prix") and b.get("surface_m2") and b.get("commune"):
            signatures[(b["commune"], b["prix"], b["surface_m2"])].append(b)
    for (commune, prix, surface), lot in signatures.items():
        if len(lot) > 1 and len({b.get("agence") for b in lot}) > 1:
            audit.signaler(
                "même bien chez plusieurs agences",
                f"{commune} — {prix} € / {surface} m² : "
                + ", ".join(sorted({str(b.get('agence')) for b in lot})))


def verifier_photos(biens: list[dict], audit: Audit) -> None:
    """Une annonce sans photo ne donne envie de rien.

    Un quart des biens s'affichait avec une illustration générée alors que la
    page de l'agence montrait bien des clichés : la photo n'était cherchée que
    dans schema.org et OpenGraph. Le signalement se fait par agence — quand
    TOUS les biens d'une agence sont sans photo, c'est son site qu'on lit mal,
    pas ses annonces qui en manquent.
    """
    par_agence: dict = defaultdict(lambda: [0, 0])
    for b in biens:
        etat = par_agence[b.get("agence") or b.get("source") or "?"]
        etat[0] += 1
        if (b.get("photo") or "").startswith("http"):
            etat[1] += 1
    for agence, (total, avec) in sorted(par_agence.items(), key=lambda kv: kv[1][1] - kv[1][0]):
        if total >= 3 and avec == 0:
            audit.signaler("aucune photo pour toute une agence",
                           f"{agence} — {total} bien(s), pas une seule photo")
    total = len(biens)
    avec = sum(1 for b in biens if (b.get("photo") or "").startswith("http"))
    if total and avec / total < 0.75:
        audit.signaler("couverture photo insuffisante",
                       f"{avec} bien(s) illustré(s) sur {total} "
                       f"({round(100 * avec / total)} %)")


def verifier_liens(biens: list[dict], audit: Audit) -> None:
    """Sans lien vers l'annonce d'origine, la mise en relation est morte."""
    for b in biens:
        url = b.get("url") or ""
        if not url.startswith("http"):
            audit.signaler("lien vers l'annonce manquant ou invalide", _etiquette(b))
        photo = b.get("photo") or ""
        if photo and not photo.startswith("http"):
            audit.signaler("photo à l'URL non absolue", f"{photo[:60]}  {_etiquette(b)}")


# Cases à cocher de l'interface → colonne qui les porte.
FILTRES_BOOLEENS = {
    "Cave / sous-sol": "has_cave",
    "Puits / source": "has_puits",
    "Chauffage au bois": "has_bois",
    "Panneaux solaires": "has_solaire",
    "Dépendances / grange": "has_dependances",
    "Verger / potager": "has_potager",
    "Habitat troglodyte": "has_troglodyte",
    "Commune sans inondation recensée": "hors_inondation",
}


def verifier_filtres_actifs(biens: list[dict], audit: Audit) -> None:
    """Une case qui sélectionne 0 % ou 100 % du catalogue ne filtre rien.

    C'est exactement ce qui est arrivé à « hors zone inondable » : les
    risques Géorisques ont été renommés `*_commune`, le chargement lisait
    encore l'ancienne clé, et la case laissait passer 133 biens sur 133 —
    dont 86 dans une commune documentée inondable. Silencieux, invisible
    aux tests unitaires, et pourtant la case promettait quelque chose.
    """
    for libelle, colonne in FILTRES_BOOLEENS.items():
        connus = [b for b in biens if b.get(colonne) is not None]
        if len(connus) < 20:          # échantillon trop mince pour conclure
            continue
        coches = sum(1 for b in connus if b[colonne])
        if coches == 0:
            audit.signaler("case à cocher qui ne renvoie jamais rien",
                           f"« {libelle} » ({colonne}) : 0 bien sur {len(connus)}")
        elif coches == len(connus):
            audit.signaler("case à cocher qui ne filtre rien",
                           f"« {libelle} » ({colonne}) : "
                           f"{coches} biens sur {len(connus)}")


""" Fraîcheur : au-delà, un bien affiché n'a pas été reconstaté en ligne
depuis longtemps, et peut fort bien être vendu."""
JOURS_AVANT_PEREMPTION = 45


def verifier_fraicheur(biens: list[dict], audit: Audit) -> None:
    """Un bien affiché doit avoir été revu en ligne récemment.

    La collecte s'arrête sur un budget de temps : sans rotation, elle
    revisitait toujours les mêmes premières agences, et les biens des autres
    restaient affichés indéfiniment sans jamais être reconstatés. Le site
    laissait croire à une sélection à jour.

    Ce contrôle rend la chose visible plutôt que supposée — c'est ce point
    aveugle qui a fait conclure à tort qu'un correctif d'extraction s'était
    appliqué à tout le catalogue.
    """
    from datetime import date, timedelta

    limite = (date.today() - timedelta(days=JOURS_AVANT_PEREMPTION)).isoformat()
    perimes = [b for b in biens if (b.get("revue_le") or "") < limite]
    if perimes:
        par_agence: dict = defaultdict(int)
        for b in perimes:
            par_agence[b.get("agence") or "?"] += 1
        detail = ", ".join(f"{a} ({n})" for a, n in
                           sorted(par_agence.items(), key=lambda kv: -kv[1])[:6])
        audit.signaler(
            f"bien non reconstaté depuis plus de {JOURS_AVANT_PEREMPTION} jours",
            f"{len(perimes)} bien(s) — {detail}")


RE_VILLE_DU_TITRE = re.compile(
    r"\b(?:à|a|de)\s+([A-ZÉÈÀÂÔÎÛ][\w'\-]+(?:[ -][A-ZÉÈÀÂÔÎÛ][\w'\-]+){0,3})")


def _sans_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def verifier_commune_conforme_au_titre(biens: list[dict], audit: Audit) -> None:
    """La commune enregistrée ne doit pas contredire celle du titre.

    Quand la page ne donne pas d'adresse, le code postal du pied de page —
    celui de l'agence — est pris pour celui du bien. Cas réel : sept offres
    « Maison + Terrain à Oslon / Seurre / Chenôves » toutes enregistrées à
    Chalon-sur-Saône, siège du constructeur. Le site annonçait alors sept
    biens dans une commune où il n'y en avait aucun.

    Des communes voisines ou fusionnées se ressemblent peu (Montval-sur-Loir
    et Dissay-sous-Courcillon sont la même commune depuis 2016) : ce contrôle
    signale, il ne corrige pas.
    """
    for b in biens:
        m = RE_VILLE_DU_TITRE.search(b.get("titre") or "")
        commune = b.get("commune")
        if not m or not commune:
            continue
        du_titre, enregistree = _sans_accents(m.group(1)), _sans_accents(commune)
        if not du_titre or du_titre in enregistree or enregistree in du_titre:
            continue
        audit.signaler(
            "commune enregistrée en désaccord avec le titre",
            f"enregistré « {commune} », titre « {m.group(1)} »  {_etiquette(b)}")


REGLES = (
    verifier_prix_au_m2,
    verifier_surfaces,
    verifier_pieces,
    verifier_geographie,
    verifier_couverture_des_pastilles,
    verifier_score,
    verifier_comparaison_au_marche,
    verifier_biens_vendus,
    verifier_doublons,
    verifier_liens,
    verifier_photos,
    verifier_filtres_actifs,
    verifier_fraicheur,
    verifier_commune_conforme_au_titre,
)


def auditer(biens: list[dict]) -> Audit:
    audit = Audit()
    for regle in REGLES:
        regle(biens, audit)
    return audit


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--json", type=Path,
                        help="auditer un export JSON plutôt que la base")
    parseur.add_argument("--strict", action="store_true",
                        help="sortir en erreur s'il reste des anomalies")
    parseur.add_argument("--detail", type=int, default=8,
                        help="nombre de cas listés par famille (défaut : 8)")
    args = parseur.parse_args()

    if args.json:
        biens = json.loads(args.json.read_text(encoding="utf-8"))
        provenance = str(args.json)
    else:
        try:
            biens = _biens_depuis_db()
        except sqlite3.Error as e:
            print(f"Base illisible : {e}")
            return 2
        provenance = str(db.chemin_db())

    print(f"Audit de {len(biens)} bien(s) — {provenance}\n")
    if not biens:
        print("Aucun bien à auditer.")
        return 0

    audit = auditer(biens)
    if not audit.total:
        print("Aucune anomalie. Chaque chiffre décrit bien ce qu'il prétend décrire.")
        return 0

    for famille, cas in sorted(audit.anomalies.items(), key=lambda kv: -len(kv[1])):
        print(f"■ {famille} — {len(cas)} cas")
        for c in cas[:args.detail]:
            print(f"    {c}")
        if len(cas) > args.detail:
            print(f"    … et {len(cas) - args.detail} autre(s)")
        print()

    part = 100 * audit.total / len(biens)
    print(f"Total : {audit.total} anomalie(s) sur {len(biens)} biens ({part:.0f} %).")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
