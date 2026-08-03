# Cadre légal de la collecte d'annonces — à lire avant usage réel

> Ce document est une synthèse de bon sens, pas un avis juridique.
> Pour un lancement commercial, consultez un avocat spécialisé.

## Ce que fait (et ne fait pas) ce POC

- Les robots fournis **respectent le fichier `robots.txt`** des sites : une
  page que le site interdit aux robots n'est **pas** visitée
  (`ROBOTSTXT_OBEY = True` par défaut ; désactivable pour un usage strictement
  personnel via `REFUGE_ROBOTSTXT=0`).
- Le collecteur se présente comme un **navigateur** (User-Agent Chrome), car
  beaucoup de sites d'agences refusent les clients qui s'annoncent « robot »
  alors qu'ils servent la page à un navigateur. Ce n'est pas un déguisement
  malveillant : la cadence reste **lente** (1 requête à la fois, ~2,5 s), on ne
  surcharge jamais le site, et l'usage visé est une **veille personnelle**. On
  ne cherche pas à forcer les protections avancées (Cloudflare, CAPTCHA…).
- **Aucune donnée personnelle des vendeurs n'est collectée** (ni nom, ni
  téléphone, ni e-mail) : uniquement le bien, son prix et son texte.
- Les très grands portails (SeLoger, Leboncoin, Logic-Immo…) sont
  **exclus** : leurs conditions générales interdisent la collecte automatisée
  et ils la bloquent techniquement. Le POC ne cherche pas à contourner ces
  protections — c'est un choix, pas une limite technique.
- **Bien'ici** a été ajouté à la demande, via son API JSON publique (celle
  que le navigateur appelle en visitant le site), sans contournement de
  protection. Ses CGU restreignent néanmoins la réutilisation des annonces :
  réservez ce robot à une **veille personnelle**, gardez la cadence lente
  par défaut, et passez par un flux officiel pour tout usage au-delà.

## Les règles du jeu en France (résumé)

1. **Conditions générales des sites** : la plupart des portails interdisent
   l'extraction automatisée. Les ignorer expose à une responsabilité
   contractuelle, voire à l'infraction d'extraction substantielle d'une base
   de données (droit *sui generis*, art. L342-1 du Code de la propriété
   intellectuelle).
2. **Données personnelles (RGPD)** : les coordonnées d'un vendeur particulier
   sont des données personnelles. Ne les collectez pas (ce POC ne le fait
   pas), ou assumez des obligations lourdes (information, registre, etc.).
3. **Charge des serveurs** : une collecte agressive peut être qualifiée
   d'entrave à un système de traitement automatisé (art. 323-2 du Code
   pénal). D'où la cadence lente imposée ici.

## Les voies propres pour une version production

- **Flux partenaires / API des portails** (SeLoger et Leboncoin ont des
  programmes pour les professionnels) ;
- **agrégateurs sous licence** (Melo, Yanport…) qui revendent la donnée
  d'annonces avec un contrat clair ;
- **partenariats directs** avec des agences et mandataires locaux ;
- **données publiques** librement réutilisables : ventes réelles DVF,
  API Géorisques, Base Adresse Nationale, données communales INSEE —
  déjà utilisées ou prévues dans ce projet.
