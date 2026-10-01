# Cadre légal de la collecte d'annonces

> Ce document décrit ce que le projet fait réellement, mesuré dans le code et
> les données — pas ce qu'il voudrait faire. Ce n'est pas un avis juridique :
> pour l'exploitation commerciale, voir la dernière section.

Réécrit le 1er octobre 2026. La version précédente affirmait qu'« aucune
donnée personnelle n'est collectée » et parlait d'une « veille personnelle ».
Les deux étaient faux : le fichier public portait le texte entier de chaque
annonce — avec le numéro de mobile de 1 258 mandataires et 1 170 courriels
nominatifs — et le site est public, avec une page destinée aux professionnels.
Ce qui suit a été corrigé le même jour, et ce document ne dit plus que ce que
le code fait.

## Ce que le projet est

Un site public (res-immo.vercel.app) qui liste des maisons à vendre à moins de
350 km de Paris, les note sur des critères de résilience climatique à partir
de données publiques, et renvoie chaque fiche vers l'annonce d'origine, sur le
site de l'agence. L'éditeur est un entrepreneur individuel identifié dans les
mentions légales (`app/seo.py`, `EDITEUR`). Des prestations payantes sont
proposées aux agences (`/professionnels`) : rapports, priorité de collecte,
export de données, études — jamais de mise en relation avec des acheteurs,
qui relèverait de l'entremise immobilière (loi Hoguet) et a été retirée le
17 août 2026.

## Ce que font les robots

- **Ils disent leur nom.** Depuis le 1er octobre 2026, tous se présentent
  sous une seule identité, `RefugeImmoBot/1.0 (+https://res-immo.vercel.app/robot)`,
  définie une fois dans `app/robot.py`. La page `/robot` dit ce qu'ils font,
  comment les bloquer (deux lignes de `robots.txt`) et comment obtenir un
  retrait. La bascule a été mesurée avant d'être faite : sur 292 sites et
  trois réseaux, un seul refuse le robot déclaré en acceptant un navigateur ;
  son refus est respecté.
- **Ils respectent `robots.txt`** (`ROBOTSTXT_OBEY = True` ; les collecteurs
  de réseaux lisent les sitemaps déclarés et n'ouvrent pas les chemins
  interdits), lisent les plans de site destinés aux moteurs, tiennent une
  connexion par site et attendent entre deux pages (2,5 s pour le robot
  générique). Ils ne contournent aucune protection : CAPTCHA, pare-feu et
  pages refusées sont des refus, pas des obstacles.
- **Les grands portails sont exclus** (SeLoger, Leboncoin, Logic-Immo,
  Bien'ici) : leurs conditions générales interdisent la collecte, et le projet
  ne la fait pas. Le robot Bien'ici qui subsiste dans le code n'est plus
  utilisé ; le catalogue ne contient aucune annonce de portail.
- **Une agence peut partir, et on ne revient pas.** `data/agences_exclues.json`
  est consulté par les trois collecteurs, par la découverte mensuelle (qui ne
  rebranche jamais un site exclu), par l'export et par le chargement.
  `scripts/exclure_agence.py` tient la promesse des mentions légales en une
  commande : retrait immédiat du fichier publié, et inscription durable.

## Ce qui est conservé, et ce qui ne l'est pas

- **Des faits** : prix, surface, pièces, terrain, commune, étiquette
  énergétique, coordonnées géographiques, lien vers la page d'origine. Les
  faits ne sont pas protégés par le droit d'auteur.
- **Des constats** : la page de l'annonce est lue à la collecte pour y
  repérer une cave, un puits, un poêle, l'état déclaré du bien, une mention
  « vendu » ; seul le constat est gardé (`features`, `etat_declare`, `vendu`,
  `plusieurs_biens`). **Le texte de la page n'est ni republié ni conservé**
  — ni sur le site, ni dans l'interface programmable, ni dans le fichier
  public. Il l'était jusqu'au 1er octobre ; l'historique du dépôt a été
  réécrit ce jour-là pour en retirer toutes les versions.
- **Aucune coordonnée.** Numéros de téléphone et courriels sont effacés des
  champs libres à l'entrée (`app/caviardage.py`), et le recensement
  d'agences ne garde plus le téléphone qu'OpenStreetMap fournit. Le fichier
  public est mesuré sur ce point à chaque export (`identifiants_restants`).
- **Les photographies restent chez l'agence** : elles sont affichées depuis
  ses serveurs, avec notre Referer honnête, sans copie. Le relais qui les
  republiait depuis notre domaine avec un Referer forgé a été retiré le
  10 août 2026 — c'était la position la plus fragile du projet.
- **Les descriptifs rédigés par les agences** ne sortent pas de l'API. Le
  champ `description` du fichier public est vide pour l'essentiel ; les textes
  du site sont rédigés par le site.

## Les règles du jeu en France (résumé)

1. **Données personnelles (RGPD).** Les coordonnées professionnelles d'une
   personne physique — un mandataire, un agent — sont des données
   personnelles, publiques ou non ; la CNIL l'a rappelé en sanctionnant la
   réutilisation de coordonnées « déjà publiques » (Kaspr, décembre 2024).
   Le projet n'en conserve aucune. Les seules données personnelles traitées
   sont celles des visiteurs (journaux de l'hébergeur, adresse e-mail des
   alertes, en double opt-in) : voir `/confidentialite`.
2. **Droit des bases de données (art. L341-1 et s. CPI).** Reprendre une part
   substantielle du catalogue d'un réseau peut être qualifié d'extraction si
   le réseau prouve un investissement propre à sa base. C'est le risque
   principal qui subsiste, avec IAD et Safti ; la réponse du projet est le
   retrait sans délai et sans justification, et une collecte qui dit son nom.
   C'est le point sur lequel un avis d'avocat est nécessaire avant toute
   facturation aux agences.
3. **Conditions générales des sites et loyauté.** Un robot identifié,
   robots.txt respecté, aucune protection contournée, retrait sur simple
   demande : c'est ce qui distingue une collecte loyale d'un parasitisme. La
   cadence lente protège aussi de la qualification d'entrave à un système de
   traitement automatisé (art. 323-2 du Code pénal).
4. **Mentions légales (LCEN, art. 6).** Éditeur, SIREN, directeur de la
   publication et hébergeur sont publiés ; l'adresse et le courriel de contact
   doivent l'être avant tout changement de nom de domaine.
5. **Loi Hoguet.** Aucune mise en relation rémunérée, aucune négociation,
   aucune visite : le site n'est pas un intermédiaire.

## Avant d'aller plus loin

- **Nom et domaine.** Une agence « Le Refuge Immobilier » (SAS, Hautes-Alpes,
  créée en mai 2025) exploite lerefugeimmo.com. Vérifier les marques à l'INPI
  et envisager un autre nom avant d'acheter un domaine.
- **Avocat.** Une consultation en propriété intellectuelle sur le droit des
  bases de données, spécifiquement pour les réseaux de mandataires, avant la
  première facture.
- **Les voies propres** restent les mêmes : flux partenaires des portails,
  agrégateurs sous licence, partenariats directs avec les agences, et les
  données publiques déjà utilisées (Géorisques, Base Adresse Nationale,
  Insee, IGN, DVF).
