"""Rédiger une description à partir de NOS données, sans toucher à celle de l'agence.

Deux idées qu'il ne faut pas confondre
--------------------------------------
« Réécrire le texte de l'agence pour éviter le contenu dupliqué » et « écrire
notre propre texte à partir des faits » se ressemblent de loin. Ce sont deux
choses opposées.

**Réécrire** est précisément ce que les règles anti-spam de Google appellent
du contenu récupéré : « modifier légèrement le contenu provenant d'autres
sources » y figure au même titre que la copie pure. Un texte filé n'est pas
un texte original, il est un texte copié qu'on a rendu plus difficile à
attribuer — la manœuvre est reconnue, et elle vise à tromper. Elle ne
protège pas davantage sur le plan du droit : les faits d'une annonce
appartiennent à tout le monde, la formulation appartient à son auteur, et
une réécriture s'attaque justement à la formulation.

Le passer par un modèle de langage ajouterait un troisième défaut, le plus
grave ici : l'invention. Un modèle à qui l'on demande de reformuler « maison
de 120 m² » écrira volontiers « spacieuse maison familiale baignée de
lumière » — la lumière, personne ne l'a mesurée. Sur des annonces à deux
cent mille euros, une qualité inventée est un mensonge, et tout ce projet
tient sur la promesse inverse.

**Écrire à partir des faits** ne pose aucun de ces problèmes. Nous disposons
de données que l'agence n'a pas : altitude, densité communale, risques
Géorisques, distance à la centrale la plus proche, temps de trajet, gare, et
notre propre notation pilier par pilier. Les mettre en phrases, et les
comparer à leur terroir, produit un texte que personne d'autre ne peut
écrire — donc original au sens propre, et pas seulement au sens juridique.

Le risque réel, et comment il est tenu
--------------------------------------
Ce n'est pas la duplication avec les agences : c'est la duplication entre
NOS pages. Neuf cent quatre-vingt-treize fiches bâties sur le même gabarit
diraient toutes la même chose, et ce serait à bon droit jugé sans valeur.

La parade n'est pas de faire tourner des synonymes — ce serait filer notre
propre texte, avec la même malhonnêteté en petit. Elle est de ne rien dire
qui ne soit propre au bien : chaque phrase porte une comparaison chiffrée à
son département, et n'existe que si la donnée existe. Un bien sans altitude
connue n'aura pas la phrase d'altitude. `tests/test_redaction.py` mesure la
distinction obtenue sur le catalogue réel, et refuse de descendre en dessous.
"""

from __future__ import annotations

import statistics

# En deçà, comparer à « la médiane du département » n'a pas de sens.
ECHANTILLON_MINI = 5
# Écart en deçà duquel on ne dit rien : « 3 % au-dessus » est du bruit.
ECART_PARLANT = 12


def contexte_departemental(biens: list[dict]) -> dict:
    """Médianes par département, pour situer chaque bien parmi ses voisins.

    C'est ce qui distingue une description d'un relevé : « 210 m d'altitude »
    ne dit rien, « 160 m au-dessus de la médiane du département » situe.
    """
    par_dept: dict = {}
    for bien in biens:
        dept = str(bien.get("departement") or "")
        if dept:
            par_dept.setdefault(dept, []).append(bien)
    contexte = {}
    for dept, lot in par_dept.items():
        if len(lot) < ECHANTILLON_MINI:
            continue
        contexte[dept] = {
            "nombre": len(lot),
            "altitude": _mediane(b.get("altitude") for b in lot),
            "surface": _mediane(b.get("surface_m2") for b in lot),
            "terrain": _mediane(b.get("terrain_m2") for b in lot),
            "score": _mediane(b.get("score_total") for b in lot),
        }
    return contexte


def _mediane(valeurs):
    v = [x for x in valeurs if x is not None]
    return statistics.median(v) if v else None


def _nombre(valeur) -> str:
    return f"{round(valeur):,}".replace(",", " ")


def _distance(km) -> str:
    """« 25 km », « 2,8 km » — jamais « 25.0 km ».

    Le point décimal anglais et le zéro inutile sont les deux marques qui
    trahissent le plus vite un texte fabriqué. On écrit comme on écrirait.
    """
    if km is None:
        return ""
    arrondi = round(float(km), 1)
    if arrondi == int(arrondi):
        return f"{int(arrondi)}\u00a0km"
    return f"{arrondi:.1f}".replace(".", ",") + "\u00a0km"


# Le genre du type de bien, pour que le participe s'accorde. « Maison situé »
# se remarque à la première lecture et discrédite tout ce qui suit.
FEMININS = {"maison", "longère", "fermette", "propriété", "villa", "grange",
            "chaumière", "demeure", "bâtisse", "ferme", "maison de maître",
            "bergerie", "métairie"}


def _accord(type_bien: str) -> tuple[str, str]:
    """(nom capitalisé, « e » d'accord si le nom est féminin)."""
    nom = (type_bien or "bien").strip()
    return nom.capitalize(), ("e" if nom.lower() in FEMININS else "")


def _ecart(valeur, reference) -> int | None:
    """Écart en pourcentage, ou None s'il n'est pas assez net pour être dit."""
    if valeur is None or not reference:
        return None
    ecart = round(100 * (valeur - reference) / reference)
    return ecart if abs(ecart) >= ECART_PARLANT else None


def _situation(bien: dict, repere: dict | None) -> str:
    phrases = []
    type_bien, e = _accord(bien.get("type_bien"))
    commune = bien.get("commune")
    if not commune:
        return ""

    altitude = bien.get("altitude")
    if altitude is not None:
        debut = (f"{type_bien} situé{e} à {commune}, "
                 f"à {round(altitude)} m d'altitude")
        if repere and repere.get("altitude") is not None:
            marche = round(altitude - repere["altitude"])
            if abs(marche) >= 40:
                debut += (f" — soit {abs(marche)} m "
                          f"{'au-dessus' if marche > 0 else 'en dessous'} de la "
                          f"médiane des biens que nous suivons dans le "
                          f"département")
        phrases.append(debut + ".")
    else:
        phrases.append(f"{type_bien} situé{e} à {commune}.")

    densite = bien.get("densite_hab_km2")
    if densite is not None:
        if densite < 40:
            phrases.append(
                f"La commune compte {_nombre(densite)} habitants au kilomètre "
                f"carré : une densité rurale, qui limite l'effet d'îlot de "
                f"chaleur en été.")
        elif densite < 150:
            phrases.append(f"La densité communale est de {_nombre(densite)} "
                           f"habitants au kilomètre carré.")
        else:
            phrases.append(
                f"Avec {_nombre(densite)} habitants au kilomètre carré, la "
                f"commune est urbaine : le bâti y accumule davantage la "
                f"chaleur estivale qu'en pleine campagne.")
    return " ".join(phrases)


def _le_bien(bien: dict, repere: dict | None) -> str:
    phrases = []
    surface, terrain = bien.get("surface_m2"), bien.get("terrain_m2")
    if surface:
        debut = f"La surface habitable est de {_nombre(surface)} m²"
        if bien.get("pieces"):
            debut += f" pour {bien['pieces']} pièces"
        ecart = _ecart(surface, (repere or {}).get("surface"))
        if ecart is not None:
            debut += (f", {abs(ecart)} % "
                      f"{'de plus' if ecart > 0 else 'de moins'} que la "
                      f"médiane départementale")
        phrases.append(debut + ".")
    if terrain:
        debut = f"Le terrain mesure {_nombre(terrain)} m²"
        if terrain >= 10000:
            hectares = f"{terrain / 10000:.1f}".rstrip("0").rstrip(".")
            debut += f", soit {hectares.replace('.', ',')} hectare"
            if terrain >= 20000:
                debut += "s"
        ecart = _ecart(terrain, (repere or {}).get("terrain"))
        if ecart is not None and terrain < 10000:
            debut += (f", {abs(ecart)} % "
                      f"{'au-dessus' if ecart > 0 else 'en dessous'} de la "
                      f"médiane locale")
        phrases.append(debut + ".")
    if bien.get("prix") and surface:
        phrases.append(f"Le prix demandé revient à "
                       f"{_nombre(bien['prix'] / surface)} € le mètre carré.")
    if bien.get("dpe"):
        phrases.append(f"Le diagnostic de performance énergétique est classé "
                       f"{bien['dpe']}.")
    return " ".join(phrases)


def _resilience(bien: dict, repere: dict | None) -> str:
    detail = bien.get("score_detail") or {}
    piliers = detail.get("piliers") or {}
    if not piliers:
        return ""
    total = bien.get("score_total")
    phrases = []
    if total is not None:
        debut = f"Refuge Immo note ce bien {round(total)} sur 100"
        if detail.get("classe"):
            debut += f" — {detail['classe'].lower()}"
        ecart = _ecart(total, (repere or {}).get("score"))
        if ecart is not None:
            debut += (f", {abs(ecart)} % "
                      f"{'au-dessus' if ecart > 0 else 'en dessous'} de la "
                      f"médiane du département")
        phrases.append(debut + ".")

    # On ne récite pas les cinq piliers : on nomme celui qui porte la note et
    # celui qui la retient. C'est ce qu'un lecteur retient, et ce qui varie
    # réellement d'un bien à l'autre.
    notes = [(cle, d) for cle, d in piliers.items() if d.get("max")]
    if notes:
        fort = max(notes, key=lambda kv: kv[1]["points"] / kv[1]["max"])
        faible = min(notes, key=lambda kv: kv[1]["points"] / kv[1]["max"])
        if fort[0] != faible[0]:
            phrases.append(
                f"Le pilier le mieux servi est « {fort[1]['libelle'].lower()} » "
                f"({round(fort[1]['points'])} points sur {fort[1]['max']}) ; "
                f"le plus faible, « {faible[1]['libelle'].lower()} » "
                f"({round(faible[1]['points'])} sur {faible[1]['max']}).")

    # Les badges d'accès (« gare à 2,8 km · Paris en 90 min ») redisent le
    # paragraphe suivant : les répéter ferait bavard et gonflerait le texte
    # sans rien apporter — le défaut même qu'on cherche à éviter.
    atouts = [b for b in (bien.get("badges") or [])
              if b and "·" not in b and "Paris" not in b]
    if atouts:
        phrases.append("Éléments relevés dans l'annonce : "
                       + ", ".join(atouts[:6]) + ".")
    return " ".join(phrases)


def _acces(bien: dict) -> str:
    phrases = []
    minutes = bien.get("temps_voiture_min")
    if minutes:
        heures, reste = divmod(round(minutes), 60)
        duree = f"{heures} h {reste:02d}" if heures else f"{reste} min"
        phrase = f"Paris est à {duree} de route"
        if bien.get("distance_km"):
            phrase += f", pour environ {round(bien['distance_km'] * 1.25)} km"
        phrases.append(phrase + ".")
    train = bien.get("train")
    if isinstance(train, dict) and train.get("nom"):
        phrase = f"La gare la plus proche est {train['nom']}"
        if train.get("km"):
            phrase += f", à {_distance(train['km'])}"
        if train.get("minutes_paris"):
            heures, reste = divmod(round(train["minutes_paris"]), 60)
            phrase += (f", d'où Paris se rejoint en "
                       f"{f'{heures} h {reste:02d}' if heures else f'{reste} min'}")
        phrases.append(phrase + ".")
    return " ".join(phrases)


def _vigilance(bien: dict) -> str:
    risques = bien.get("risques") or {}
    phrases = []
    vigilances = [v for v in (risques.get("vigilances") or []) if v]
    if vigilances:
        phrases.append(
            "Géorisques recense sur la commune : "
            + ", ".join(v.lower() for v in vigilances[:5])
            + ". Ces risques valent pour la commune entière et non pour cette "
              "parcelle — presque toute commune française est concernée par "
              "au moins l'un d'eux. L'état des risques, obligatoire à la "
              "vente, fait seul foi.")
    if risques.get("nucleaire_km") is not None:
        nom = risques.get("nucleaire_nom") or "la plus proche"
        phrases.append(f"La centrale nucléaire {nom} se trouve à "
                       f"{round(risques['nucleaire_km'])} km.")
    return " ".join(phrases)


def _heures(minutes) -> str:
    """« 1 h 50 », « 45 min » — la durée telle qu'on la dit."""
    if not minutes:
        return ""
    heures, reste = divmod(round(minutes), 60)
    return f"{heures} h {reste:02d}" if heures else f"{reste} min"


def bloc_de_faits(bien: dict) -> list[tuple[str, str]]:
    """Les faits du bien en cinq ou six lignes, lisibles en deux secondes.

    Les comptes qui diffusent des maisons bon marché ouvrent tous leurs
    publications par le même bloc — lieu, prix, chambres, surface — et il
    tient debout pour une raison simple : on veut d'abord savoir SI l'on
    continue à lire. La prose vient après, la liste de définitions plus bas
    encore.

    Deux différences avec le leur. Le prix porte son PRIX AU MÈTRE CARRÉ, qui
    dit à lui seul si l'affaire mérite un détour. Et la dernière ligne est la
    note de résilience, que personne d'autre ne peut afficher — c'est elle
    qui sépare ce catalogue d'une liste de bonnes affaires.

    Rien n'y est écrit qui ne soit dans nos données : une ligne sans matière
    disparaît, plutôt que d'afficher un tiret ou « n.c. ».
    """
    lignes: list[tuple[str, str]] = []

    lieu = bien.get("commune") or ""
    if lieu and bien.get("code_postal"):
        lieu = f"{lieu} ({bien['code_postal']})"
    if lieu:
        lignes.append(("📍", lieu))

    prix, surface = bien.get("prix"), bien.get("surface_m2")
    if prix:
        montant = f"{_nombre(prix)} €"
        if surface:
            montant += f" · {_nombre(prix / surface)} €/m²"
        lignes.append(("💶", montant))

    mesures = []
    if surface:
        mesures.append(f"{_nombre(surface)} m² habitables")
    if bien.get("terrain_m2"):
        mesures.append(f"{_nombre(bien['terrain_m2'])} m² de terrain")
    if mesures:
        lignes.append(("📐", " · ".join(mesures)))

    if bien.get("pieces"):
        pieces = bien["pieces"]
        lignes.append(("🛏", f"{pieces} pièce{'s' if pieces > 1 else ''}"))

    train = bien.get("train")
    if isinstance(train, dict) and train.get("nom"):
        acces = f"Gare de {train['nom']}"
        if train.get("km") is not None:
            acces += f" à {_distance(train['km'])}"
        if train.get("minutes_paris"):
            acces += f" · Paris en {_heures(train['minutes_paris'])}"
        lignes.append(("🚉", acces))
    elif bien.get("temps_voiture_min"):
        lignes.append(("🚗", f"Paris en {_heures(bien['temps_voiture_min'])} de route"))

    if bien.get("score_total"):
        lignes.append(("🛡", f"Résilience {round(bien['score_total'])}/100"))
    return lignes


def description_longue(bien: dict, contexte: dict | None = None) -> list[str]:
    """Les paragraphes de la fiche, écrits depuis nos données.

    Chaque paragraphe n'existe que si sa matière existe : un bien sans
    altitude, sans score ou sans gare n'aura pas la phrase correspondante.
    C'est ce qui fait varier les textes d'une fiche à l'autre — la donnée,
    et non un tirage de synonymes.
    """
    repere = (contexte or {}).get(str(bien.get("departement") or ""))
    paragraphes = [_situation(bien, repere), _le_bien(bien, repere),
                   _resilience(bien, repere), _acces(bien), _vigilance(bien)]
    return [p for p in paragraphes if p]
