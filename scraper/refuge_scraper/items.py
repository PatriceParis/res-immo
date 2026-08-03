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
