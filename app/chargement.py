"""Préparation et insertion des annonces en base.

C'est ici qu'une annonce « brute » (venant du jeu de démonstration ou des
robots de collecte) est enrichie : distance et temps de route depuis Paris,
détection des équipements dans le texte, distance à la centrale nucléaire la
plus proche, puis calcul du score de résilience.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from . import (caviardage, db, etat_du_bien, extraction, gares, geo, marche,
               regions, scoring)
from .qualite import PRIX_MINI, est_bien_valide

# Au-delà, le nombre de pièces annoncé ne peut pas décrire la surface : même
# une demeure aux très grands volumes reste sous 120 m² par pièce.
MAX_M2_PAR_PIECE = 120


def preparer_annonce(brut: dict) -> dict:
    # Les identifiants d'autrui sortent AVANT tout le reste : une clé d'API
    # captée dans le texte d'une page n'a rien à faire dans notre base, et
    # encore moins dans un dépôt public (voir app/caviardage.py).
    annonce = caviardage.caviarder_annonce(brut)
    titre = annonce.get("titre", "")
    description = annonce.get("description", "")

    # Prix aberrant (< 15 000 € pour une maison = référence ou n° pris pour un
    # prix) : on l'efface plutôt que d'afficher « 3 480 € » sur une propriété.
    prix = annonce.get("prix")
    if prix is not None and prix < PRIX_MINI:
        annonce["prix"] = None

    # Le miroir du garde-fou précédent : le prix manque, mais le titre le
    # porte en toutes lettres. Six maisons de NC Immo s'affichaient « Prix sur
    # demande » alors que leur titre annonçait « 79.000,00 EUROS ». La lecture
    # des montants à la française a été corrigée à l'extraction, mais un
    # correctif d'extraction ne répare que ce qui est RECOLLECTÉ — et une
    # agence n'est revisitée que tous les deux jours. On relit donc ici, à
    # chaque chargement : le catalogue déjà publié se répare sans attendre son
    # tour, et les prochaines agences qui écrivent ainsi n'attendront pas non
    # plus.
    #
    # Mêmes bornes qu'à l'extraction, à dessein. Quand elle juge un prix au m²
    # absurde et que la surface vient du titre, c'est le PRIX qu'elle efface :
    # sans ce même contrôle ici, la relecture ressusciterait précisément ce
    # qu'elle a écarté.
    if not annonce.get("prix"):
        retrouve = extraction.prix_dans(titre)
        if retrouve and extraction.prix_m2_credible(retrouve,
                                                    annonce.get("surface_m2")):
            annonce["prix"] = retrouve

    # Nombre de pièces invraisemblable au regard de la surface. Sauté aux yeux
    # sur la première fiche du site : « Maison · 520 m² · 1 pièce ». Personne
    # ne vend 520 m² d'une seule pièce ; c'est une lecture ratée, et elle
    # s'affichait au beau milieu des caractéristiques. On préfère ne rien
    # annoncer — la surface et le terrain suffisent à situer le bien.
    pieces, surface = annonce.get("pieces"), annonce.get("surface_m2")
    if pieces and (pieces > 30 or (surface and surface / pieces > MAX_M2_PAR_PIECE)):
        annonce["pieces"] = None

    # Région : déduite du département (les annonces d'agences ne la donnent pas).
    if not annonce.get("region"):
        dept = annonce.get("departement") or (str(annonce["code_postal"])[:2]
                                              if annonce.get("code_postal") else None)
        region = regions.region_du_departement(dept)
        if region:
            annonce["region"] = region
            annonce.setdefault("departement", dept)

    lat, lon = annonce.get("lat"), annonce.get("lon")
    if lat is not None and lon is not None:
        distance = geo.distance_paris_km(lat, lon)
        annonce["distance_km"] = distance
        annonce["temps_voiture_min"] = geo.temps_voiture_min(distance)
        # Accès sans voiture : gare la plus proche et temps de train vers Paris.
        annonce["train"] = gares.gare_la_plus_proche(lat, lon)

    # Détection sur le titre + la description + le texte complet de la page
    # (`texte`) : les descriptions d'agences sont souvent très courtes, l'essentiel
    # (cave, puits, troglodyte…) est ailleurs dans la page.
    detection = f"{description} {annonce.get('texte', '')}"
    features = scoring.extraire_criteres(titre, detection)
    annonce["features"] = features

    risques = dict(annonce.get("risques") or {})
    # Données Géorisques collectées avant la distinction de portée : leurs
    # drapeaux étaient déjà **communaux** (séisme et radon ressortaient à 100 %).
    # On les requalifie pour ne pas pénaliser le bien comme s'il était exposé.
    if risques.get("source") == "georisques" and not risques.get("portee"):
        for ancien, nouveau in (("inondation", "inondation_commune"),
                                ("feu_foret", "feu_foret_commune"),
                                ("seisme", "seisme_commune"),
                                ("radon", "radon_commune"),
                                ("icpe", "icpe_commune")):
            if ancien in risques:
                risques[nouveau] = risques.pop(ancien)
        risques["portee"] = "commune"
    if lat is not None and lon is not None and risques.get("nucleaire_km") is None:
        nom, dist = geo.centrale_la_plus_proche(lat, lon)
        risques["nucleaire_km"] = dist
        risques["nucleaire_nom"] = nom
    annonce["risques"] = risques

    detail = scoring.calculer_score(annonce)
    annonce["score_total"] = detail["total"]
    annonce["score_detail"] = detail
    annonce["badges"] = detail["badges"]
    annonce["alertes"] = detail["alertes"]

    annonce["has_cave"] = int(features.get("cave", False))
    annonce["has_puits"] = int(features.get("puits", False))
    annonce["has_bois"] = int(features.get("bois", False))
    annonce["has_solaire"] = int(features.get("solaire", False))
    annonce["has_dependances"] = int(features.get("grange_dependance", False))
    annonce["has_potager"] = int(features.get("verger_potager", False))
    annonce["has_troglodyte"] = int(features.get("troglodyte", False))
    # Ce que l'annonce DÉCLARE de l'état du bien. Détecté ici, comme la cave et
    # le puits, parce que c'est ici qu'on a encore le texte de la page : l'API
    # ne le laisse pas sortir, et le catalogue servi est reconstruit depuis les
    # seules colonnes. Sans cette colonne, la page « sans travaux » n'aurait
    # rien à lire. Le constat est publié ; le texte, jamais.
    annonce["etat_declare"] = etat_du_bien.etat_declare(annonce)
    annonce["sans_travaux"] = int(annonce["etat_declare"] == "sans_travaux")
    # Mémoire portée par le fichier exporté (app/historique.py) : on la
    # laisse telle quelle, c'est elle qui dit ce qui est nouveau.
    # Le filtre d'inondation lisait encore la clé `inondation`, disparue quand
    # les risques Géorisques ont été renommés `*_commune` (leur portée réelle).
    # Plus aucun bien n'était donc marqué en zone inondable : la case « Hors
    # zone inondable » ne filtrait PLUS RIEN — 133 biens sur 133 la passaient,
    # dont 86 dans une commune où l'inondation est documentée.
    #
    # On accepte les deux clés : `inondation` quand l'information est connue à
    # la parcelle, `inondation_commune` (le cas courant) quand elle ne l'est
    # qu'à l'échelle de la commune. L'intitulé de la case le dit.
    annonce["hors_inondation"] = 0 if (
        risques.get("inondation") or risques.get("inondation_commune")) else 1
    return annonce


# Au-delà, ce n'est plus une base de repli depuis Paris — et c'est en pratique
# le signe d'une géolocalisation ratée (un numéro de référence pris pour un code
# postal envoyait des biens du Perche dans la Creuse ou le Cantal).
DISTANCE_MAX_KM = 350

# Départements des terroirs ciblés. Un bien annoncé hors de cette liste par une
# agence du Perche trahit une erreur de lecture, pas une vraie annonce
# lointaine : on l'écarte même sans coordonnées.
#
# L'Île-de-France en est exclue **volontairement** : elle est dernière au
# classement des terroirs (trop dense, artificialisée, en stress hydrique) et
# ne fait donc pas partie de la cible. Sans cette exclusion, les agences
# frontalières y ramenaient des biens — La Ferté-sous-Jouarre, Nangis — que
# l'application est précisément censée écarter.
#
# La liste se déduit ENTIÈREMENT du classement des terroirs : la Sarthe et la
# Mayenne y figuraient auparavant en dur, si bien que leurs biens étaient
# comptés dans le total mais rattachés à aucune pastille — introuvables par
# le filtre de région. Elles relèvent désormais du terroir « Pays de la Loire ».
# Trois départements du Grand Est sortent de la liste : leur territoire ENTIER
# est au-delà des 350 km que l'application s'impose, mesuré avec sa propre
# fonction — Saverne 367 km, Colmar 379, Belfort 360, et ce sont leurs points
# les plus proches. Ils étaient donc ciblés sans qu'aucun de leurs biens ne
# puisse jamais être servi : la collecte y aurait dépensé son budget pour des
# annonces écartées au chargement. La Haute-Saône, elle, reste — Vesoul est à
# 313 km, Gray à 287.
HORS_DE_PORTEE = {"67", "68", "90"}

DEPARTEMENTS_CIBLES = {
    dept for dept, region in regions.REGION_PAR_DEPT.items()
    if region in set(regions.regions_cibles()) and dept not in HORS_DE_PORTEE
}


def _signatures_suspectes(annonces: list[dict], seuil: int = 3) -> set:
    """Repère les (agence, prix, surface, terrain) qui reviennent à l'identique.

    Quand une agence sort plusieurs biens avec EXACTEMENT le même prix, la même
    surface et le même terrain, ce ne sont pas des biens : l'extraction a lu un
    bandeau commun à toutes les pages du site (cas réel : 10 annonces à
    530 000 €, 265 m², dans dix communes différentes). On préfère ne rien
    afficher plutôt que des biens fantômes aux prix faux.
    """
    compte: dict = {}
    for a in annonces:
        cle = (a.get("agence"), a.get("prix"), a.get("surface_m2"), a.get("terrain_m2"))
        if cle[1] is None and cle[2] is None:
            continue
        compte[cle] = compte.get(cle, 0) + 1
    return {cle for cle, n in compte.items() if n >= seuil}


def _photos_de_mobilier(annonces: list[dict], seuil_nom: int = 3) -> set:
    """Repère les images qui reviennent d'une annonce à l'autre chez une agence.

    Deux maisons différentes ne partagent jamais leur photo. Une image qu'on
    retrouve sur plusieurs annonces du même site n'est donc pas la photo d'un
    bien : c'est le mobilier de la page — logo, en-tête, bandeau « espace
    client », icône Facebook, icône de cloche.

    On a d'abord voulu reconnaître ce mobilier à son NOM. Trois fois de suite,
    il est revenu sous un nom neuf : `FR.png` (le drapeau du sélecteur de
    langue), `logo_og.png` (la vignette OpenGraph), puis `bell.png` — une
    cloche servie à huit annonces de la même agence et logée sous
    /vente/maisons/, donc classée parmi les MEILLEURES candidates. Aucune
    liste de noms ne rattrapera la suivante. La répétition, elle, est ce que
    voit un lecteur : toutes les annonces montrent la même image.

    Deux critères, selon ce dont on est sûr :

    - le même FICHIER (URL identique) sur au moins deux annonces : impossible
      pour deux biens distincts, quel que soit son nom ;
    - le même NOM DE FICHIER sur au moins trois annonces : les gabarits
      servent le mobilier relativement à chaque annonce (`…/1942/img/bell.png`,
      `…/1988/img/bell.png`). Trois, et non deux, parce que deux photos
      réelles peuvent honnêtement s'appeler chacune `FACADE-PRINCIPALE.jpg`.
    """
    par_url: dict = {}
    par_nom: dict = {}
    for a in annonces:
        agence = a.get("agence")
        if not agence:
            continue
        # On compte les ANNONCES où l'image apparaît, pas ses occurrences :
        # une galerie propose la même photo en plusieurs tailles, ce qui ne
        # dit rien sur son caractère décoratif.
        for photo in dict.fromkeys(_candidates(a)):
            par_url.setdefault((agence, photo), set()).add(id(a))
            nom = _nom_de_fichier(photo)
            if nom:
                par_nom.setdefault((agence, nom), set()).add(id(a))

    mobilier = set()
    for (_, photo), annonces_vues in par_url.items():
        if len(annonces_vues) >= 2:
            mobilier.add(photo)
    noms_communs = {nom for (_, nom), vues in par_nom.items() if len(vues) >= seuil_nom}
    for a in annonces:
        for photo in _candidates(a):
            if _nom_de_fichier(photo) in noms_communs:
                mobilier.add(photo)
    return mobilier


def _nom_de_fichier(url: str) -> str:
    """Ce qui identifie l'image dans son adresse — requête comprise.

    Beaucoup de sites servent leurs photos par un script :
    `image-get.inc.php?f=1024x550&n=11665`. Le nom de fichier y est le même
    pour TOUTES les annonces, et seule la requête change. S'arrêter au nom
    faisait passer les vraies photos pour du mobilier répété — l'inverse
    exact de ce qu'on cherche.
    """
    morceaux = urlparse(url or "")
    nom = morceaux.path.rsplit("/", 1)[-1]
    return f"{nom}?{morceaux.query}" if morceaux.query else nom


def _candidates(annonce: dict) -> list:
    """Les images proposées pour une annonce, de la plus plausible à la moins.

    La photo DÉJÀ RETENUE passe toujours en tête — y compris lorsqu'elle
    figure aussi dans la liste. C'est elle que `scripts/verifier_photos.py` a
    réellement ouverte et jugée conforme ; la laisser à son rang d'origine
    revenait à défaire ce travail à chaque chargement du site.

    Le défaut était invisible et durable : la vérification corrigeait la
    photo, l'export la publiait, puis le chargement reprenait bêtement la
    première candidate de la page — chez Groupe 123 Immo, une adresse en
    `/600xauto/images/…` qui répond 404 quand les vraies photos vivent sous
    `/1200xauto/images/biens/…`. Quatre-vingt-huit annonces de vingt agences
    retombaient ainsi sur leur dessin de repli, alors que le catalogue les
    comptait « illustrées ».
    """
    photos = [u for u in (annonce.get("photos") or []) if u]
    retenue = annonce.get("photo")
    if retenue:
        photos = [retenue] + [u for u in photos if u != retenue]
    return photos


def photo_retenue(annonce: dict, mobilier: set) -> str | None:
    """La première candidate qui ne soit pas du mobilier de site."""
    for photo in _candidates(annonce):
        if photo not in mobilier:
            return photo
    return None


def charger_liste(conn, annonces: list[dict]) -> int:
    """Enrichit et insère les annonces VALIDES (filtre qualité). Renvoie le nombre chargé.

    Deux temps : on prépare d'abord tous les biens retenus, car situer un prix
    par rapport à son secteur suppose de connaître l'ensemble ; on écrit
    ensuite.
    """
    retenues = _preparer_toutes(conn, annonces)
    medianes = marche.medianes_par_secteur(retenues)
    for annonce in retenues:
        db.upsert_annonce(conn, marche.situer(annonce, medianes))
    conn.commit()
    return len(retenues)


def _preparer_toutes(conn, annonces: list[dict]) -> list[dict]:
    """Applique tous les filtres de qualité et de périmètre, sans écrire."""
    suspectes = _signatures_suspectes(annonces)
    mobilier = _photos_de_mobilier(annonces)
    retenues = []
    for brut in annonces:
        retenue = photo_retenue(brut, mobilier)
        if retenue != brut.get("photo"):
            # La première candidate était du mobilier : on prend la suivante.
            # S'il n'en reste aucune, l'illustration de repli — qui ne prétend
            # rien — vaut mieux qu'une cloche présentée comme la maison.
            brut = dict(brut, photo=retenue)
        if (brut.get("agence"), brut.get("prix"), brut.get("surface_m2"),
                brut.get("terrain_m2")) in suspectes:
            continue  # doublons issus d'un bandeau de site, pas de vrais biens
        if not est_bien_valide(brut):
            continue  # blog, page catalogue, appartement, parking, vendu… : écarté
        annonce = preparer_annonce(brut)
        distance = annonce.get("distance_km")
        if distance is not None and distance > DISTANCE_MAX_KM:
            continue  # hors zone de repli, ou géolocalisation aberrante
        dept = annonce.get("departement")
        if not dept:
            # Sans localisation, on ne peut ni situer le bien, ni calculer sa
            # distance de Paris, sa densité ou sa gare : la moitié du score est
            # indéterminable et l'acheteur ne sait même pas où c'est. En
            # pratique, ce sont des pages d'agence ou de constructeur.
            continue
        if str(dept) not in DEPARTEMENTS_CIBLES:
            continue  # hors des terroirs ciblés (souvent une réf. lue comme un CP)
        retenues.append(annonce)
    return retenues


def biens_servis(annonces: list[dict]) -> list[dict]:
    """Parmi les entrées d'un export, celles que le site montrera vraiment.

    Le fichier d'export n'est pas le catalogue : il compte trois cents entrées
    de plus que le site n'en sert — pages de catalogue, départements hors
    terroir, doublons de bandeau. Tout contrôle qui les confond surestime le
    catalogue ou signale des défauts que personne ne voit.

    On rejoue donc les vrais filtres, plutôt que d'en réécrire une copie
    ailleurs : une copie finirait par diverger, et c'est précisément une
    divergence de ce genre qui a laissé passer les photos mortes.
    """
    gardes = {a.get("id") for a in _preparer_toutes(None, annonces) if a.get("id")}
    return [b for b in annonces if b.get("id") in gardes]


def charger_annonces_json(conn, chemin: Path | str) -> int:
    """Charge un fichier JSON (liste d'annonces brutes) en base."""
    return charger_liste(conn, json.loads(Path(chemin).read_text(encoding="utf-8")))
