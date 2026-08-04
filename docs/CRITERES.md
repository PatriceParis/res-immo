# Le score de résilience — barème détaillé

## Philosophie

Le score répond à une question simple : **« si la vie devient plus difficile
(canicules, pénuries, coupures, crues…), cette maison aide-t-elle ses
occupants à tenir ? »** Il additionne six piliers, notés sur 100 au total.
Un bien parfait n'existe pas ; au-delà de 70, on tient un candidat sérieux.

Le score est un **outil de tri, pas une vérité** : il repère les annonces qui
méritent une visite, il ne remplace ni le diagnostic ni le notaire.

## Les 6 piliers

### 💧 Autonomie en eau — 12 points
| Critère | Points | Pourquoi |
|---|---|---|
| Puits ou forage | 6 | eau disponible même si le réseau flanche ; le critère le plus difficile à ajouter après coup |
| Récupération d'eau de pluie (cuve, citerne) | 3 | arrosage, appoint, réserve |
| Cours d'eau, mare ou étang à proximité | 3 | ressource de secours (à filtrer), fraîcheur |

### 🕳️ Abri & stockage — 18 points
| Critère | Points | Pourquoi |
|---|---|---|
| **Cave ou sous-sol** | **9** | stockage longue durée au frais (récoltes, conserves), refuge en canicule ou tempête — l'atout signature de l'application |
| Grange, dépendances | 5 | stockage de matériel, bois, extension possible |
| Atelier ou garage | 3 | réparer soi-même |

### 🔥 Énergie — 17 points
| Critère | Points | Pourquoi |
|---|---|---|
| Chauffage au bois (poêle, insert, chaudière) | 7 | chauffer sans réseau ni fioul |
| Panneaux solaires | 5 | électricité en autonomie partielle |
| Bonne isolation : DPE A/B | 5 (C : 3) | besoin d'énergie réduit à la source |

### 🥕 Autonomie alimentaire — 18 points

**La question : « ce bien permet-il de produire une partie de sa nourriture ? »**
On additionne deux choses : **l'espace** (un terrain, pour cultiver ou élever)
**ET** les **aménagements déjà là** (potager, poulailler…). Ainsi un petit
terrain bien équipé peut marquer autant qu'un grand terrain nu. Total plafonné
à 18.

| Critère | Points | Pourquoi |
|---|---|---|
| Terrain ≥ 1 ha | 8 | de l'espace pour cultiver / élever |
| Terrain ≥ 5 000 m² | 6 | |
| Terrain ≥ 2 500 m² | 4 | |
| Terrain ≥ 1 000 m² | 2 | |
| Verger ou potager déjà en place | +4 | production immédiate |
| Prairie / pâture | +3 | élevage, foin |
| Poulailler | +2 | œufs, volaille |
| Vigne | +2 | |
| Ruches | +2 | miel, pollinisation |
| Serre | +2 | cultures prolongées |

*Exemple : une maison sans grand terrain mais avec potager (+4), poulailler (+2)
et ruches (+2) obtient 8/18 — elle est déjà partiellement nourricière. Une
propriété d'un hectare nu obtient 8/18.*

### 🌊 Exposition aux risques — 15 points (on part de 15, on retire)
| Risque | Points retirés |
|---|---|
| Zone inondable | −8 |
| Sols argileux (retrait-gonflement) fort | −3 (moyen : −1) |
| Site industriel Seveso à < 5 km | −4 (< 10 km : −2) |
| Centrale nucléaire à < 10 km | −5 (< 20 km : −3) |
| Zone sensible aux feux de forêt | −2 |

La distance aux centrales est calculée automatiquement (liste des 18 CNPE
embarquée). Les autres risques sont renseignés par l'API officielle de l'État
**Géorisques**. L'enrichissement tourne **automatiquement à chaque collecte**
(étape « Enrichir les risques officiels » du workflow), et peut se relancer à la
main : `python scripts/enrichir_risques.py`.

#### ⚠️ Portée des données Géorisques : commune ≠ bien

Le point d'accès utilisé indique qu'un risque est **documenté sur la commune**,
pas que *ce* bien y est exposé. Mesuré sur nos annonces réelles :

| Risque « présent » | Part des communes |
|---|---|
| Zonage sismique | **100 %** |
| Potentiel radon | **100 %** |
| Inondation | 80 % |
| Installation classée (ICPE) | 75 % |

Toute commune française a un zonage sismique et un potentiel radon ; presque
toutes ont une rivière. Retirer 8 points d'inondation sur cette base
pénaliserait 80 % des biens **à tort** — et ferait passer une ferme perchée du
Perche pour une maison les pieds dans l'eau.

Ces signaux sont donc traités comme des **points de vigilance à vérifier à
l'adresse** (affichés sous la fiche), avec une pénalité symbolique (−2 pour
l'inondation communale, −1 pour les feux). La pénalité pleine (−8) reste
réservée à un bien **réellement situé** en zone inondable. L'état des risques
étant obligatoire à la vente, l'acheteur aura la réponse exacte au moment de
l'offre.

### 🚗 Situation & accès — 20 points
| Critère | Points |
|---|---|
| Altitude ≥ 200 m | 3 (≥ 100 m : 2) |
| Densité < 30 hab/km² | 7 (< 80 : 5 ; < 300 : 2) |
| Paris à ≤ 1 h 30 de route | 6 (≤ 2 h 30 : 4 ; ≤ 3 h 30 : 2) |
| Hameau / à l'écart / pleine campagne | 2 |
| **Gare à ≤ 15 km, Paris en ≤ 1 h** | **4** (≤ 1 h 30 : 3 ; ≤ 2 h : 2) |
| Gare entre 15 et 25 km | 1 |

Le POC cible une **base de repli atteignable** : un refuge à 6 h de route ne
sert à rien en cas de départ précipité — d'où des points pour la proximité,
alors que la faible densité joue en sens inverse. C'est cet équilibre qui
fait ressortir le Perche, la Puisaye ou le Pays d'Othe.

#### 🚆 Pourquoi le train compte

La voiture suppose du **carburant**, un véhicule en état et des routes
praticables. Une commune desservie par une gare reste **atteignable sans
voiture** — en cas de pénurie, de prix de l'énergie qui s'envole, ou pour qui
n'a tout simplement pas de véhicule. C'est aussi ce qui rend un repli
**compatible avec un travail à Paris**, donc un projet réaliste plutôt qu'un
rêve : on peut s'installer *avant* la crise, pas seulement y fuir.

Villes qui cumulent ruralité et accès direct :

| Ville | Paris en train | Terroir |
|---|---|---|
| **Vendôme**–Villiers-sur-Loir | **42 min** (TGV, Montparnasse) | Perche vendômois |
| **Château-Thierry** | ~50 min (Est) | Sud de l'Aisne, vallée de la Marne |
| **Noyon** | ~1 h (Nord) | Noyonnais, Oise |
| Compiègne · Creil · Sens · Vernon | 30–55 min | Oise, Yonne, Eure |

La table des gares vit dans `app/gares.py` (nom, position, minutes depuis
Paris) ; la gare la plus proche d'un bien est trouvée automatiquement, dans un
rayon de 25 km au-delà duquel la voiture redevient indispensable.

### ➕ Autres critères de résilience (détectés dans le texte)

Au-delà des équipements « classiques », le score reconnaît aussi :

| Critère | Pilier(s) | Intérêt résilience |
|---|---|---|
| **Habitat troglodyte** | Abri +8, Énergie +3 | creusé dans la roche : **frais l'été, tempéré l'hiver**, cellier naturel — précieux face aux canicules |
| Source / captage | Eau +4 | eau gravitaire, sans réseau ni pompe |
| Bâti pierre / tuffeau / colombage | Énergie +3 | forte **inertie thermique** (confort sans climatisation) |
| Pompe à chaleur / géothermie | Énergie +3 | chauffage sobre |
| Poulailler · vigne · ruches · prairie | Alimentation | production nourricière |
| Hameau · à l'écart · pleine campagne | Situation +2 | tranquillité, moins de dépendances |
| « autonome / autonomie » | badge | orientation du bien |

Ces mots-clés sont cherchés sur **tout le texte de la page** de l'annonce (pas
seulement la courte description), et la **densité de population** de la commune
est récupérée automatiquement (open data) pour le pilier Situation.

## Pourquoi ce barème a été rééquilibré

Un critère ne vaut que s'il **trie**. Le barème initial mettait 20 points sur
l'eau, dont 12 pour le seul puits — or **aucune** des annonces réelles
collectées ne mentionne un puits, une source ou des panneaux solaires : les
agences décrivent la cuisine et la vue, pas l'autonomie. Ces 20 points étaient
donc du poids mort : ils ne départageaient personne et tassaient tous les
scores vers le bas.

Le poids a été déplacé vers ce qui est **réellement renseigné**, sans rien
retirer à la logique de résilience :

| Pilier | Avant | Après | Pourquoi |
|---|---|---|---|
| Autonomie en eau | 20 | **12** | presque jamais mentionné dans les annonces |
| Abri & stockage | 15 | **18** | la cave est citée dans ~1 annonce sur 4 |
| Énergie | 15 | **17** | le chauffage au bois est très souvent indiqué |
| Autonomie alimentaire | 15 | **18** | la surface du terrain est presque toujours donnée |
| Exposition aux risques | 20 | **15** | quasi tous les biens y obtenaient le maximum |
| Situation & accès | 15 | **20** | densité, altitude, route et gare sont calculés pour *chaque* bien |

Un puits reste un vrai plus (6 points, le plus gros bonus « équipement » du
pilier eau) — mais il n'est plus décisif, car c'est un critère qui se vérifie
**en visite**, pas dans une annonce.

## Lecture du total

| Total | Classe |
|---|---|
| 70–100 | Excellent potentiel refuge |
| 55–69 | Bon potentiel |
| 40–54 | Potentiel moyen |
| 0–39 | Potentiel limité |

## Comment les équipements sont détectés

Les annonces ne remplissent pas de case « puits » : l'application **lit le
texte** et repère les mots-clés (avec ou sans accents, au singulier ou au
pluriel) : cave, sous-sol, puits, forage, poêle, cheminée, insert,
photovoltaïque, verger, potager, serre, grange, dépendance, ruisseau, étang,
récupération d'eau… La liste vit dans `app/scoring.py` (dictionnaire
`MOTIFS`).

Limite assumée du POC : une annonce qui écrirait « sans cave » serait
comptée à tort (les négations sont rares dans les annonces immobilières).

## Ajuster le barème

Tout le barème tient dans **`app/scoring.py`**, fonctions `_pilier_*`.
Modifiez les points, puis rechargez les données
(`python scripts/charger_demo.py`) : les scores sont recalculés.
