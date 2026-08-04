# Audit correctif global

Point de départ : un bug signalé par l'utilisateur. La pastille d'un terroir
annonçait **« 60 biens »** quand la liste filtrée n'en montrait que **2**.

Le défaut n'était pas isolé. Il appartient à une famille : **des chiffres et
des contrôles affichés qui ne font pas ce qu'ils prétendent faire.** Ces
défauts ne font pas planter le site, ils le rendent faux — et aucun test
unitaire ne les attrape, parce qu'ils naissent des vraies données.

Cet audit les a cherchés partout. Ce document liste ce qui a été trouvé, ce
qui a été corrigé, et ce qui a été délibérément laissé.

---

## 1. Des chiffres qui ne décrivaient pas ce qu'ils annonçaient

| Où | Ce qui était affiché | La réalité |
|---|---|---|
| Pastilles de terroir | « 60 biens » | Compté **sans aucun filtre**, à côté d'une liste filtrée à 2 |
| Chaque vignette | « 📷 1 / 9 » | **Nombre inventé** : `6 + hachage(identifiant) % 7` |
| Argument de contact | « 8 autres photos + le dossier complet » | Idem — on ne connaît **qu'une** photo par bien |
| Compteur de résultats | « 250 biens trouvés » | Seuls 200 étaient listés (plafond de l'API) |
| Slogan du site | « les **5** terroirs à moins de **2 h 30** de Paris » | Il y en a **6**, et **49 %** des biens sont au-delà de 2 h 30 (jusqu'à 3 h 35) |

**Corrections.** La clause `WHERE` est désormais partagée entre la liste et le
comptage par région (`db._clauses`), les deux ne peuvent plus diverger. Le
compte de photos est **supprimé, pas remplacé** — inventer un chiffre plus
vraisemblable aurait été le même défaut en plus discret. Le compteur précise
« — les N premiers affichés » quand il tronque. Le slogan n'annonce plus que
ce que le code garantit : le périmètre de 350 km.

## 2. Un filtre qui ne filtrait rien

La case **« Hors zone inondable »** laissait passer **133 biens sur 133**,
dont **86** dans une commune où Géorisques documente l'inondation.

Cause : les risques Géorisques ont été renommés `*_commune` — pour dire leur
portée réelle, l'API documentant le risque à l'échelle de la **commune** et non
de la parcelle. Le chargement, lui, lisait encore l'ancienne clé `inondation`,
disparue au passage. Plus aucun bien n'était marqué inondable.

La case écarte désormais 86 biens, et son intitulé dit ce qu'elle fait :
**« Commune sans inondation recensée »**, avec le rappel que le risque
s'apprécie ensuite à l'adresse.

## 3. Seize biens comptés dans le total, rattachés à aucun terroir

La Sarthe (72) et la Mayenne (53) étaient acceptées **en dur** par le
chargement, sans appartenir à aucune région du classement. Leurs 16 biens
étaient comptés dans « 133 biens trouvés » mais n'apparaissaient dans aucune
pastille : **introuvables par le filtre de région**, et la somme des pastilles
ne retombait pas sur le total.

Elles relèvent désormais du terroir **Pays de la Loire** (Perche sarthois et
bocage mayennais, 74/100, 3ᵉ du classement). Le Perche ne s'arrête pas à la
frontière de l'Orne — et **Le Mans est la meilleure desserte de toute la
sélection : 55 min de Montparnasse**, mieux que Vendôme. Ces biens étaient
jusqu'ici notés comme si aucune gare n'existait ; cinq gares ont été ajoutées.

*Effet de bord évité au passage :* le nombre de terroirs ciblés était figé à 5.
Ajouter une région aurait fait sortir le Centre-Val de Loire — d'où viennent
les troglodytes et le Vendômois — sans que personne ne l'ait décidé.

## 4. Des données extraites à côté de la plaque

| Cas réel | Lu | Vrai |
|---|---|---|
| Propriété à 950 000 € | 50 m² (**19 000 €/m²**) | 350 m² — la première surface du texte était celle de la **piscine** |
| « Terrain de 2 500 m² » | 500 m² habitables | 130 m² — le motif attrapait la fin d'un nombre plus grand |
| « 132,96 m² » | 96 m² | 132,96 m² — décimales ignorées |

L'extracteur retient maintenant, parmi les surfaces plausibles, **celle qui
donne un prix au m² cohérent** (300 à 8 000 €/m²). Quand prix et surface
restent incompatibles, on efface celui des deux qui est le moins sûr plutôt
que d'afficher un prix au m² absurde.

## 5. Ce qui a été vérifié et jugé sain

- **Somme des pastilles = total de la liste** : 133 = 133, filtres compris.
- **Score = somme de ses six piliers**, pour les 133 biens.
- **Écart au marché** recalculable depuis les deux prix au m² affichés.
- **Aucun bien vendu** dans la sélection.
- **Aucun doublon** d'URL ni de bien partagé entre agences.
- **Détection des atouts** (cave, puits, eau à proximité) : aucun faux positif
  du type « puits de lumière » ou « rue du Moulin » sur le jeu réel.
- **Biens fantômes** (bandeau de site lu comme un bien) : les 10 cas connus
  sont bien écartés avant affichage.
- **Temps de route** : estimé à vol d'oiseau corrigé, et **annoncé comme tel**
  à côté de la liste et sur chaque fiche.

## 6. Une règle écartée après vérification

« Terrain plus petit que la surface habitable » semblait révéler des erreurs
de lecture. Vérification faite sur les six cas signalés — tous des maisons de
ville de Tours — **l'agence annonce elle-même « Terrain 70 m² »**. Six faux
positifs sur six : la règle a été retirée. Une règle qui crie au loup est pire
que pas de règle.

---

# Pour que cela ne se reproduise plus

Corriger ces défauts un à un ne suffisait pas : il en reviendra d'autres de
la même famille à chaque évolution. Quatre pièces les empêchent désormais
d'atteindre le site.

## 1. Les promesses de l'interface, écrites une seule fois

`app/coherence.py` énonce **douze invariants** en français, chacun avec le
moyen de le vérifier. Ce sont les promesses que l'écran fait à l'utilisateur :

| Promesse | Ce qu'elle empêche |
|---|---|
| Le compteur décrit la liste, ou dit qu'il tronque | « 250 biens trouvés », 200 affichés |
| La somme des pastilles égale le total | Les 16 biens sarthois comptés nulle part |
| Cliquer une pastille donne le nombre annoncé | **Le bug d'origine** : « 60 biens », 2 dans la liste |
| Chaque case réduit la sélection, et tout ce qui reste la satisfait | La case d'inondation inerte |
| Les curseurs bornent réellement | Un budget de 200 000 € qui laisse passer 400 000 € |
| Chaque tri range vraiment | Un « moins cher d'abord » qui ne trie pas |
| Chaque bien mène à son agence | Une mise en relation impossible |
| Le score égale la somme de ses piliers | Un score qui contredit son propre détail |
| L'écart au marché est recalculable | « 18 % sous le secteur » sorti de nulle part |
| « Nouveau » et les baisses de prix sont justifiés | De faux signaux d'achat |
| Les bornes des filtres couvrent les données | Un bien inatteignable par le curseur |
| Les agences annoncées existent | Une agence au menu sans aucun bien |

Ces invariants ne dépendent pas de la façon dont on interroge le site : ils
tournent aussi bien sur un banc d'essai que sur le site en ligne.

## 2. Ce que l'utilisateur voit vraiment

Le contrat au niveau de l'API ne suffisait pas : **le compte de photos inventé
vivait entièrement dans le JavaScript**, l'API était irréprochable.

`scripts/auditer_interface.py` ouvre donc la vraie page dans un vrai
navigateur et compare l'écran aux données : compteur, pastilles, chaque case
à cocher, fiche détaillée. Il refuse en outre toute **promesse chiffrée non
sourcée** (« 1 / 9 photos », « 8 autres photos »), et interdit qu'une valeur
affichée vienne d'un hachage ou d'un tirage au sort — seule l'illustration de
repli, décor assumé, a le droit de varier.

```bash
python scripts/auditer_interface.py                          # démarre le site et l'audite
python scripts/auditer_interface.py --url https://res-immo.vercel.app
```

## 3. La preuve que ces contrôles détectent quelque chose

Un contrôle qui ne détecte rien donne une fausse assurance — exactement le
travers combattu ici. Chaque invariant est donc confronté, dans
`tests/test_coherence.py`, à une API **délibérément menteuse**, et doit le
voir. Un test vérifie qu'aucun invariant n'échappe à cette preuve ; deux
autres qu'aucune case à cocher ni aucun tri de l'interface n'est hors
contrat — c'est ce dernier qui a révélé que le tri « prix au m² » n'était
surveillé par rien.

La garantie a été éprouvée en **réintroduisant les trois vrais bugs** : le
compte de photos fabriqué, la pastille qui ignore les filtres, la case
d'inondation inerte. Les trois sont détectés — le deuxième réaffiche
littéralement « Centre-Val de Loire annonce 60 biens ».

## 4. Une vérification à chaque modification

Le dépôt n'avait **aucune** vérification automatique : une modification
pouvait atteindre le site sans que rien ne l'ait relue.
`.github/workflows/verification.yml` fait désormais passer, à chaque push :
les tests, l'audit des données servies, puis l'audit de l'interface dans un
navigateur. En mode strict — une promesse non tenue arrête la vérification.

## L'audit des données

`scripts/auditer.py` reste le pendant côté données, et tourne aussi à chaque
collecte (`.github/workflows/collecte.yml`).

```bash
python scripts/auditer.py              # audite data/refuge.db
python scripts/auditer.py --json data/annonces_reel.json
python scripts/auditer.py --strict     # sort en erreur s'il reste des anomalies
```

Dix familles de règles : prix au m² invraisemblable, surfaces hors bornes,
géographie incohérente, biens hors de toute pastille, score ≠ somme des
piliers, écart au marché non reproductible, biens vendus, doublons, liens
morts, et **case à cocher qui sélectionne 0 % ou 100 % du catalogue** — c'est
cette dernière qui aurait attrapé le filtre d'inondation.

---

## Où en est-on

- **108 tests** passent, dont la preuve de détection de chaque invariant.
- **26 promesses d'interface tenues** sur les données réelles.
- **7 anomalies de données sur 133 biens (5 %)**, toutes antérieures aux
  correctifs d'extraction : réextraites avec le code actuel, les 5 prix au m²
  aberrants disparaissent.

## Ajouter quelque chose à l'interface

Une nouvelle case à cocher, un nouveau tri, un nouveau chiffre affiché ?
**Ajoutez l'invariant correspondant dans `app/coherence.py`.** Les tests
refusent une case ou un tri qui ne serait couvert par rien — c'est
volontaire : c'est la seule façon d'empêcher qu'un contrôle tombe en panne
en silence, comme l'a fait celui de l'inondation.
