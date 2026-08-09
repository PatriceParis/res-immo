# Référencement — audit, mots-clés, et ce qui a été fait

Mesures du 9 août 2026, sur un catalogue de 1 361 entrées dont **993 réellement
servies** par le site.

---

## 1. Audit de départ

Le diagnostic tient en une phrase : **il n'y avait rien à indexer.**

Refuge Immo est une page unique rendue en JavaScript. Un robot qui demande la
page reçoit un `<title>`, deux `<link>` et des conteneurs vides que seul le
navigateur remplit.

| Point | État avant | Conséquence |
|---|---|---|
| URL par annonce | **aucune** — tout se joue en fenêtre modale | 993 biens, une seule adresse indexable |
| URL par terroir | **aucune** | aucune page ne peut répondre à « maison à vendre en Normandie » |
| `robots.txt` | absent | aucune consigne, aucun plan de site annoncé |
| `sitemap.xml` | absent | découverte laissée au hasard des liens — or il n'y en avait aucun |
| `llms.txt` | absent | les modèles reconstituent le site de mémoire, donc de travers |
| `<meta name="description">` | absente | Google fabrique lui-même l'extrait affiché |
| `<link rel="canonical">` | absente | duplications d'adresses non arbitrées |
| OpenGraph / Twitter | absents | un partage n'affiche ni titre ni image |
| Données structurées | **aucune** | aucun prix, aucune surface, aucune position lisibles par machine |
| Liens internes dans le HTML servi | **zéro** | un robot arrive sur l'accueil et n'a nulle part où aller |

### Le point décisif : les robots d'IA n'exécutent pas JavaScript

Google sait rendre une page JavaScript, au prix d'un second passage et d'un
délai. **GPTBot, ClaudeBot, PerplexityBot, CCBot et consorts ne le font pas :**
ils lisent le HTML tel qu'il arrive. Pour eux, le site était littéralement
vide.

C'est l'enjeu principal, et pas un enjeu secondaire : un acheteur qui se
demande « où acheter une maison résiliente près de Paris » pose de plus en plus
la question à un assistant, pas à un moteur. Sur cette requête-là, Refuge Immo
a quelque chose d'unique à dire — et n'était pas citable.

---

## 2. Recherche de mots-clés

**Ce que cette recherche est, et ce qu'elle n'est pas.** Aucun outil de volume
(Semrush, Ahrefs, Google Keyword Planner) n'est accessible depuis
l'environnement de développement, qui n'a pas le réseau. Les intentions
ci-dessous sont déduites du **catalogue réel** et des conventions de recherche
immobilière française. **Les volumes ne sont pas vérifiés** — ils restent à
confirmer, et c'est la première chose à faire avec un outil payant.

### Trois familles d'intention

**A. Recherche immobilière classique** — gros volume, concurrence écrasante
(SeLoger, Leboncoin, Bien'ici). On ne gagnera pas « maison à vendre Normandie »
en frontal. On peut gagner la longue traîne :

| Intention | Notre page | Matière disponible |
|---|---|---|
| `maison à vendre + {commune}` | fiches d'annonce | 430 communes couvertes |
| `longère / corps de ferme / moulin à vendre` | fiches | types rares, peu disputés |
| `maison avec puits + terrain` | à créer | 31 biens avec source, 51 avec eau à proximité |
| `maison chauffage au bois campagne` | à créer | 325 biens |
| `maison avec dépendances près de Paris` | à créer | 288 biens |

**B. Recherche de projet** — c'est notre terrain, et il est peu occupé :

| Intention | Notre page |
|---|---|
| `où s'installer face au réchauffement climatique` | pages de terroir |
| `région la moins exposée au changement climatique France` | page de terroir + classement |
| `acheter maison résiliente climat` | accueil + terroirs |
| `quitter Paris s'installer campagne 2 heures` | terroirs (140 biens à moins de 2 h) |
| `maison zone non inondable {région}` | terroirs (part hors inondation affichée) |

**C. Interrogation d'assistant** — formulée en question, sans mot-clé :

> « Quelles régions à moins de 3 h de Paris sont les moins exposées à la
> sécheresse ? » · « Une maison en Normandie ou en Bourgogne pour se prémunir
> du climat ? » · « Combien coûte une maison avec un puits dans le Perche ? »

Ces questions n'ont pas de page dédiée sur le web français. C'est là que
l'avantage est le plus net, et c'est ce que visent les paragraphes citables et
le `llms.txt`.

### Six pages de terroir, les seules à porter un sujet

| Terroir | Biens | Communes | Prix médian | Altitude médiane |
|---|---:|---:|---:|---:|
| Normandie | 318 | 102 | 294 500 € | 50 m |
| Grand Est | 224 | 108 | 181 900 € | 215 m |
| Centre-Val de Loire | 216 | 100 | 225 000 € | 127 m |
| Hauts-de-France | 147 | 72 | 224 900 € | 54 m |
| Bourgogne-Franche-Comté | 72 | 39 | 260 000 € | 221 m |
| Pays de la Loire | 16 | 9 | 134 000 € | 65 m |

Personne ne tape « res-immo ». Ces six pages sont les seules qui puissent
répondre à une requête réelle, parce qu'elles portent un sujet et non un bien.

---

## 3. Ce qui a été fait

### Pages rendues par le serveur (`app/pages.py`)

- **`/annonce/{descriptif}/{id}`** — une page par bien, ~993 pages.
  Adresse en deux segments : nos identifiants contiennent eux-mêmes des
  tirets (`immo-ray-com-a678b12`), et les découper au dernier tiret renvoyait
  un identifiant inexistant — toutes les fiches répondaient 410.
- **`/terroir/{slug}`** — six pages, les cibles principales.
- Redirection **301** vers l'adresse canonique si le descriptif a changé
  (le titre évolue au fil des collectes : prix révisé, surface corrigée).
- **410 Gone** et non 404 pour un bien retiré : le moteur le sort de son index
  sans attendre, et sans compter l'adresse comme une erreur de notre part.

### Ce que ces pages publient — et ne publient pas

Nos annonces viennent des sites d'agences. Recopier leur texte de vente
(3 000 signes en moyenne) serait du contenu dupliqué : pénalisant au
référencement, et discutable vis-à-vis des agences.

Les fiches ne portent donc que **des faits** — prix, surface, pièces, terrain,
commune, DPE, qui n'appartiennent à personne — et **notre analyse** : score de
résilience, altitude, risques Géorisques, distance à la centrale nucléaire,
temps de route et gare. Un test l'impose (`test_la_prose_de_l_agence_n_est_
jamais_republiee`). Chaque fiche renvoie visiblement vers l'annonce d'origine.

### Indexation par les IA

- **`/llms.txt`** (convention llmstxt.org) : ce qu'est le site, la méthode de
  notation pilier par pilier, les sources officielles, et **les limites** —
  prix demandés et non prix de vente, note comparative et non expertise,
  risques communaux et non parcellaires, notes réellement observées de 14 à 62
  sur 100. Son intérêt n'est pas d'être « lu par l'IA » comme un sésame : c'est
  de fournir, en un seul endroit, la version que nous jugeons exacte plutôt que
  d'en laisser un modèle reconstituer une de travers.
- **`/robots.txt`** nomme **dix-huit robots d'IA un par un** (GPTBot,
  OAI-SearchBot, ClaudeBot, Claude-SearchBot, PerplexityBot, Google-Extended,
  CCBot, Applebot-Extended, MistralAI-User…). Les nommer n'est pas cosmétique :
  plusieurs n'explorent que si une règle les vise.
- **Paragraphes citables** : chaque page de terroir ouvre sur un passage
  autonome de 140 à 170 mots qui répond dès la première phrase et porte des
  chiffres vérifiables. C'est le format qu'un assistant extrait — mesuré à
  147 mots sur la Normandie.
- **Titres en questions** : « Combien de biens et à quel prix ? », « Comment la
  note de résilience est-elle calculée ? »

### Données structurées

`RealEstateListing` avec `Offer` (prix, devise, disponibilité),
`SingleFamilyResidence` (surface, pièces, terrain, `GeoCoordinates`,
`PostalAddress`), `BreadcrumbList`, `ItemList`, `Organization`, et `WebSite`
avec `SearchAction` sur l'accueil. Le vendeur est déclaré comme
`RealEstateAgent` distinct : nous référençons, nous ne vendons pas, et le
balisage doit le dire.

*Note :* `FAQPage` n'a délibérément pas été utilisé — Google en a retiré les
résultats enrichis en mai 2026. Les questions-réponses sont en HTML sémantique
ordinaire, que les modèles lisent aussi bien.

### Le reste

- `<head>` complet sur l'accueil : description, canonique, OpenGraph, Twitter.
- **Pied de page avec les six liens de terroir dans le HTML servi.** Sans lui,
  un robot arrive sur l'accueil et n'a aucun lien à suivre : c'est le seul
  chemin de découverte du site. Il sert aussi aux visiteurs — la navigation par
  région manquait.
- `sitemap.xml` engendré depuis le catalogue : 1 000 adresses.
- Adresses absolues déduites de la requête, jamais écrites en dur : sur un
  déploiement de prévisualisation Vercel, une canonique en dur serait fausse,
  ce qui est pire que pas de canonique.

### Une faille corrigée en chemin

Le test d'échappement a révélé une **injection de script** : `json.dumps`
protège les guillemets mais ni `<` ni `/`. Une commune nommée
`Bellême"><script>…` refermait la balise `<script type="application/ld+json">`
et tout ce qui suivait était exécuté comme du HTML. Nos données viennent de
sites tiers, c'est-à-dire de nulle part. Les trois caractères sont désormais
échappés en séquences unicode : le JSON reste identique à la relecture, et
plus rien ne sort de la balise.

---

## 4. Comment saurons-nous que cela a échoué ?

Chaque mesure doit pouvoir être démentie, sinon ce ne sont que des vœux.

| Attendu | Délai | Signe d'échec |
|---|---|---|
| Pages indexées | 4–8 semaines | Search Console reste sous 100 pages sur 1 000 |
| Premières impressions sur les terroirs | 6–10 semaines | zéro impression sur « maison résiliente » et voisins |
| Citation par un assistant | 2–4 mois | interroger ChatGPT/Perplexity sur « maison résiliente près de Paris » ne renvoie jamais le site |
| Extraits enrichis (prix, surface) | 4–8 semaines | l'outil de test des résultats enrichis de Google signale des erreurs |

**À faire vous-même, et que je ne peux pas faire d'ici :** déclarer le site à
la Google Search Console et à Bing Webmaster Tools, y soumettre le sitemap, et
confirmer les volumes de recherche avec un outil payant. Sans Search Console,
aucune de ces mesures n'est observable.

---

## 5. Ce qui reste à faire

1. **Un nom de domaine.** `res-immo.vercel.app` est un sous-domaine partagé :
   l'autorité se construit mal dessus, et le nom ne dit rien. C'est le premier
   investissement à faire, avant tout le reste.
2. **Pages thématiques** sur les atouts, où la matière existe déjà : maison
   avec puits ou source (82 biens), chauffage au bois (325), dépendances (288),
   bâti en pierre (112), à moins de 2 h de Paris (140).
3. **Pages par commune** pour les 12 communes les mieux fournies (Le Havre 38,
   Caen 23, Tours 20, Nancy 19…), en veillant à ne pas fabriquer de pages
   maigres sur les communes à un seul bien.
4. **Contenu éditorial** : c'est ce qui manquera le plus longtemps. Un moteur
   comme un modèle privilégient les pages qui expliquent. « Comment choisir une
   région face au climat », « lire un état des risques », « pourquoi l'altitude
   compte ».
5. **Vitesse** : Leaflet et ses tuiles pèsent lourd sur l'accueil. Les pages
   serveur, elles, sont en HTML nu avec une feuille de style incorporée — c'est
   volontaire, et c'est ce que verront les robots.
