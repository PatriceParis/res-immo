# Charte graphique de Refuge Immo

Ce document dit comment le site s'écrit et se dessine. Il a été arrêté en
novembre 2026, après une mesure du site : 22 tailles de texte, 25 espacements,
10 arrondis et aucune police de marque. Tout tient maintenant en quelques
valeurs, et un test (`tests/test_charte.py`) vérifie qu'on s'y tient.

Une version consultable, avec les aperçus, existe sous forme de système de
design : https://claude.ai/artifact/UzKcnbvUNDZ4p5cR1vTpnY

## Les polices

Deux polices, hébergées dans `app/static/vendor/fonts/` (licence libre OFL,
aucun service extérieur) :

- **Bricolage Grotesque** pour les titres, le nom du site, les prix et les
  scores. Elle a du caractère ; employée partout, elle fatiguerait.
- **Figtree** pour tout le reste : texte courant, libellés, boutons, chiffres
  dans une phrase.

Dans le code : `var(--f-titre)` et `var(--f-texte)`.

## Les tailles de texte

Sept tailles, chacune avec un rôle. Aucune autre.

| Jeton | Taille | Rôle |
|---|---|---|
| `--t-32` | 32 px | Prix, score |
| `--t-24` | 24 px | Titre de page, nom du site |
| `--t-20` | 20 px | Titre de fiche |
| `--t-18` | 18 px | Titre de section, chapeau |
| `--t-16` | 16 px | Texte courant, valeurs |
| `--t-14` | 14 px | Libellés, précisions |
| `--t-12` | 12 px | Mentions, légendes |

Graisses : 400 pour lire, 600 pour les libellés et les boutons, 700 pour les
titres. Les grands chiffres (prix, score) montent à 800.

## Les espacements

Huit pas, tous multiples de 4. L'écart dit ce qui va ensemble.

| Jeton | Valeur | Usage |
|---|---|---|
| `--e-4` | 4 px | Entre une icône et son chiffre, dans un badge |
| `--e-8` | 8 px | Entre deux éléments liés : icône et libellé, deux étiquettes |
| `--e-12` | 12 px | Dans un bouton, entre deux lignes d'une liste |
| `--e-16` | 16 px | Marge des cartes, bord de l'écran sur téléphone |
| `--e-24` | 24 px | Entre deux sections d'une fiche |
| `--e-32` | 32 px | Entre deux blocs d'une page |
| `--e-48` | 48 px | Avant un nouveau chapitre |
| `--e-64` | 64 px | Bas de page |

Les valeurs de 1 à 3 px restent permises : ce sont des réglages d'alignement,
pas des espacements.

## Les arrondis

| Jeton | Valeur | Usage |
|---|---|---|
| `--r-6` | 6 px | Étiquettes, badges |
| `--r-10` | 10 px | Boutons, champs |
| `--r-14` | 14 px | Cartes, photos, score |
| `--r-pastille` | 999 px | Compteurs, terroirs |

## Trois règles de mise en page

- Une zone cliquable mesure au moins 44 px de haut.
- Le texte courant ne dépasse pas 68 caractères par ligne.
- Un cadre (bordure, fond, arrondi) signale un objet à part : une carte, un
  bouton. Les sections d'une même fiche se séparent par un filet et 24 px,
  sans cadre.

## Le logo

Une maison pleine, une feuille découpée à la place de la porte : l'abri
protège quelque chose de vivant. Il est défini une seule fois, dans
`app/seo.py` (`marque_svg`), et recopié dans `app/static/index.html`.

- Le nom s'écrit « Refuge Immo », en Bricolage Grotesque, à droite du dessin.
- Autour du logo, une marge libre égale à la moitié de sa hauteur.
- Taille minimale : 16 px pour le dessin seul, 24 px de haut avec le nom.
- Deux versions, pas plus : crème sur vert, vert sur crème ou blanc.
- Jamais pâle, jamais déformé, jamais sur un autre fond.

## Les couleurs

Elles n'ont pas changé. Elles sont déclarées en tête de
`app/static/style.css`. La gamme du score (`--n1` à `--n4`) a été validée
pour le daltonisme et le contraste : on n'y touche pas, et le chiffre reste
toujours écrit à côté de la couleur.

## Les icônes

Des tracés au trait, de la couleur du texte qu'ils accompagnent. Pas d'émoji
en guise d'icône. Les mêmes tracés servent à l'application (`TRACES` dans
`app.js`) et aux pages servies (`_TRACES` dans `pages.py`).

## Pour modifier la charte

Changer la valeur d'un jeton suffit : tout le site suit. Les jetons existent
à deux endroits qui doivent rester identiques — `app/static/style.css` et la
feuille embarquée de `app/pages.py` — et le test le vérifie.
