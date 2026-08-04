"""Situer le prix d'un bien par rapport à son secteur.

Un prix seul ne dit rien : 150 000 € est cher dans la Nièvre et donné dans
l'Oise. Ce qui intéresse l'acheteur, c'est l'**écart au marché local** — et
c'est précisément ce qu'aucun portail n'affiche clairement.

La référence est la **médiane du prix au m² des biens comparables du même
département**, calculée sur la sélection elle-même. C'est une mesure modeste
mais honnête : elle ne prétend pas être le prix de marché notarial (qui
viendrait des ventes réelles, données DVF), elle situe le bien parmi ceux que
l'acheteur peut effectivement visiter.

La médiane, et non la moyenne : une seule propriété à 900 000 € ne doit pas
déplacer la référence de tout un département.
"""

from __future__ import annotations

import statistics

# En deçà, la médiane ne veut rien dire : mieux vaut ne rien afficher qu'une
# comparaison bâtie sur deux biens.
ECHANTILLON_MINI = 5

# En deçà de cet écart, le bien est « dans le marché » : afficher « 3 % sous
# le secteur » donnerait une fausse impression de précision.
ECART_SIGNIFICATIF = 10


def prix_m2(bien: dict) -> float | None:
    """Prix au m² habitable, ou None si l'un des deux manque."""
    prix, surface = bien.get("prix"), bien.get("surface_m2")
    if not prix or not surface or surface <= 0:
        return None
    return prix / surface


def medianes_par_secteur(biens: list[dict]) -> dict:
    """Médiane du prix au m² par département, sur les secteurs assez fournis."""
    par_dept: dict = {}
    for bien in biens:
        dept, pm2 = bien.get("departement"), prix_m2(bien)
        if dept and pm2:
            par_dept.setdefault(str(dept), []).append(pm2)
    return {dept: statistics.median(valeurs)
            for dept, valeurs in par_dept.items()
            if len(valeurs) >= ECHANTILLON_MINI}


def situer(bien: dict, medianes: dict) -> dict:
    """Ajoute au bien son écart au marché du secteur, si celui-ci est mesurable.

    Renvoie le bien enrichi de `prix_m2`, `prix_m2_secteur` et
    `ecart_marche_pct` (négatif = moins cher que le secteur).
    """
    enrichi = dict(bien)
    pm2 = prix_m2(bien)
    reference = medianes.get(str(bien.get("departement") or ""))
    if not pm2 or not reference:
        return enrichi
    enrichi["prix_m2"] = round(pm2)
    enrichi["prix_m2_secteur"] = round(reference)
    enrichi["ecart_marche_pct"] = round(100 * (pm2 - reference) / reference)
    return enrichi


def libelle_ecart(bien: dict) -> str:
    """Phrase courte pour l'interface, ou chaîne vide si rien de notable."""
    ecart = bien.get("ecart_marche_pct")
    if ecart is None or abs(ecart) < ECART_SIGNIFICATIF:
        return ""
    return (f"{abs(ecart)} % sous le prix du secteur" if ecart < 0
            else f"{ecart} % au-dessus du secteur")
