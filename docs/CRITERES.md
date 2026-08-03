# Le score de résilience — barème détaillé

## Philosophie

Le score répond à une question simple : **« si la vie devient plus difficile
(canicules, pénuries, coupures, crues…), cette maison aide-t-elle ses
occupants à tenir ? »** Il additionne six piliers, notés sur 100 au total.
Un bien parfait n'existe pas ; au-delà de 70, on tient un candidat sérieux.

Le score est un **outil de tri, pas une vérité** : il repère les annonces qui
méritent une visite, il ne remplace ni le diagnostic ni le notaire.

## Les 6 piliers

### 💧 Autonomie en eau — 20 points
| Critère | Points | Pourquoi |
|---|---|---|
| Puits ou forage | 12 | eau disponible même si le réseau flanche ; le critère le plus difficile à ajouter après coup |
| Récupération d'eau de pluie (cuve, citerne) | 4 | arrosage, appoint, réserve |
| Cours d'eau, mare ou étang à proximité | 4 | ressource de secours (à filtrer), fraîcheur |

### 🕳️ Abri & stockage — 15 points
| Critère | Points | Pourquoi |
|---|---|---|
| **Cave ou sous-sol** | **8** | stockage longue durée au frais (récoltes, conserves), refuge en canicule ou tempête — l'atout signature de l'application |
| Grange, dépendances | 4 | stockage de matériel, bois, extension possible |
| Atelier ou garage | 3 | réparer soi-même |

### 🔥 Énergie — 15 points
| Critère | Points | Pourquoi |
|---|---|---|
| Chauffage au bois (poêle, insert, chaudière) | 6 | chauffer sans réseau ni fioul |
| Panneaux solaires | 5 | électricité en autonomie partielle |
| Bonne isolation : DPE A/B | 4 (C : 2) | besoin d'énergie réduit à la source |

### 🥕 Autonomie alimentaire — 15 points

**La question : « ce bien permet-il de produire une partie de sa nourriture ? »**
On additionne deux choses : **l'espace** (un terrain, pour cultiver ou élever)
**ET** les **aménagements déjà là** (potager, poulailler…). Ainsi un petit
terrain bien équipé peut marquer autant qu'un grand terrain nu. Total plafonné
à 15.

| Critère | Points | Pourquoi |
|---|---|---|
| Terrain ≥ 1 ha | 6 | de l'espace pour cultiver / élever |
| Terrain ≥ 5 000 m² | 5 | |
| Terrain ≥ 2 500 m² | 4 | |
| Terrain ≥ 1 000 m² | 2 | |
| Verger ou potager déjà en place | +4 | production immédiate |
| Prairie / pâture | +3 | élevage, foin |
| Poulailler | +2 | œufs, volaille |
| Vigne | +2 | |
| Ruches | +2 | miel, pollinisation |
| Serre | +2 | cultures prolongées |

*Exemple : une maison sans grand terrain mais avec potager (+4), poulailler (+2)
et ruches (+2) obtient 8/15 — elle est déjà partiellement nourricière. Une
propriété d'un hectare nu obtient 6/15.*

### 🌊 Exposition aux risques — 20 points (on part de 20, on retire)
| Risque | Points retirés |
|---|---|
| Zone inondable | −8 |
| Sols argileux (retrait-gonflement) fort | −3 (moyen : −1) |
| Site industriel Seveso à < 5 km | −4 (< 10 km : −2) |
| Centrale nucléaire à < 10 km | −5 (< 20 km : −3) |
| Zone sensible aux feux de forêt | −2 |

La distance aux centrales est calculée automatiquement (liste des 18 CNPE
embarquée). Les autres risques viennent du jeu de démonstration ou, pour de
vraies annonces, de l'API officielle **Géorisques**
(`python scripts/enrichir_risques.py`).

### 🚗 Situation & accès — 15 points
| Critère | Points |
|---|---|
| Altitude ≥ 200 m | 3 (≥ 100 m : 2) |
| Densité < 30 hab/km² | 6 (< 80 : 4 ; < 300 : 2) |
| Paris à ≤ 1 h 30 de route | 6 (≤ 2 h 30 : 4 ; ≤ 3 h 30 : 2) |

Le POC cible une **base de repli atteignable** : un refuge à 6 h de route ne
sert à rien en cas de départ précipité — d'où des points pour la proximité,
alors que la faible densité joue en sens inverse. C'est cet équilibre qui
fait ressortir le Perche, la Puisaye ou le Pays d'Othe.

### ➕ Autres critères de résilience (détectés dans le texte)

Au-delà des équipements « classiques », le score reconnaît aussi :

| Critère | Pilier(s) | Intérêt résilience |
|---|---|---|
| **Habitat troglodyte** | Abri +7, Énergie +3 | creusé dans la roche : **frais l'été, tempéré l'hiver**, cellier naturel — précieux face aux canicules |
| Source / captage | Eau +6 | eau gravitaire, sans réseau ni pompe |
| Bâti pierre / tuffeau / colombage | Énergie +3 | forte **inertie thermique** (confort sans climatisation) |
| Pompe à chaleur / géothermie | Énergie +3 | chauffage sobre |
| Poulailler · vigne · ruches · prairie | Alimentation | production nourricière |
| Hameau · à l'écart · pleine campagne | Situation +2 | tranquillité, moins de dépendances |
| « autonome / autonomie » | badge | orientation du bien |

Ces mots-clés sont cherchés sur **tout le texte de la page** de l'annonce (pas
seulement la courte description), et la **densité de population** de la commune
est récupérée automatiquement (open data) pour le pilier Situation.

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
