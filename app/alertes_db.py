"""Le stockage des inscriptions — la seule pièce qui exige un service externe.

Pourquoi une base HORS du dépôt, alors que tout le reste vit dans git : une
adresse e-mail est une donnée personnelle et le dépôt est public. La leçon
vient du dispositif de mise en relation retiré le 17 août, qui journalisait
les adresses à côté de la base — donc dans /tmp sur l'hébergement, effacées à
chaque redémarrage. Recueillir pour perdre est le pire des deux mondes.

pg8000 plutôt qu'un pilote compilé : du Python pur, qui s'installe partout —
la fonction Vercel comme le runner GitHub — sans chaîne de compilation. Et du
Postgres standard : Neon aujourd'hui, n'importe quel fournisseur demain.

Tout échoue FERMÉ. Sans DATABASE_URL, `connexion()` lève, et l'appelant
répond « pas encore ouvert » — jamais un formulaire qui encaisse une adresse
sans destination. L'import de pg8000 est paresseux pour la même raison : son
absence ne doit pas empêcher le reste de l'application de servir.

UNE inscription par adresse (UNIQUE) : c'est le niveau gratuit assumé — une
alerte par personne — et c'est la contrainte qui rend la désinscription sans
ambiguïté : effacer l'adresse efface tout.
"""

from __future__ import annotations

import json
import os
import ssl
from urllib.parse import unquote, urlparse

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alertes (
    email         TEXT PRIMARY KEY,
    prix_max      INTEGER,
    terroirs      TEXT NOT NULL,
    confirme      BOOLEAN NOT NULL DEFAULT FALSE,
    cree_le       DATE NOT NULL DEFAULT CURRENT_DATE,
    dernier_envoi DATE
)
"""


def connexion():
    """Ouvre la base désignée par DATABASE_URL, ou lève RuntimeError."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL absent : les alertes ne sont pas ouvertes")
    try:
        import pg8000.dbapi
    except ImportError as exc:                     # pragma: no cover
        raise RuntimeError("pg8000 manquant (voir requirements.txt)") from exc
    morceaux = urlparse(url)
    return pg8000.dbapi.connect(
        user=unquote(morceaux.username or ""),
        password=unquote(morceaux.password or ""),
        host=morceaux.hostname,
        port=morceaux.port or 5432,
        database=(morceaux.path or "/postgres").lstrip("/"),
        # Neon comme la plupart des Postgres hébergés exigent TLS ; le
        # contexte par défaut vérifie le certificat — on ne le désarme pas.
        ssl_context=ssl.create_default_context(),
    )


def preparer(conn) -> None:
    with conn.cursor() as curseur:
        curseur.execute(_SCHEMA)
    conn.commit()


def inscrire(conn, email: str, prix_max: int | None, terroirs: list[str]) -> None:
    """Enregistre ou remplace l'inscription, NON confirmée.

    Modifier une inscription repasse par la confirmation, même si l'adresse
    était déjà confirmée : le formulaire est public, et changer les critères
    de quelqu'un d'autre serait sinon à la portée de n'importe qui.
    """
    with conn.cursor() as curseur:
        curseur.execute(
            "INSERT INTO alertes (email, prix_max, terroirs, confirme)"
            " VALUES (%s, %s, %s, FALSE)"
            " ON CONFLICT (email) DO UPDATE"
            " SET prix_max = EXCLUDED.prix_max,"
            "     terroirs = EXCLUDED.terroirs,"
            "     confirme = FALSE",
            (email, prix_max, json.dumps(terroirs, ensure_ascii=False)))
    conn.commit()


def confirmer(conn, email: str) -> bool:
    with conn.cursor() as curseur:
        curseur.execute("UPDATE alertes SET confirme = TRUE WHERE email = %s",
                        (email,))
        touche = curseur.rowcount
    conn.commit()
    return bool(touche)


def supprimer(conn, email: str) -> bool:
    """L'effacement promis : immédiat, total, sans trace conservée."""
    with conn.cursor() as curseur:
        curseur.execute("DELETE FROM alertes WHERE email = %s", (email,))
        touche = curseur.rowcount
    conn.commit()
    return bool(touche)


def actives(conn) -> list[dict]:
    """Les inscriptions CONFIRMÉES — les seules auxquelles on écrit."""
    with conn.cursor() as curseur:
        curseur.execute(
            "SELECT email, prix_max, terroirs, cree_le, dernier_envoi"
            " FROM alertes WHERE confirme ORDER BY email")
        lignes = curseur.fetchall()
    sortie = []
    for email, prix_max, terroirs, cree_le, dernier_envoi in lignes:
        sortie.append({
            "email": email,
            "prix_max": prix_max,
            "terroirs": json.loads(terroirs or "[]"),
            "cree_le": cree_le.isoformat() if cree_le else "",
            "dernier_envoi": dernier_envoi.isoformat() if dernier_envoi else "",
        })
    return sortie


def noter_envoi(conn, email: str, jour_iso: str) -> None:
    with conn.cursor() as curseur:
        curseur.execute("UPDATE alertes SET dernier_envoi = %s WHERE email = %s",
                        (jour_iso, email))
    conn.commit()
