"""Effacer les identifiants d'autrui avant de les enregistrer.

Nous conservons le texte visible de chaque page d'annonce : c'est lui qui
permet de détecter une cave, un puits, un poêle à bois — la moitié du score
de résilience en dépend. Mais un site moderne mêle à son texte des jetons
techniques, et la première collecte chez IAD en a rapporté un : une clé
d'accès Mapbox, que le site emploie pour ses cartes.

GitHub a refusé le dépôt, et il a eu raison. Republier la clé d'un tiers
dans un dépôt public, c'est l'exposer à qui voudra s'en servir à ses frais —
que la page soit publique n'y change rien : elle n'a pas vocation à être
recopiée et archivée chez nous.

On les efface donc à l'entrée, avant la base et avant l'export. Aucune perte
pour la détection : personne ne cherche « cave » dans un jeton.
"""

from __future__ import annotations

import re

MARQUE = "[identifiant retiré]"

# Chaque motif vise une famille d'identifiants reconnaissable à sa forme, non
# à son contexte : c'est ce qui les rend fiables sur du texte quelconque.
MOTIFS = (
    # Mapbox — celui rencontré. `pk.` (public) et `sk.` (secret), corps JWT.
    re.compile(r"\b[ps]k\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # Jeton JWT quelconque (trois segments base64 séparés par des points).
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # Clés d'API Google, Amazon, Stripe, GitHub, Slack : formats fixes.
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bA(?:KIA|SIA)[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[0-9A-Za-z]{16,}\b"),
    re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    # Affectation explicite : api_key = « … », "token": "…", Bearer …
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|"
               r"client[_-]?secret|authorization|bearer)\b\s*[:=]?\s*"
               r"[\"']?[A-Za-z0-9_\-\.]{24,}[\"']?"),
)

# Champs qu'on nettoie. On ne touche PAS aux adresses (`url`, `photo`) : une
# photo signée y perdrait sa signature, donc son image. Si un jour un secret
# s'y logeait, le garde-fou de l'export le dirait plutôt que de le laisser
# passer — et la bonne réponse serait alors d'écarter le bien, pas de casser
# son adresse.
CHAMPS_A_CAVIARDER = ("texte", "description", "titre")


def caviarder(texte: str) -> str:
    """Le texte, ses identifiants remplacés par une marque explicite."""
    if not texte:
        return texte
    for motif in MOTIFS:
        texte = motif.sub(MARQUE, texte)
    return texte


def caviarder_annonce(annonce: dict) -> dict:
    """Une annonce dont les champs libres ne portent plus d'identifiant."""
    propre = dict(annonce)
    for champ in CHAMPS_A_CAVIARDER:
        if propre.get(champ):
            propre[champ] = caviarder(propre[champ])
    return propre


def porte_un_identifiant(valeur: str) -> bool:
    return bool(valeur) and any(motif.search(valeur) for motif in MOTIFS)


def preparer_pour_publication(annonce: dict) -> tuple[dict, list[str]]:
    """L'annonce publiable, et ce qu'il a fallu lui retirer.

    Écarter le bien entier serait disproportionné : quand une adresse de photo
    est signée par un jeton — cas réel chez Immo Côte d'Opale, dont les images
    portent un `access-token=` —, c'est l'IMAGE qui pose problème, pas
    l'annonce. On retire donc les adresses fautives et on garde le bien, qui
    reste une vraie maison à vendre.

    Un bien n'est abandonné que si son propre lien est en cause : sans lien
    vers l'agence, il ne sert plus à rien, et on ne peut pas le republier sans
    republier le jeton.
    """
    propre = caviarder_annonce(annonce)
    retires = []

    candidates = propre.get("photos")
    if isinstance(candidates, list):
        gardees = [u for u in candidates
                   if not (isinstance(u, str) and porte_un_identifiant(u))]
        if len(gardees) != len(candidates):
            retires.append(f"photos ({len(candidates) - len(gardees)} adresse(s))")
            propre["photos"] = gardees

    if isinstance(propre.get("photo"), str) and porte_un_identifiant(propre["photo"]):
        suivantes = [u for u in (propre.get("photos") or []) if isinstance(u, str)]
        propre["photo"] = suivantes[0] if suivantes else None
        retires.append("photo")

    return propre, retires


def identifiants_restants(annonce: dict) -> list[str]:
    """Les champs qui contiennent encore quelque chose d'un identifiant.

    Sert de garde-fou à l'export : mieux vaut écarter un bien que faire
    échouer toute une collecte sur un dépôt refusé — ou pire, publier la clé
    de quelqu'un.

    On descend dans les listes et les dictionnaires. La première version ne
    regardait que les valeurs texte de premier niveau : elle ne voyait donc
    pas `photos`, qui est une LISTE d'adresses, ni `risques`, qui est un
    dictionnaire. Le dépôt a été refusé une seconde fois pour cette raison —
    un garde-fou qui ne regarde pas partout ne garde rien.
    """
    coupables = []

    def parcourir(valeur, chemin: str) -> None:
        if isinstance(valeur, str):
            if valeur and any(motif.search(valeur) for motif in MOTIFS):
                coupables.append(chemin)
        elif isinstance(valeur, dict):
            for cle, sous in valeur.items():
                parcourir(sous, f"{chemin}.{cle}" if chemin else str(cle))
        elif isinstance(valeur, (list, tuple)):
            for rang, sous in enumerate(valeur):
                parcourir(sous, f"{chemin}[{rang}]")

    for champ, valeur in annonce.items():
        parcourir(valeur, champ)
    return coupables
