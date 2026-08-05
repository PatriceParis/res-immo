"""Registre officiel des agences immobilières (base SIRENE, code NAF 68.31Z).

Pourquoi cette piste
--------------------
OpenStreetMap et les annuaires de réseaux donnent ce que quelqu'un a bien
voulu y déclarer. Le registre des entreprises, lui, est **exhaustif par
construction** : toute agence immobilière en activité y figure, sous le code
d'activité 68.31Z « Agences immobilières ». C'est une donnée publique de
l'État, interrogeable sans clé par département.

Ce qu'il donne, et ce qu'il ne donne pas
----------------------------------------
Il donne le nom, la commune et l'identité légale — pas le site web. Il ne
remplace donc pas les autres sources : il sert de **référence** pour savoir
combien d'agences existent réellement sur un terroir, donc quelle part on
en couvre. « 29 agences branchées » ne veut rien dire ; « 29 sur les 214
recensées dans l'Orne » se discute.

Il sert aussi à repérer les manques : une agence du registre dont aucune
source ne connaît le site est une piste à chercher nommément.

Ce module ne fait AUCUN appel réseau : il interprète des réponses déjà
récupérées, ce qui le rend testable hors-ligne.
"""

from __future__ import annotations

import re
import unicodedata

# Code d'activité principale des agences immobilières (nomenclature NAF).
NAF_AGENCE_IMMOBILIERE = "68.31Z"

API = "https://recherche-entreprises.api.gouv.fr/search"

# Ce qui, dans une dénomination, trahit une activité hors cible : gestion de
# copropriété pure, marchand de biens, constructeur, promoteur.
HORS_CIBLE = re.compile(
    r"\bsyndic\b|copropriet|gestion locative|marchand de biens|promotion"
    r"|promoteur|constructeur|b[âa]tir\b|lotisseur|amenageur", re.IGNORECASE)


def _sans_accents(texte: str) -> str:
    sans = unicodedata.normalize("NFD", texte or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sans.lower()).strip()


def parametres(departement: str, page: int = 1, par_page: int = 25) -> dict:
    """Paramètres d'appel pour un département donné."""
    return {
        "activite_principale": NAF_AGENCE_IMMOBILIERE,
        "departement": departement,
        "etat_administratif": "A",        # établissements en activité
        "page": page,
        "per_page": par_page,
    }


def agences_depuis_reponse(reponse: dict, departement: str) -> list[dict]:
    """Réponse de l'API entreprises → agences {nom, commune, departement, siren}.

    Une entreprise peut avoir plusieurs établissements : on retient ceux qui
    sont dans le département visé, car c'est l'ADRESSE de l'agence qui compte,
    pas le siège social.
    """
    agences, vues = [], set()
    for entreprise in (reponse or {}).get("results", []):
        raison = (entreprise.get("nom_complet")
                  or entreprise.get("nom_raison_sociale") or "").strip()
        if not raison or HORS_CIBLE.search(raison):
            continue
        etablissements = entreprise.get("matching_etablissements") or []
        if not etablissements and entreprise.get("siege"):
            etablissements = [entreprise["siege"]]
        for etab in etablissements:
            cp = str(etab.get("code_postal") or "")
            if not cp.startswith(str(departement)):
                continue
            siret = etab.get("siret") or entreprise.get("siren") or ""
            if siret in vues:
                continue
            vues.add(siret)
            agences.append({
                "nom": raison,
                "commune": (etab.get("libelle_commune") or "").title(),
                "code_postal": cp,
                "departement": str(departement),
                "siret": siret,
                "adresse": etab.get("adresse") or "",
            })
    return agences


def nombre_de_pages(reponse: dict) -> int:
    """Nombre de pages annoncé par l'API (1 au minimum)."""
    try:
        return max(1, int((reponse or {}).get("total_pages") or 1))
    except (TypeError, ValueError):
        return 1


def couverture(recensees: list[dict], connues: list[dict]) -> dict:
    """Part des agences du registre dont on connaît le site, par département.

    Le rapprochement se fait sur le nom normalisé : imparfait — une agence
    peut exercer sous une enseigne différente de sa raison sociale — mais il
    donne l'ordre de grandeur, qui est ce qui manquait.
    """
    noms_connus = {_sans_accents(a.get("nom", "")) for a in connues}
    par_dept: dict = {}
    for a in recensees:
        d = a.get("departement") or "?"
        etat = par_dept.setdefault(d, {"recensees": 0, "reconnues": 0, "manquantes": []})
        etat["recensees"] += 1
        nom = _sans_accents(a.get("nom", ""))
        if any(nom and (nom in c or c in nom) for c in noms_connus):
            etat["reconnues"] += 1
        else:
            etat["manquantes"].append(a)
    return par_dept
