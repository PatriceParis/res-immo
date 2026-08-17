"""Alertes e-mail : la logique, sans réseau ni base.

Ce module décide — qui reçoit quoi, avec quel jeton, sous quelle forme — et ne
touche à rien : pas de base, pas d'envoi, pas de fichier. C'est ce qui le rend
testable hors ligne, la même séparation que mandataires.py.

Le cadre est celui de la page /alertes, et il est juridique autant que
technique : le visiteur choisit ses critères LUI-MÊME, son adresse ne part
chez personne, aucune sélection n'est faite pour lui. L'alerte est un filtre
qu'il a réglé, pas un conseil qu'on lui donne — c'est ce qui la tient à
distance de l'entremise.

Trois choix qui méritent une ligne :

- **Double confirmation.** N'importe qui peut taper l'adresse d'autrui dans un
  formulaire. Une inscription ne vaut rien tant que son destinataire n'a pas
  cliqué le lien reçu ; avant cela, rien d'autre ne part que le courriel
  d'activation.
- **Le jeton est un HMAC de l'adresse.** Pas de table de jetons, pas
  d'expiration à gérer : le lien de désinscription reste valable à vie —
  c'est la promesse de la politique de confidentialité, « effacement immédiat
  et sans condition ».
- **Texte brut, zéro pixel.** Le site ne trace pas ses visiteurs ; ses
  courriels ne tracent pas leurs lecteurs. Pas de HTML, pas d'image, pas de
  lien réécrit.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from urllib.parse import quote

from . import seo
from .qualite import PRIX_MAXI

RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[a-z]{2,}$", re.IGNORECASE)

# En dessous, aucun palier proposé ; au-delà du plafond du catalogue, le
# critère ne filtrerait rien. Les bornes disent l'espace des alertes possibles.
PRIX_ALERTE_MINI = 50_000

# Un courriel-fleuve finit en indésirable et ne se lit pas. Au-delà, on compte.
BIENS_PAR_COURRIEL = 30


def valider(email: str, prix_max, terroirs) -> tuple[str, int | None, list[str]]:
    """Normalise une demande d'alerte, ou lève ValueError avec la raison.

    La validation est ici et non dans l'API : le script d'envoi et les tests
    doivent juger une inscription exactement comme le formulaire.
    """
    email = (email or "").strip().lower()
    if not RE_EMAIL.match(email):
        raise ValueError("adresse e-mail invalide")
    if prix_max is not None:
        try:
            prix_max = int(prix_max)
        except (TypeError, ValueError):
            raise ValueError("budget illisible")
        if not (PRIX_ALERTE_MINI <= prix_max <= PRIX_MAXI):
            raise ValueError("budget hors des bornes du catalogue")
    retenus: list[str] = []
    for terroir in terroirs or []:
        if terroir not in seo.TERROIRS:
            raise ValueError(f"terroir inconnu : {terroir}")
        if terroir not in retenus:
            retenus.append(terroir)
    if not retenus:
        raise ValueError("choisir au moins un terroir")
    return email, prix_max, retenus


def jeton(email: str, secret: str) -> str:
    """HMAC de l'adresse : le porteur du lien prouve qu'il a reçu nos courriels.

    Un secret vide lèverait la protection sans bruit : on refuse.
    """
    if not secret:
        raise ValueError("ALERTES_SECRET manquant")
    return hmac.new(secret.encode(), email.strip().lower().encode(),
                    hashlib.sha256).hexdigest()


def jeton_valide(email: str, secret: str, candidat: str) -> bool:
    if not (secret and candidat):
        return False
    return hmac.compare_digest(jeton(email, secret), str(candidat))


def correspond(bien: dict, prix_max: int | None, terroirs: list[str]) -> bool:
    """Le bien entre-t-il dans les critères que le visiteur a lui-même fixés ?

    Un bien SANS prix ne correspond jamais à un budget : promettre « sous
    150 000 € » sur une annonce muette serait inventer. Sans critère de
    budget, il passe.
    """
    if bien.get("region") not in terroirs:
        return False
    if prix_max is not None:
        prix = bien.get("prix")
        if not prix or prix > prix_max:
            return False
    return True


def nouveaux_depuis(biens: list[dict], depuis_iso: str) -> list[dict]:
    """Les biens APPARUS strictement après cette date (vue_le).

    C'est `vue_le` qui fait foi — la première fois qu'on a vu l'annonce — et
    non `revue_le` : une alerte signale les nouveautés, pas les re-visites.
    """
    return [b for b in biens if (b.get("vue_le") or "") > (depuis_iso or "")]


def lien_desinscription(email: str, secret: str, base: str = seo.SITE) -> str:
    return (f"{base}/api/alertes/desinscrire?email={quote(email)}"
            f"&jeton={jeton(email, secret)}")


def lien_confirmation(email: str, secret: str, base: str = seo.SITE) -> str:
    return (f"{base}/api/alertes/confirmer?email={quote(email)}"
            f"&jeton={jeton(email, secret)}")


def _criteres_en_clair(prix_max: int | None, terroirs: list[str]) -> str:
    noms = ", ".join(seo.TERROIRS[t]["cherche"] for t in terroirs)
    budget = f"jusqu'à {seo._euros(prix_max)}" if prix_max else "tous budgets"
    return f"{budget} — {noms}"


def corps_confirmation(email: str, prix_max: int | None, terroirs: list[str],
                       secret: str, base: str = seo.SITE) -> tuple[str, str]:
    """Le courriel d'activation. Sans clic, il ne se passera JAMAIS rien."""
    texte = f"""Bonjour,

Une alerte Refuge Immo a été demandée pour cette adresse, avec ces critères :
{_criteres_en_clair(prix_max, terroirs)}.

Si c'est bien vous, activez-la en ouvrant ce lien :
{lien_confirmation(email, secret, base)}

Si ce n'est pas vous, ignorez simplement ce message : sans clic de votre
part, aucune alerte ne sera envoyée et cette adresse ne sera plus contactée.

Refuge Immo — {base}
Ce courriel ne contient ni image ni suivi d'ouverture."""
    return "Activez votre alerte Refuge Immo", texte


def corps_alerte(email: str, prix_max: int | None, terroirs: list[str],
                 biens: list[dict], secret: str,
                 base: str = seo.SITE) -> tuple[str, str]:
    """Le courriel d'alerte : des faits, des liens, la porte de sortie."""
    montres = biens[:BIENS_PAR_COURRIEL]
    lignes = "\n\n".join(
        f"- {seo.titre_annonce(b)}\n  {base}{seo.url_annonce(b)}"
        for b in montres)
    reste = ""
    if len(biens) > len(montres):
        reste = (f"\n\n… et {len(biens) - len(montres)} autre(s), "
                 f"à voir sur {base}/")
    n = len(biens)
    sujet = (f"{n} nouvelle{'s' if n > 1 else ''} maison{'s' if n > 1 else ''} "
             f"dans vos critères — Refuge Immo")
    texte = f"""Bonjour,

{n} nouvelle(s) annonce(s) correspond(ent) à votre alerte
({_criteres_en_clair(prix_max, terroirs)}) :

{lignes}{reste}

Rappels utiles : ces annonces sont publiées par des agences et relevées
automatiquement — un bien peut être vendu avant que nous le sachions, et la
note de résilience compare les biens du catalogue entre eux ({base}/methode).

Pour ne plus recevoir ces alertes (effacement immédiat, sans condition) :
{lien_desinscription(email, secret, base)}

Refuge Immo — {base}
Ce courriel ne contient ni image ni suivi d'ouverture."""
    return sujet, texte
