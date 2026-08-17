"""Envoi de courriels par l'API de Resend — urllib, aucune dépendance neuve.

Pourquoi un service d'envoi plutôt que SMTP direct : un courriel parti d'une
fonction Vercel ou d'un runner GitHub sans réputation d'expéditeur finit en
indésirable, quand il n'est pas refusé. Resend (ou équivalent) porte cette
réputation — c'est tout ce qu'on lui demande.

Tant que le nom de domaine n'existe pas, l'expéditeur par défaut est celui du
bac à sable de Resend, qui ne peut écrire qu'au titulaire du compte : les
essais sont donc possibles avant le domaine, sans risquer d'écrire au monde.

Aucune adresse de destinataire n'est journalisée ici : les journaux des
GitHub Actions sont publics.
"""

from __future__ import annotations

import json
import os
import urllib.request

API = "https://api.resend.com/emails"
EXPEDITEUR_BAC_A_SABLE = "Refuge Immo <onboarding@resend.dev>"


def configure() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip())


def envoyer(destinataire: str, sujet: str, texte: str,
            lien_desinscription: str = "", timeout: int = 20) -> bool:
    """Envoie un courriel TEXTE. Vrai si le service l'a accepté.

    L'en-tête List-Unsubscribe reprend le lien de désinscription : les
    messageries affichent alors leur propre bouton « se désabonner », et il
    fait exactement ce que promet la politique de confidentialité.
    """
    cle = os.environ.get("RESEND_API_KEY", "").strip()
    if not cle:
        return False
    charge: dict = {
        "from": os.environ.get("ALERTES_EXPEDITEUR", EXPEDITEUR_BAC_A_SABLE),
        "to": [destinataire],
        "subject": sujet,
        "text": texte,
    }
    if lien_desinscription:
        charge["headers"] = {"List-Unsubscribe": f"<{lien_desinscription}>"}
    requete = urllib.request.Request(
        API, data=json.dumps(charge).encode("utf-8"),
        headers={"Authorization": f"Bearer {cle}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            return 200 <= reponse.status < 300
    except Exception:
        return False
