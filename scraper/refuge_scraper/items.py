"""Structure d'une annonce collectée, avant enrichissement."""

import scrapy


class AnnonceItem(scrapy.Item):
    source = scrapy.Field()
    url = scrapy.Field()
    titre = scrapy.Field()
    description = scrapy.Field()
    prix = scrapy.Field()            # entier, en euros
    surface_m2 = scrapy.Field()
    terrain_m2 = scrapy.Field()
    pieces = scrapy.Field()
    type_bien = scrapy.Field()
    commune = scrapy.Field()
    code_postal = scrapy.Field()
    dpe = scrapy.Field()             # classe énergie A…G si fournie par le site
    lat = scrapy.Field()             # position si fournie par le site
    lon = scrapy.Field()
    agence = scrapy.Field()          # nom de l'agence détentrice du mandat
    agence_url = scrapy.Field()      # site de l'agence (pour « voir chez l'agence »)
