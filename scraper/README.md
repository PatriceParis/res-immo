# Collecte des annonces (robots Scrapy)

## Pourquoi il n'y a pas (encore) SeLoger ni Leboncoin

Les grands portails (SeLoger, Leboncoin, Bien'ici, Logic-Immo…) :

1. **interdisent la collecte automatisée dans leurs conditions d'utilisation** ;
2. utilisent des protections anti-robots professionnelles (DataDome…) qui
   bloquent de toute façon les collecteurs simples.

Contourner ces protections serait à la fois fragile et juridiquement risqué.
Le POC collecte donc des **sites d'annonces entre particuliers**, moins
verrouillés, et le reste de l'application (score, filtres, carte) est
démontré avec un **jeu de données fictif réaliste** (`data/annonces_demo.json`).

Pour une version production, les pistes propres sont : les **flux
partenaires** des portails, les APIs d'agrégateurs (Melo, Yanport…) ou des
partenariats directs avec des agences. Voir `docs/LEGAL.md`.

## Robots disponibles

| Robot | Site | Commande |
|-------|------|----------|
| `pap` | pap.fr | `bash scripts/collecter.sh pap` |
| `iep` | immo-entre-particuliers.com | `bash scripts/collecter.sh iep` |

Les annonces collectées sont géocodées (Base Adresse Nationale), notées par
le moteur de score, puis ajoutées à la même base que l'interface web —
rechargez simplement la page pour les voir.

## Garde-fous intégrés

- `ROBOTSTXT_OBEY = True` : ce que le site interdit n'est pas visité ;
- 1 requête à la fois, ~2,5 s d'attente entre chaque, ralentissement
  automatique si le site répond lentement ;
- User-Agent honnête (`RefugeImmo-POC`), pas de faux navigateur.

## Si un robot ne trouve plus rien

Les sites changent régulièrement leur mise en page. Les robots utilisent une
analyse « heuristique » (titre, prix en €, surfaces en m²) qui résiste bien
aux petits changements, mais les **URL de départ** peuvent expirer : faites
une recherche sur le site concerné, copiez l'adresse de la page de résultats
et remplacez `start_urls` dans le fichier du robot.
