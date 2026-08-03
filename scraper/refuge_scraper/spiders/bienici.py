"""Robot Bien'ici (bienici.com) — ajouté à la demande, à utiliser avec discernement.

Bien'ici est le portail du consortium des professionnels de l'immobilier.
Plutôt que d'analyser des pages HTML (générées en JavaScript), ce robot
interroge la même API JSON que le site lui-même :

    1. `res.bienici.com/suggest.json` traduit un nom de lieu (« yonne »,
       « perche »…) en identifiants de zones internes ;
    2. `www.bienici.com/realEstateAds.json` renvoie les annonces (prix,
       surfaces, description, position GPS approximative, DPE…).

⚠️ Précautions :
- usage strictement personnel — les CGU des grands portails restreignent la
  collecte automatisée (lire docs/LEGAL.md avant de lancer) ;
- le robots.txt du site est respecté d'office : si Bien'ici interdit ces
  adresses aux robots, rien ne sera collecté (message dans le journal) ;
- cadence lente héritée des réglages communs (1 requête / ~2,5 s) ;
- écrit hors ligne, non testé en conditions réelles : si le format de l'API
  change, ouvrez le journal — le robot explique ce qu'il n'a pas trouvé.

Exemples :
    bash scripts/collecter.sh bienici
    bash scripts/collecter.sh bienici -a "lieux=orne, yonne" -a prix_max=300000 -a pages=3
"""

from __future__ import annotations

import json
import urllib.parse

import scrapy

from ..items import AnnonceItem

URL_SUGGEST = "https://res.bienici.com/suggest.json?q={q}"
URL_ANNONCES = "https://www.bienici.com/realEstateAds.json?filters={filtres}"

# Départements cibles du POC (rayon ~3 h autour de Paris).
LIEUX_DEFAUT = (
    "seine-et-marne, essonne, yvelines, val-d'oise, oise, aisne, marne, aube, "
    "yonne, nievre, cher, loiret, loir-et-cher, eure-et-loir, eure, orne"
)


class SpiderBienici(scrapy.Spider):
    name = "bienici"
    allowed_domains = ["bienici.com", "www.bienici.com", "res.bienici.com"]
    type_bien = "maison"

    def __init__(self, lieux: str = LIEUX_DEFAUT, prix_max=None, pages="5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lieux = [l.strip() for l in lieux.split(",") if l.strip()]
        self.prix_max = int(prix_max) if prix_max else None
        self.pages = max(1, int(pages))

    # ------------------------------------------------------------------
    # 1. lieu → identifiants de zone
    # ------------------------------------------------------------------
    def start_requests(self):
        for lieu in self.lieux:
            yield scrapy.Request(
                URL_SUGGEST.format(q=urllib.parse.quote(lieu)),
                callback=self.parse_suggestion,
                cb_kwargs={"lieu": lieu},
            )

    def parse_suggestion(self, response, lieu):
        try:
            data = json.loads(response.text)
        except ValueError:
            self.logger.warning("Réponse illisible de suggest.json pour « %s »", lieu)
            return
        candidats = data if isinstance(data, list) else data.get("suggestions") or []
        zone_ids: list = []
        for candidat in candidats[:1]:  # meilleure suggestion uniquement
            if isinstance(candidat, dict):
                zone_ids += candidat.get("zoneIds") or []
                if candidat.get("zoneId"):
                    zone_ids.append(candidat["zoneId"])
        if not zone_ids:
            self.logger.warning("Aucune zone trouvée pour « %s » — vérifiez l'orthographe", lieu)
            return
        yield self._requete_annonces(zone_ids, page=0, lieu=lieu)

    # ------------------------------------------------------------------
    # 2. zones → annonces (paginé)
    # ------------------------------------------------------------------
    def _requete_annonces(self, zone_ids, page, lieu):
        filtres = {
            "size": 24,
            "from": page * 24,
            "filterType": "buy",
            "propertyType": ["house"],
            "onTheMarket": [True],
            "sortBy": "publicationDate",
            "sortOrder": "desc",
            "zoneIdsByTypes": {"zoneIds": zone_ids},
        }
        if self.prix_max:
            filtres["maxPrice"] = self.prix_max
        url = URL_ANNONCES.format(filtres=urllib.parse.quote(json.dumps(filtres)))
        return scrapy.Request(
            url,
            callback=self.parse_annonces,
            cb_kwargs={"zone_ids": zone_ids, "page": page, "lieu": lieu},
        )

    def parse_annonces(self, response, zone_ids, page, lieu):
        try:
            data = json.loads(response.text)
        except ValueError:
            self.logger.warning("Réponse illisible de realEstateAds.json (%s)", lieu)
            return
        annonces = data.get("realEstateAds") or []
        if not annonces and page == 0:
            self.logger.info("Aucune annonce renvoyée pour « %s » (zones %s)", lieu, zone_ids)
        for ad in annonces:
            item = self._vers_item(ad)
            if item:
                yield item
        if annonces and page + 1 < self.pages:
            yield self._requete_annonces(zone_ids, page + 1, lieu)

    # ------------------------------------------------------------------
    # 3. annonce JSON → item interne
    # ------------------------------------------------------------------
    def _vers_item(self, ad: dict) -> AnnonceItem | None:
        if not isinstance(ad, dict) or not (ad.get("price") or ad.get("surfaceArea")):
            return None
        position = (ad.get("blurInfo") or {}).get("position") or ad.get("position") or {}
        identifiant = ad.get("id")
        ville = ad.get("city") or ""
        titre = ad.get("title") or " ".join(filter(None, [
            "Maison",
            f"{ad.get('roomsQuantity')} pièces" if ad.get("roomsQuantity") else None,
            f"{ad.get('surfaceArea'):.0f} m²" if ad.get("surfaceArea") else None,
            f"— {ville}" if ville else None,
        ]))
        return AnnonceItem(
            source="bienici",
            # Lien best-effort : le site redirige /annonce/<id> vers la page complète.
            url=f"https://www.bienici.com/annonce/{identifiant}" if identifiant else "",
            titre=str(titre)[:200],
            description=str(ad.get("description") or "")[:4000],
            prix=int(ad["price"]) if ad.get("price") else None,
            surface_m2=ad.get("surfaceArea"),
            terrain_m2=ad.get("landSurfaceArea") or ad.get("gardenSurfaceArea"),
            pieces=ad.get("roomsQuantity"),
            type_bien="maison",
            commune=ville or None,
            code_postal=ad.get("postalCode"),
            dpe=(ad.get("energyClassification") or None),
            lat=position.get("lat"),
            lon=position.get("lon"),
        )
