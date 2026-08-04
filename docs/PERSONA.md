# Le POC vu par l'utilisateur final (persona, douleurs, objectifs)

Ce document recentre le projet sur **la personne qui s'en sert**, et non sur la
prouesse technique. Toutes les décisions produit ci-dessous en découlent.

## Persona principal — « Camille & Sofiane, les néo-ruraux prudents »

> Camille, 38 ans, et Sofiane, 41 ans, cadres à Paris, deux enfants (6 et 9 ans).
> Appartement au 3ᵉ sans extérieur ; l'été 2023 à 39 °C dans le salon les a
> marqués. Ils ne sont **pas survivalistes** : ce sont des gens rationnels,
> inquiets du climat et de la fragilité des villes, qui veulent **un plan B**.
> Budget 250 000–400 000 €. Ils télétravaillent 2 jours/semaine.

Ce qu'ils cherchent : une **maison de repli à la campagne**, à ≤ 2 h 30 de Paris,
**habitable tout de suite** (week-ends, télétravail) et **résiliente** si les
choses se dégradent (canicules, coupures, pénuries) — sans y laisser leurs
économies ni leur santé mentale.

### Personas secondaires
- **« Le préparationniste raisonné »** : priorité autonomie (eau, bois, terrain),
  tolère plus loin, veut des critères durs (hors zone inondable, loin du nucléaire).
- **« Le retraité qui anticipe »** : veut du calme, un potager, un bien sain
  (DPE correct), pas de travaux lourds.

## Douleurs (pains) — ce qui les bloque aujourd'hui

1. **Les portails ne parlent pas « résilience ».** SeLoger/Leboncoin listent
   des milliers de biens mais **aucun moyen de juger** : y a-t-il une cave ?
   un puits ? est-ce inondable ? une centrale à côté ? Il faudrait recouper à
   la main Géorisques, la distance, le DPE… pour **chaque** annonce.
2. **La peur du piège** : acheter une passoire thermique, une maison en zone
   inondable, un bien « isolé mais trop loin », ou près d'un risque caché.
3. **Le manque de temps** : impossible de visiter 40 maisons ; il faut une
   **présélection déjà qualifiée**.
4. **« Où chercher ? »** : ils ne savent pas quels secteurs sont à la fois
   **résilients ET accessibles**.
5. **La charge émotionnelle** : envie de sécurité et de reprendre la main, sans
   basculer dans la parano ni se sentir ridicules.

## Objectifs (gains) — ce qu'ils veulent obtenir

- Une **liste courte de biens résilients** dans leur budget, à ≤ 2 h 30.
  *Le souhait est bien celui-là, mais la sélection va en pratique jusqu'à
  3 h 35 de route (périmètre de 350 km) : les meilleurs terroirs ne sont pas
  tous à 2 h 30, et le train raccourcit souvent le trajet réel — Le Mans en
  55 min, Le Creusot en 1 h 20. D'où le filtre « temps de route » et le
  pilier « accès sans voiture », qui laissent l'arbitrage à l'utilisateur au
  lieu de lui promettre 2 h 30 partout.*
- **Comprendre pourquoi** un bien est résilient (score transparent) pour
  **oser franchir le pas** — une décision rationnelle, pas anxieuse.
- **Voir** le bien (une photo suffit à créer l'envie) et **entrer en contact
  vite** pour les bonnes affaires.
- Être **rassurés sur les risques** (les pièges signalés clairement).

## Ce que ça change dans le POC (et qui est déjà fait)

| Douleur / objectif | Décision produit appliquée |
|---|---|
| « Où chercher ? » + « pas parano » | **On cible les terroirs les plus résilients** (indice `app/regions.py`), on **écarte l'Île-de-France** (dense, artificialisée, stress hydrique). Bandeau « Terroirs ciblés » cliquable, classé par résilience. |
| Les portails ne parlent pas résilience | **Score /100 transparent** en 6 piliers, mis en avant sur chaque bien et détaillé dans la fiche. |
| Peur du piège | **Points de vigilance** explicites (zone inondable, argiles, nucléaire/Seveso proche, passoire thermique). |
| Manque de temps | **Présélection triée par score**, filtres « atouts indispensables » (cave, puits, hors inondation…). |
| Besoin de voir | **Une photo** sur chaque bien (réelle si l'agence en publie, illustration sinon). |
| Entrer en contact | **Bouton de mise en relation** avec l'agence (cf. modèle économique). |
| Accessibilité | **Temps de route depuis Paris** affiché partout, en avant. |

## Modèle économique (ce que la photo unique matérialise)

Le POC montre **une** photo par bien. La logique produit :

- **Gratuit pour l'acheteur** — Camille & Sofiane ne paient rien pour chercher,
  comparer et comprendre. C'est ce qui crée l'audience.
- **Rémunération à la mise en relation qualifiée** — quand un utilisateur
  motivé demande « le reste » (toutes les photos, le dossier complet, la
  visite), la plateforme le **met en relation avec l'agence** détentrice du
  mandat. C'est là qu'est la valeur : un contact chaud, pré-qualifié par le
  score et les filtres. Le bouton « Recevoir les photos & être recontacté » de
  la fiche matérialise cette étape (formulaire de démonstration dans le POC).
- Pistes complémentaires : abonnement « alertes » (nouveaux biens à fort score),
  mise en avant pour les agences partenaires, rapport de résilience détaillé.

Ce choix aligne les intérêts : l'acheteur gagne du temps et de la sérénité,
l'agence reçoit des contacts qualifiés, la plateforme est payée à la valeur créée.

## Ce qu'il faudrait tester avec de vrais utilisateurs (prochaines étapes)

1. Le score inspire-t-il **confiance** ? (comprennent-ils les 6 piliers ?)
2. Les **terroirs ciblés** correspondent-ils à leur imaginaire du « bon coin » ?
3. Combien acceptent de **laisser leur e-mail** pour recevoir le dossier ?
   (le vrai test du modèle économique)
4. Quels **filtres** manquent (gare à moins de X km ? fibre ? école ?) ?
