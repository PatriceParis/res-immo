"""Envoie les alertes e-mail aux inscriptions confirmées.

Tourne une fois par jour (voir .github/workflows/alertes.yml), APRÈS la
collecte du matin : chaque abonné reçoit les biens apparus depuis son dernier
envoi, filtrés par les critères qu'il a lui-même fixés. Pas de nouveauté dans
ses critères = pas de courriel — le silence est une information, pas un oubli.

Sans configuration (DATABASE_URL, ALERTES_SECRET, RESEND_API_KEY), le script
dit qu'il n'a rien à faire et sort en succès : le workflow peut exister avant
les clés sans jamais échouer pour de mauvaises raisons.

Les journaux des GitHub Actions sont PUBLICS : ce script n'imprime jamais une
adresse — seulement des comptes.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import json  # noqa: E402

from app import alertes, alertes_db, chargement, courriels  # noqa: E402

REEL = RACINE / "data" / "annonces_reel.json"


def main() -> None:
    manquantes = [nom for nom in ("DATABASE_URL", "ALERTES_SECRET", "RESEND_API_KEY")
                  if not os.environ.get(nom, "").strip()]
    if manquantes:
        print(f"Alertes non configurées ({', '.join(manquantes)} absent) — rien à faire.")
        return

    secret = os.environ["ALERTES_SECRET"]
    biens = json.loads(REEL.read_text(encoding="utf-8"))
    # Seuls les biens réellement SERVIS peuvent être annoncés : alerter sur un
    # bien que la page d'arrivée ne montre pas serait promettre dans le vide.
    servis = chargement.biens_servis(biens)
    print(f"{len(servis)} bien(s) servi(s) au catalogue")

    conn = alertes_db.connexion()
    try:
        alertes_db.preparer(conn)
        inscriptions = alertes_db.actives(conn)
        print(f"{len(inscriptions)} inscription(s) confirmée(s)")
        envoyes = muets = rates = 0
        aujourd_hui = date.today().isoformat()
        for inscription in inscriptions:
            depuis = inscription["dernier_envoi"] or inscription["cree_le"]
            frais = [b for b in alertes.nouveaux_depuis(servis, depuis)
                     if alertes.correspond(b, inscription["prix_max"],
                                           inscription["terroirs"])]
            if not frais:
                muets += 1
                continue
            sujet, texte = alertes.corps_alerte(
                inscription["email"], inscription["prix_max"],
                inscription["terroirs"], frais, secret)
            if courriels.envoyer(
                    inscription["email"], sujet, texte,
                    alertes.lien_desinscription(inscription["email"], secret)):
                alertes_db.noter_envoi(conn, inscription["email"], aujourd_hui)
                envoyes += 1
            else:
                rates += 1
        print(f"envoyé(s) : {envoyes} · sans nouveauté : {muets} · échec(s) : {rates}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
