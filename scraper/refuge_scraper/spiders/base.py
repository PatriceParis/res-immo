"""Socle commun des robots de collecte.

Les sites immobiliers changent régulièrement leur mise en page : plutôt que de
dépendre de sélecteurs CSS fragiles, la page de détail est analysée de façon
heuristique (titre = h1, prix = premier montant en euros, surfaces repérées
par « m² »…). Chaque robot ne définit donc que : ses URL de départ, le motif
des liens d'annonces et, s'il le souhaite, des sélecteurs plus précis.
"""

from __future__ import annotations

import re

import scrapy

from ..items import AnnonceItem

RE_PRIX = re.compile(r"(\d[\d\s  .]{3,})\s*€")
RE_SURFACE = re.compile(r"(\d{2,4})\s*m[²2]\b", re.IGNORECASE)
RE_TERRAIN = re.compile(
    r"(?:terrain|parcelle|jardin)\D{0,30}?(\d[\d\s  ]{2,})\s*m[²2]",
    re.IGNORECASE,
)
RE_TERRAIN_HA = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:ha|hectares?)\b", re.IGNORECASE)
RE_PIECES = re.compile(r"(\d{1,2})\s*pi[eè]ces?", re.IGNORECASE)
RE_COMMUNE = re.compile(r"([A-ZÀ-Ü][\w''\- ]{2,40})\s*\((\d{5})\)")


def _nombre(texte: str | None) -> int | None:
    if not texte:
        return None
    chiffres = re.sub(r"[^\d]", "", texte)
    return int(chiffres) if chiffres else None


class SpiderAnnonces(scrapy.Spider):
    """Classe de base : à spécialiser avec start_urls et motif_lien_annonce."""

    motif_lien_annonce = r"/annonce"
    motif_page_suivante = "a[rel=next]::attr(href), .pagination a.next::attr(href)"
    type_bien = "maison"

    def parse(self, response):
        """Page de liste : suit chaque lien d'annonce, puis la page suivante."""
        vus = set()
        for href in response.css("a::attr(href)").getall():
            if re.search(self.motif_lien_annonce, href) and href not in vus:
                vus.add(href)
                yield response.follow(href, callback=self.parse_annonce)
        for suivant in response.css(self.motif_page_suivante).getall()[:1]:
            yield response.follow(suivant, callback=self.parse)

    # ------------------------------------------------------------------
    # Analyse heuristique d'une page de détail
    # ------------------------------------------------------------------
    def parse_annonce(self, response):
        texte = " ".join(
            t.strip() for t in response.css("body *:not(script):not(style)::text").getall()
            if t.strip()
        )
        titre = (response.css("h1::text").get() or "").strip() or response.css(
            "title::text").get("").strip()

        description = " ".join(
            t.strip() for t in response.css(self.selecteur_description()).getall()
            if t.strip()
        ) or texte[:1500]

        prix_texte = RE_PRIX.search(texte)
        surface = RE_SURFACE.search(f"{titre} {texte}")
        terrain = RE_TERRAIN.search(texte)
        terrain_ha = RE_TERRAIN_HA.search(texte) if not terrain else None
        pieces = RE_PIECES.search(f"{titre} {texte}")
        commune = RE_COMMUNE.search(f"{titre} — {texte[:800]}")

        item = AnnonceItem(
            source=self.name,
            url=response.url,
            titre=titre[:200] or "Annonce sans titre",
            description=description[:4000],
            prix=_nombre(prix_texte.group(1)) if prix_texte else None,
            surface_m2=_nombre(surface.group(1)) if surface else None,
            terrain_m2=(
                _nombre(terrain.group(1)) if terrain
                else int(float(terrain_ha.group(1).replace(",", ".")) * 10_000)
                if terrain_ha else None
            ),
            pieces=_nombre(pieces.group(1)) if pieces else None,
            type_bien=self.type_bien,
            commune=commune.group(1).strip() if commune else None,
            code_postal=commune.group(2) if commune else None,
        )
        # On ne garde que les pages qui ressemblent vraiment à une annonce.
        if item["prix"] or item["surface_m2"]:
            yield item

    def selecteur_description(self) -> str:
        return (
            ".item-description ::text, .description ::text, "
            "[class*=description] ::text, article p::text"
        )
