# Stratégie de collecte : passer par les agences, pas par les portails

## Le problème

Les grands portails (Leboncoin, SeLoger, Bien'ici…) concentrent les annonces,
mais **interdisent la collecte automatisée** et la bloquent techniquement
(protections anti-robots professionnelles). Les collecter frontalement est à
la fois fragile et juridiquement risqué.

## L'idée : les agences veulent, elles, être trouvées

Derrière presque chaque annonce d'un portail, il y a une **agence** qui
détient le mandat — et cette agence a son **propre site web**. Or un site
d'agence vit de sa visibilité sur Google : il est donc **ouvert aux robots
des moteurs** et, mieux, il publie des **données structurées** faites pour
être lues par une machine. On récupère l'annonce à la source, proprement.

```
   Portail (Leboncoin / Bien'ici)          Site de l'agence
   ┌───────────────────────────┐           ┌────────────────────────┐
   │ 1. QUELLES AGENCES ont     │           │ 3. sitemap.xml → liste │
   │    des biens intéressants  │──────────▶│    des annonces        │
   │    dans ma zone ?          │  nom du   │ 4. schema.org (JSON-LD)│
   │    → decouvrir_agences.py  │  mandat   │    → prix, surface, GPS│
   └───────────────────────────┘           │ 5. score + carte       │
                                            └────────────────────────┘
                2. annuaire d'agences (agences.json)
```

## Pourquoi c'est robuste : schema.org + sitemap

Deux standards du web, présents sur la quasi-totalité des sites d'agences
parce qu'ils servent le référencement Google :

- **`sitemap.xml`** — le plan du site, que l'agence publie *pour* les moteurs.
  Il donne la liste de toutes les pages d'annonces, sans avoir à naviguer.
- **`schema.org` en JSON-LD** — un bloc de données structurées inséré dans
  chaque page d'annonce (`<script type="application/ld+json">`), du type
  `RealEstateListing` / `Product` : prix, surface, nombre de pièces,
  coordonnées GPS, DPE… au format machine, **identique d'un logiciel d'agence
  à l'autre**.

Conséquence : **un seul collecteur générique** (`app/extraction.py` +
`scraper/…/spiders/agence.py`) fonctionne sur des centaines de sites
d'agences, sans code spécifique par site et sans casser au prochain
changement de design. C'est l'inverse du scraping HTML classique, fragile.

À défaut de schema.org, le collecteur se rabat sur les balises OpenGraph
(`og:title`…) puis sur quelques repères dans le texte (prix en €, m²).

## « Déclinaisons locales » des réseaux

Beaucoup d'agences appartiennent à des **réseaux** (Orpi, Century 21, Guy
Hoquet, Nestenn…) : chaque agence locale a son propre site, mais tous
partagent le **même logiciel**, donc la **même structure de données**.
Détecter le réseau, c'est couvrir d'un coup toutes ses agences locales.
L'annuaire (`scraper/refuge_scraper/agences.json`) distingue ces réseaux
nationaux des **spécialistes du bien de caractère / rural** (Patrice Besse,
Groupe Mercure…), plus pertinents pour le public « refuge ».

## En pratique

```bash
# 1. Découvrir les agences actives dans une zone (via l'API Bien'ici)
python scripts/decouvrir_agences.py --lieux "orne, yonne, nievre" --prix-max 300000
#    → complète automatiquement agences.json

# 2. Collecter directement chez ces agences (sitemap + schema.org)
bash scripts/collecter.sh agence                       # tout l'annuaire
bash scripts/collecter.sh agence -a agence="Patrice Besse"
bash scripts/collecter.sh agence -a site=https://une-agence-locale.fr

# Les biens récoltés (avec le nom de l'agence et un lien « voir chez
# l'agence ») apparaissent dans l'application, filtrables par agence.
```

## Garde-fous (voir aussi docs/LEGAL.md)

- **robots.txt respecté d'office** : une page que le site interdit aux robots
  n'est pas visitée ;
- **cadence lente** (1 requête à la fois, ~2,5 s d'attente, ralentissement
  automatique) ;
- **usage personnel** : on lit des données publiques d'annonces à la source ;
  aucune donnée personnelle de vendeur n'est collectée ;
- pour un usage au-delà du personnel, privilégier les **flux officiels** des
  agences/réseaux ou des agrégateurs sous licence.

## Limite honnête du POC

Ce collecteur est **écrit et testé hors-ligne** (l'extracteur schema.org est
couvert par des tests, `tests/test_extraction.py`), mais il n'a pas encore
été lancé sur de vrais sites depuis cet environnement (sans accès internet).
Au premier lancement chez vous, le journal du robot indique précisément, pour
chaque agence, ce qui a été trouvé (sitemap, nombre d'annonces) ou non —
de quoi ajuster l'annuaire en deux minutes.
