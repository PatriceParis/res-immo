# Brancher les alertes e-mail (et la mesure d'audience)

Tout le code est en place et **dormant** : sans les clés ci-dessous, la page
/alertes affiche « pas encore ouvertes », l'API répond 503, et le passage
quotidien dit « rien à faire ». Poser les clés suffit — aucun déploiement à
refaire, aucun code à toucher.

## 1. La base des inscriptions — Neon (gratuit)

1. Créer un compte sur https://neon.tech puis un projet (région Europe).
2. Copier la **chaîne de connexion** (« Connection string », commence par
   `postgresql://`).

C'est `DATABASE_URL`. Les adresses e-mail vivront là, jamais dans ce dépôt
(qui est public).

## 2. L'envoyeur de courriels — Resend (gratuit jusqu'à 100/jour)

1. Créer un compte sur https://resend.com.
2. Créer une **clé API** : c'est `RESEND_API_KEY`.
3. Tant que le nom de domaine n'existe pas, l'expéditeur de test
   (`onboarding@resend.dev`) ne peut écrire **qu'à votre propre adresse** —
   parfait pour essayer sans risque.
4. Une fois le domaine acheté : l'ajouter dans Resend (« Domains », deux
   enregistrements DNS à poser), puis définir `ALERTES_EXPEDITEUR`, par
   exemple `Refuge Immo <alertes@votre-domaine.fr>`.

## 3. Le secret des liens — à inventer

`ALERTES_SECRET` : une longue chaîne aléatoire (40 caractères et plus,
n'importe lesquels). Elle signe les liens d'activation et de désinscription.
La garder secrète, ne jamais la changer ensuite (les anciens liens de
désinscription cesseraient de fonctionner).

## 4. Poser les clés — aux DEUX endroits

- **Vercel** (pour le formulaire) : projet → Settings → Environment
  Variables → ajouter `DATABASE_URL`, `ALERTES_SECRET`, `RESEND_API_KEY`
  (et plus tard `ALERTES_EXPEDITEUR`), puis « Redeploy ».
- **GitHub** (pour l'envoi quotidien) : dépôt → Settings → Secrets and
  variables → Actions → « New repository secret » — les trois mêmes noms.

Dès que les trois sont posées côté Vercel, la page /alertes montre le vrai
formulaire. L'envoi part chaque matin à 6 h 30 UTC (workflow « Envoi des
alertes e-mail », lançable aussi à la main pour essayer).

## 5. La mesure d'audience — un interrupteur

Tableau de bord Vercel → projet → onglet **Analytics** → « Enable ».
C'est le compteur sans cookie de l'hébergeur : pas de bandeau à afficher, et
la politique de confidentialité du site le décrit déjà. Tant que ce n'est pas
activé, le script répond 404 et il ne se passe rien.

## Ce que le dispositif ne fait jamais

Aucune adresse transmise à une agence, aucune commission, aucune sélection
faite à la place du visiteur, aucun pixel de suivi dans les courriels, aucune
adresse imprimée dans les journaux (publics) des GitHub Actions. La
désinscription efface la ligne immédiatement, sans condition.
