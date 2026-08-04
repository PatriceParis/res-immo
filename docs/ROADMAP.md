# Feuille de route

Ce document part de **ce qui limite le produit aujourd'hui**, mesuré sur les
données réelles, et non d'une liste d'envies. Chaque chantier indique pourquoi
il compte pour l'utilisateur, et comment on saura qu'il est réussi.

## Où en est le produit

Mesuré sur la dernière collecte (4 août 2026) :

| Indicateur | Valeur |
|---|---|
| Biens collectés → affichés | 101 → **72** (le reste écarté par les filtres) |
| Avec photo | **89 %** |
| Biens vendus encore listés | **0** |
| Terroirs couverts | 7 (Oise 30, Perche 11, Sarthe 8, Indre-et-Loire 8, Yonne 6, Aisne 6, Loir-et-Cher 3) |
| Agences suivies / productives | 29 / **14** |
| Score médian · maximum | 34 · **57** |
| Biens « bon potentiel » (≥ 55) | 4 |

La chaîne fonctionne de bout en bout : découverte d'agences (OpenStreetMap) →
collecte navigateur → filtres qualité → score → publication, le tout
automatisé (collecte hebdomadaire, découverte mensuelle).

## Les trois choses qui limitent aujourd'hui

**1. Des points de score inaccessibles faute de données.**
Le barème est sain, mais trois piliers n'exploitent qu'une fraction de leurs
points parce que l'information n'est pas captée :

| Pilier | Exploité | Cause |
|---|---|---|
| Autonomie en eau | **3 %** | puits/source quasi jamais écrits dans les annonces |
| Autonomie alimentaire | **11 %** | terrains souvent petits ; aménagements rarement décrits |
| Énergie | **23 %** | **le DPE n'est jamais extrait** (0/72) |

**2. Aucune notion de temps.** Les annonces n'ont ni date d'apparition ni date
de dernière vue. Impossible de dire « nouveau cette semaine », de repérer une
annonce disparue, ou de prévenir l'utilisateur — alors que c'est précisément
ce qu'il attend d'un outil de veille.

**3. Un tiers des agences ne rend rien.** 14 agences sur 29 produisent des
biens. Les autres ouvrent leurs pages mais l'extraction n'y trouve ni prix ni
surface : sites rendus en JavaScript ou structurés autrement.

---

## Jalon 1 — Rendre exploitable ce qui est déjà sous la main

*Objectif : plus de biens correctement notés, sans collecter davantage.*

### 1.1 Extraire le DPE (impact le plus direct)
Le DPE est obligatoire dans toute annonce. Il est **présent dans 28 % des
pages** collectées (« Date de réalisation du DPE », « classe énergie »), mais
la lettre A–G est portée par une image ou un composant graphique : la lecture
du texte seul la manque. À traiter par : lecture de l'attribut `alt` et des
classes CSS de l'étiquette (`dpe-d`, `energy-class-D`), puis des champs
schema.org `energyEfficiencyScaleMin/Max`.
*Réussi si* : DPE renseigné pour ≥ 25 % des biens (aujourd'hui 0 %), ce qui
débloque jusqu'à 5 points d'Énergie sur un bien sur quatre.

### 1.2 Fiabiliser l'altitude
Renseignée pour 53 % des biens seulement — l'appel à l'API d'élévation échoue
une fois sur deux, sans repli. Ajouter une seconde source et un réessai.
*Réussi si* : ≥ 90 % des biens ont une altitude.

### 1.3 Adapter la collecte aux sites récalcitrants
Morvan Immobilier, Agence Boilot et consorts ouvrent leurs pages mais ne
livrent rien. Attendre le rendu JavaScript (`networkidle`) et, si nécessaire,
un sélecteur par site dans la configuration d'agence.
*Réussi si* : au moins 5 des 15 agences muettes deviennent productives.

---

## Jalon 2 — Intégrer les nouvelles annonces en continu

*C'est le cœur de la valeur pour l'utilisateur : être prévenu, pas surveiller.*

### 2.1 Donner une mémoire aux annonces
Ajouter `vue_le` (première apparition) et `revue_le` (dernière collecte où
l'annonce était présente). Rien d'autre ne peut être construit sans cela.

### 2.2 Ce que la mémoire permet, dans l'ordre
- **Badge « nouveau »** et tri par nouveauté — l'utilisateur voit d'un coup
  d'œil ce qui a bougé depuis sa dernière visite ;
- **Annonces disparues** : une annonce absente de deux collectes successives
  est retirée. Aujourd'hui, seul le mot « Vendu » sur la page permet de le
  savoir — or beaucoup d'agences retirent l'annonce sans le dire ;
- **Historique de prix** : une baisse de prix est un signal d'achat fort, et
  c'est une donnée qu'aucun portail ne montre clairement ;
- **Alerte** : courriel (ou flux RSS) quand un bien dépassant un seuil de
  score apparaît dans les terroirs choisis.

### 2.3 Collecte incrémentale
Les sitemaps exposent une date de dernière modification (`lastmod`). En ne
revisitant que les pages modifiées, le temps de collecte s'effondre — donc on
peut suivre beaucoup plus d'agences dans le même budget de 40 minutes.
*Réussi si* : temps de collecte divisé par deux à couverture égale.

### 2.4 Dédoublonner entre agences
Un même bien peut être en mandat chez deux agences. Le rapprochement
(commune + prix + surface, à tolérance) évite de le présenter deux fois.

---

## Jalon 3 — Affiner la pertinence

### 3.1 Le risque à la parcelle, pas à la commune
Géorisques ne dit aujourd'hui que « ce risque est documenté sur la commune » —
d'où une pénalité volontairement symbolique (voir `docs/CRITERES.md`).
Les zonages TRI/AZI permettent de savoir si **l'adresse** est en zone
inondable : c'est la différence entre un avertissement utile et un bruit.

### 3.2 Le prix relatif au marché local (données DVF)
Un bien à 150 000 € n'a pas le même intérêt selon qu'il est 20 % au-dessus ou
30 % en dessous du prix des ventes récentes de sa commune. Les données DVF
(ventes réelles, open data) permettent de signaler les vraies opportunités.

### 3.3 Assumer le pilier Eau
À 3 % d'exploitation, deux voies possibles :
- **l'accepter** — un puits se vérifie en visite, et le barème le dit ; ou
- **l'enrichir** par open data (forages déclarés en Banque du Sous-Sol,
  profondeur des nappes) : on noterait alors le *potentiel* de la commune
  plutôt que l'équipement du bien.
Le choix est à trancher avec l'usage réel ; la seconde voie change la nature
du critère et mérite d'être explicite auprès de l'utilisateur.

---

## Jalon 4 — Le produit autour des annonces

### 4.1 Rendre la mise en relation réelle
Le bouton « Recevoir les photos & être recontacté » n'a pas encore de
traitement derrière. C'est le modèle économique : gratuit pour l'acheteur,
facturé à l'agence sur contact qualifié. Il faut un formulaire, un envoi et
une trace.

### 4.2 Comparer et emporter
Comparateur de deux ou trois biens côte à côte, et fiche imprimable à
emporter en visite — avec les points à vérifier sur place (le puits, l'état
de la cave, l'humidité du troglodyte).

---

## Couverture géographique

Sept zones couvertes. À étendre par la découverte mensuelle, déjà automatique :
Thiérache, Puisaye, Pays d'Othe, Morvan (dès que les sites JavaScript seront
lisibles), et le reste de la vallée du Loir.

Le périmètre reste volontairement **≤ 350 km de Paris**, Île-de-France exclue :
un refuge à six heures de route ne remplit pas sa fonction. Des biens
remarquables existent en Périgord ou dans le Lot — le barème les note très
bien sur le fond — mais ils sortent de la promesse du produit.

## Ce qui n'est pas prévu, et pourquoi

- **Collecter les portails nationaux** (Leboncoin, SeLoger) : ils bloquent la
  collecte automatisée. La voie retenue — les sites d'agences — fonctionne et
  reste correcte vis-à-vis des éditeurs.
- **Élargir le périmètre à toute la France** : cela viderait le score de son
  sens (le pilier Situation deviendrait décoratif) et trahirait le besoin
  d'origine.
