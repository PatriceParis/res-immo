# ⛰️ Refuge Immo

**Trouvez votre base arrière à moins de 3 h de Paris.**
Refuge Immo est un POC (démonstrateur) de recherche immobilière pensé pour les
Parisiens et Franciliens qui veulent anticiper les dérèglements climatiques :
chaque bien reçoit un **score de résilience sur 100** (eau, abri, énergie,
autonomie alimentaire, risques naturels, accessibilité) et se filtre par
budget, temps de route depuis Paris, taille de terrain, présence d'une cave,
d'un puits…

![Aperçu de l'application](docs/apercu.png)

![Fiche détaillée d'un bien](docs/apercu-fiche.png)

---

## 🚀 Démarrer (aucune compétence technique requise)

**Étape 1 — une seule fois :** installez Python 3 depuis
[python.org/downloads](https://www.python.org/downloads/)
(sur Windows, cochez bien la case *« Add Python to PATH »*).

**Étape 2 :**

| Vous êtes sur… | Faites ceci |
|---|---|
| **Windows** | double-cliquez sur `demarrer.bat` |
| **Mac / Linux** | ouvrez un terminal dans le dossier et tapez `bash demarrer.sh` |

La première fois, l'installation prend une à deux minutes. Quand le message
« Refuge Immo démarre » apparaît, ouvrez **http://localhost:8000** dans votre
navigateur. C'est tout : l'application se charge avec 75 biens de
démonstration.

---

## 🧭 Ce que fait l'application

- **Carte + liste** des biens, avec une pastille de score colorée
  (vert foncé = excellent potentiel refuge) ;
- **Filtres** : budget, temps de route depuis Paris (estimé), score minimum,
  taille de terrain, et atouts indispensables (cave, puits, chauffage au bois,
  panneaux solaires, dépendances, potager, hors zone inondable) ;
- **Fiche détaillée** : décomposition du score en 6 piliers, atouts détectés,
  points de vigilance (zone inondable, sols argileux, centrale nucléaire ou
  site Seveso proche, passoire thermique…), texte de l'annonce ;
- **Détection automatique** : la cave, le puits, le poêle à bois ou le verger
  sont repérés directement dans le texte des annonces.

Le barème complet du score est expliqué dans **[docs/CRITERES.md](docs/CRITERES.md)**.

---

## 📦 D'où viennent les annonces ?

**La stratégie du POC : passer par les agences, pas par les portails.**
Les grands portails (Leboncoin, SeLoger, Bien'ici) interdisent et bloquent la
collecte. Mais derrière chaque annonce, une **agence** détient le mandat — et
son propre site, lui, est *fait pour être trouvé par Google*. On récupère donc
les biens **à la source, chez les agences**, en lisant les données structurées
(`schema.org`) et le `sitemap.xml` que ces sites publient pour le
référencement. Un seul collecteur couvre ainsi des centaines de sites. Tout
est expliqué dans **[docs/STRATEGIE_COLLECTE.md](docs/STRATEGIE_COLLECTE.md)**.

| Source | État |
|---|---|
| **Jeu de démonstration** (75 biens fictifs mais réalistes, attribués à des agences fictives) | ✅ chargé automatiquement |
| **① Découverte d'agences** via Bien'ici (« qui a des biens dans ma zone ? ») | ⚙️ `python scripts/decouvrir_agences.py` |
| **② Collecte chez les agences** (sitemap + schema.org, tout logiciel) | ⚙️ `bash scripts/collecter.sh agence` |
| **Bien'ici** (API JSON directe — position GPS et DPE inclus) | ⚙️ `bash scripts/collecter.sh bienici` |
| **Annonces entre particuliers** (PAP, immo-entre-particuliers) | ⚙️ `bash scripts/collecter.sh pap` |
| **Risques officiels Géorisques** (État) | ⚙️ `python scripts/enrichir_risques.py` |
| SeLoger, Leboncoin (scraping direct) | ❌ volontairement absents (CGU + anti-robots) |

Les alternatives propres (flux partenaires, agrégateurs sous licence) et le
cadre légal sont dans **[docs/LEGAL.md](docs/LEGAL.md)** — à lire avant toute
collecte réelle. Tous les robots respectent d'office le `robots.txt` des sites
et une cadence lente.

---

## ⚠️ Limites connues du POC

- Les **temps de route sont estimés** (distance à vol d'oiseau corrigée) :
  comptez ±20 minutes, vérifiez avant une visite ;
- les biens de démonstration sont **fictifs** (le bandeau en haut à droite le
  rappelle) ;
- les risques du jeu de démonstration sont plausibles mais simplifiés ; la
  vraie donnée s'obtient via le script Géorisques ;
- le collecteur « agences » est **testé hors-ligne** (l'extraction schema.org
  a ses tests) mais pas encore lancé sur de vrais sites depuis cet
  environnement sans internet : au premier lancement chez vous, le journal du
  robot indique pour chaque agence ce qu'il a trouvé. Voir
  `docs/STRATEGIE_COLLECTE.md` et `scraper/README.md`.

---

## 🗂 Structure du projet

| Dossier / fichier | Rôle |
|---|---|
| `demarrer.sh` / `demarrer.bat` | démarrage en un clic |
| `app/` | serveur web, base de données, **moteur de score** (`scoring.py`) |
| `app/static/` | l'interface (carte, filtres, fiches) |
| `scraper/` | robots de collecte Scrapy + garde-fous |
| `scripts/` | jeu de démo, collecte, enrichissement Géorisques |
| `data/annonces_demo.json` | les 75 biens de démonstration |
| `docs/` | barème du score, cadre légal, captures |
| `tests/` | 14 tests automatiques (`python -m pytest tests/`) |

---

## 🔭 Pistes pour la suite

1. brancher un vrai calculateur d'itinéraires (temps de route exacts) ;
2. alertes e-mail quand un bien dépasse un score donné ;
3. données climat 2050 (sécheresse, canicules — projections DRIAS) par commune ;
4. prix du marché local via les ventes réelles (données DVF open data) ;
5. partenariats / flux officiels pour élargir les sources d'annonces.
