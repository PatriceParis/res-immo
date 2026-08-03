"""Chaîne de traitement des annonces collectées :

1. géocodage de la commune via la Base Adresse Nationale (API officielle et
   gratuite) — sans réseau, l'annonce est gardée mais sans position ;
2. enrichissement (distance/temps depuis Paris, détection des équipements,
   centrale nucléaire la plus proche) et calcul du score de résilience ;
3. enregistrement dans la même base SQLite que l'interface web.
"""

from __future__ import annotations

import hashlib
import logging

import requests

from app import db
from app.chargement import preparer_annonce

logger = logging.getLogger(__name__)

URL_BAN = "https://api-adresse.data.gouv.fr/search/"


def geocoder_commune(commune: str | None, code_postal: str | None):
    """Renvoie (lat, lon, code_postal) via la Base Adresse Nationale, ou None."""
    if not commune:
        return None
    requete = f"{commune} {code_postal or ''}".strip()
    try:
        reponse = requests.get(
            URL_BAN,
            params={"q": requete, "type": "municipality", "limit": 1},
            timeout=8,
            headers={"User-Agent": "RefugeImmo-POC/0.1"},
        )
        reponse.raise_for_status()
        resultats = reponse.json().get("features") or []
    except (requests.RequestException, ValueError):
        logger.warning("Géocodage impossible pour « %s » (réseau ?)", requete)
        return None
    if not resultats:
        return None
    premier = resultats[0]
    lon, lat = premier["geometry"]["coordinates"]
    cp = premier["properties"].get("postcode")
    return lat, lon, cp


class PipelineRefuge:
    def open_spider(self, spider):
        self.conn = db.connexion()
        self.nb = 0
        self.cache_geo: dict[str, tuple | None] = {}

    def close_spider(self, spider):
        self.conn.commit()
        self.conn.close()
        logger.info("%s : %d annonce(s) enregistrée(s) dans %s",
                    spider.name, self.nb, db.chemin_db())

    def process_item(self, item, spider):
        brut = dict(item)
        brut["source"] = brut.get("source") or spider.name
        brut["id"] = "%s-%s" % (
            brut["source"],
            hashlib.sha1((brut.get("url") or brut.get("titre", "")).encode()).hexdigest()[:12],
        )

        # Géocodage seulement si le site n'a pas déjà fourni la position.
        if brut.get("lat") is None or brut.get("lon") is None:
            cle_geo = f"{brut.get('commune')}|{brut.get('code_postal')}"
            if cle_geo not in self.cache_geo:
                self.cache_geo[cle_geo] = geocoder_commune(
                    brut.get("commune"), brut.get("code_postal"))
            geo_resultat = self.cache_geo[cle_geo]
            if geo_resultat:
                brut["lat"], brut["lon"], cp = geo_resultat
                brut.setdefault("code_postal", cp)
        if brut.get("code_postal") and not brut.get("departement"):
            brut["departement"] = str(brut["code_postal"])[:2]

        db.upsert_annonce(self.conn, preparer_annonce(brut))
        self.nb += 1
        if self.nb % 20 == 0:
            self.conn.commit()
        return item
