/* Refuge Immo — logique de l'interface (vanilla JS, aucune dépendance à installer). */
"use strict";

const $ = (sel) => document.querySelector(sel);

const etat = { annonces: [], carte: null, calque: null, cadre: false, region: null, regions: [] };

/* ---------------- utilitaires ---------------- */

const fmtEuros = new Intl.NumberFormat("fr-FR", {
  style: "currency", currency: "EUR", maximumFractionDigits: 0,
});
const fmtNombre = new Intl.NumberFormat("fr-FR");

// Intl sépare les milliers par une ESPACE FINE INSÉCABLE (U+202F), qui mesure
// un sixième de cadratin. Elle est typographiquement juste, et pratiquement
// invisible : dans les polices système où le glyphe manque, le navigateur la
// rend à largeur nulle. « 250 000 € » gardait son espace en gros corps quand
// « 1479 €/m² », juste en dessous, avait perdu le sien — deux nombres côte à
// côte, deux typographies.
//
// On lui substitue l'espace insécable ordinaire (U+00A0) : un peu plus large
// que ne le voudrait l'usage, mais présente partout. Insécable, donc jamais
// de « 250 » en fin de ligne et « 000 € » à la suivante.
const ESPACE_FINE = / /g;

/** Un prix en euros, milliers séparés — « 250 000 € ». */
function euros(valeur) {
  return fmtEuros.format(valeur).replace(ESPACE_FINE, " ");
}

/** Un nombre, milliers séparés — « 1 479 », « 3 250 ». */
function nombre(valeur) {
  return fmtNombre.format(valeur).replace(ESPACE_FINE, " ");
}

function fmtTemps(minutes) {
  if (minutes == null) return "—";
  const h = Math.floor(minutes / 60), m = Math.round(minutes % 60);
  return h ? `${h} h${m ? " " + String(m).padStart(2, "0") : ""}` : `${m} min`;
}

function echap(txt) {
  const div = document.createElement("div");
  div.textContent = txt == null ? "" : String(txt);
  return div.innerHTML;
}

function niveauScore(score) {
  if (score >= 70) return "n4";
  if (score >= 55) return "n3";
  if (score >= 40) return "n2";
  return "n1";
}

const COULEURS_NIVEAU = { n1: "#c9dcc2", n2: "#7fae84", n3: "#3f7d53", n4: "#1b4332" };

function attenuer(fn, delai = 250) {
  let minuterie;
  return (...args) => { clearTimeout(minuterie); minuterie = setTimeout(() => fn(...args), delai); };
}

function empreinte(s) {
  let h = 0;
  for (let i = 0; i < (s || "").length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

/* ---------------- visuel du bien ----------------
   Une vraie photo si l'annonce en fournit une (biens collectés chez les
   agences) ; sinon une illustration générée selon le type de bien (démo). */

const CIELS = ["#dbe7f0", "#e3edd9", "#e8e6d5", "#dde8e4"];
const COLLINES = ["#bcd3b4", "#a9c6a2", "#cfe0c4"];

function batiment(type) {
  const mur = "#efe9dd", toit = "#7a5a48", porte = "#4a3f30", vitre = "#cfe0ea";
  if (type === "moulin") {
    return `<rect x='188' y='118' width='58' height='74' fill='${mur}'/>
      <polygon points='184,118 217,90 250,118' fill='${toit}'/>
      <rect x='210' y='150' width='16' height='42' fill='${porte}'/>
      <g stroke='${toit}' stroke-width='5' fill='none'>
        <circle cx='176' cy='158' r='27'/><line x1='149' y1='158' x2='203' y2='158'/>
        <line x1='176' y1='131' x2='176' y2='185'/><line x1='157' y1='139' x2='195' y2='177'/>
        <line x1='195' y1='139' x2='157' y2='177'/></g>`;
  }
  if (type === "longère" || type === "fermette" || type === "corps de ferme") {
    return `<rect x='150' y='140' width='150' height='52' fill='${mur}'/>
      <polygon points='146,140 225,112 304,140' fill='${toit}'/>
      <rect x='168' y='158' width='16' height='34' fill='${porte}'/>
      <rect x='210' y='158' width='20' height='18' fill='${vitre}'/>
      <rect x='250' y='158' width='20' height='18' fill='${vitre}'/>
      <rect x='300' y='150' width='40' height='42' fill='#e5dcc9'/>
      <polygon points='298,150 320,132 342,150' fill='${toit}'/>`;
  }
  if (type === "propriété" || type === "château" || type === "manoir") {
    return `<rect x='170' y='128' width='110' height='64' fill='${mur}'/>
      <polygon points='166,128 225,100 284,128' fill='${toit}'/>
      <rect x='276' y='104' width='30' height='88' fill='#e5dcc9'/>
      <polygon points='272,104 291,84 310,104' fill='${toit}'/>
      <rect x='214' y='158' width='20' height='34' fill='${porte}'/>
      <rect x='184' y='150' width='18' height='16' fill='${vitre}'/>
      <rect x='248' y='150' width='18' height='16' fill='${vitre}'/>`;
  }
  return `<rect x='182' y='138' width='84' height='54' fill='${mur}'/>
    <polygon points='178,138 224,108 270,138' fill='${toit}'/>
    <rect x='214' y='160' width='18' height='32' fill='${porte}'/>
    <rect x='192' y='150' width='16' height='16' fill='${vitre}'/>
    <rect x='240' y='150' width='16' height='16' fill='${vitre}'/>`;
}

function photoReelle(a) {
  const u = (a.photo || "").trim();
  if (u.startsWith("//")) return "https:" + u;         // protocol-relative
  if (u.startsWith("http://")) return "https://" + u.slice(7);
  if (u.startsWith("https://")) return u;
  return "";
}

// La photo se charge DIRECTEMENT depuis l'agence — hotlink honnête, notre
// Referer, pas de relais. Le relais /api/photo republiait chaque image
// depuis notre domaine avec un Referer forgé : la position la plus fragile
// juridiquement (Renckhoff 2018 pour la copie, VG Bild-Kunst 2021 pour le
// contournement). La sonde a mesuré le monde d'après avant la bascule :
// soixante photos sur soixante, trente hébergeurs dont IAD, zéro refus du
// hotlink honnête. Une agence qui veut ne plus paraître ici bloque notre
// referer, et c'est réglé — c'est son droit, et notre mécanisme de retrait.

// Balise <img> de la vraie photo, posée sur l'illustration : onerror bascule
// sur l'illustration si l'image ne charge pas (jamais d'image cassée).
//
// La pastille « photo de l'agence » disparaît avec elle : la laisser sur
// l'illustration de repli reviendrait à annoncer une photo qu'on ne montre
// pas — le même défaut que le compte de photos inventé, en plus discret.
// Vue aérienne de la commune — orthophotos IGN, Licence Ouverte, servies par
// la Géoplateforme. C'est le repli quand l'agence ne fournit pas de photo
// exploitable : une VRAIE image du lieu — paysage, bâti, eau, forêt — plutôt
// qu'un dessin. Le lieu est la commune, pas la parcelle : notre géolocalisation
// vient de la BAN sur commune + code postal, l'adresse exacte n'étant presque
// jamais publiée. L'étiquette « © IGN » le dit, et la licence l'exige.
function tuileAerienne(a) {
  if (a.lat == null || a.lon == null) return "";
  const z = 15, n = 2 ** z;
  const x = Math.floor((a.lon + 180) / 360 * n);
  const phi = a.lat * Math.PI / 180;
  const y = Math.floor((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2 * n);
  return "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
    + "&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM"
    + "&FORMAT=image/jpeg&TILEMATRIX=" + z + "&TILEROW=" + y + "&TILECOL=" + x;
}

/* La vue aérienne de la fiche, en pleine largeur et sur toute annonce.
   Cadrée sur la COMMUNE : nos coordonnées viennent de la Base Adresse
   Nationale à partir du nom et du code postal, l'adresse exacte ne figurant
   presque jamais dans l'annonce. La légende le dit — la montrer comme la
   parcelle serait inventer. La mention « © IGN » est due au titre de la
   Licence Ouverte. */
function vueDuCiel(a) {
  const ciel = tuileAerienne(a);
  if (!ciel) return "";
  return `<figure class="vue-ciel">
      <img src="${ciel}" loading="lazy" alt="Vue aérienne de ${echap(a.commune || "la commune")}"
           onerror="this.parentNode.remove()">
      <figcaption>${echap(a.commune || "La commune")} vue du ciel — orthophoto © IGN,
        Licence Ouverte. L'emplacement exact du bien n'est pas connu :
        l'adresse ne figure pas dans l'annonce.</figcaption>
    </figure>`;
}

function imgPhoto(a) {
  const src = photoReelle(a);
  const ciel = tuileAerienne(a);
  const premiere = src || ciel;
  if (!premiere) return "";
  // Trois étages : la photo de l'agence si elle charge, sinon la vue
  // aérienne de la commune, sinon le dessin (le fond du conteneur). Une
  // classe sur le conteneur affiche l'étiquette « © IGN » quand c'est le
  // ciel qui illustre — annoncer une vue aérienne comme la photo du bien
  // serait le mensonge d'à côté.
  const bascule = (src && ciel)
    ? `if(!this.dataset.ciel){this.dataset.ciel=1;this.src='${ciel}';}` +
      `else{this.parentNode.classList.add('photo-absente');this.remove();}`
    : `this.parentNode.classList.add('photo-absente');this.remove();`;
  return `<img class="vraie-photo" src="${premiere}"${src ? "" : ' data-ciel="1"'}
    alt="" loading="lazy" decoding="async"
    onload="if(this.dataset.ciel)this.parentNode.classList.add('vue-aerienne')"
    onerror="${bascule}">`;
}

function illustration(a) {
  const h = empreinte(a.id || a.titre || "x");
  const ciel = CIELS[h % CIELS.length], colline = COLLINES[(h >> 3) % COLLINES.length];
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 220'>
    <rect width='400' height='220' fill='${ciel}'/>
    <circle cx='${330 - (h % 40)}' cy='46' r='22' fill='#f2e6b8'/>
    <path d='M0 150 Q 100 120 200 148 T 400 140 V220 H0 Z' fill='${colline}'/>
    <path d='M0 178 Q 120 150 240 176 T 400 170 V220 H0 Z' fill='#8fb488'/>
    ${batiment(a.type_bien)}
    <g fill='#4f7a4a'><ellipse cx='96' cy='176' rx='22' ry='30'/><ellipse cx='332' cy='182' rx='19' ry='25'/></g>
  </svg>`;
  // encodeURIComponent laisse les apostrophes : on les encode pour ne pas
  // casser le url('…') qui entoure la donnée.
  return "data:image/svg+xml," + encodeURIComponent(svg).replace(/'/g, "%27");
}

/* ---------------- fraîcheur de l'annonce ----------------
   Ce que cherche celui qui revient chaque semaine : ce qui a bougé. */

// Une baisse de prix est le signal d'achat le plus parlant — et celui
// qu'aucun portail n'affiche clairement.
function baisse(a) {
  if (!a.prix_precedent || !a.prix || a.prix >= a.prix_precedent) return "";
  const ecart = Math.round(100 * (a.prix_precedent - a.prix) / a.prix_precedent);
  return `<span class="baisse-prix" title="Ancien prix : ${euros(a.prix_precedent)}">
    ↓ ${ecart} %</span>`;
}

// L'écart au prix du secteur n'est plus affiché — retiré le 9 août 2026.
//
// L'idée reste juste : 150 000 € est cher dans la Nièvre et donné dans
// l'Oise, et seul l'écart local est parlant. C'est la RÉFÉRENCE qui ne
// valait rien. Elle se calculait sur notre propre catalogue — médiane du
// €/m² des biens du même département — donc sur des prix demandés et non
// sur des ventes, et elle héritait de toutes nos erreurs de lecture.
//
// Dans le Nord, sept annonces d'une même agence portaient « 50 000 € », qui
// n'était pas leur prix mais une valeur de formulaire. La médiane du
// département tombait à 353 €/m², et deux biens réels s'affichaient à
// +1108 % et +1885 % du secteur. Une pastille fausse est pire qu'aucune
// pastille : elle a l'air d'un renseignement.
//
// La comparaison reviendra sur une référence extérieure (prix moyen au m²
// de MeilleurAgents ou équivalent). Les champs `prix_m2_secteur` et
// `ecart_marche_pct` continuent d'être calculés, stockés et vérifiés par
// l'audit de données : la tuyauterie attend, seul l'affichage s'arrête.

// Depuis quand ce bien n'a-t-il pas été reconstaté en ligne ?
//
// Une annonce affichée prétend implicitement être encore d'actualité. Or la
// collecte passe chez les agences à tour de rôle : un bien peut n'avoir pas
// été revérifié depuis plusieurs semaines, et avoir été vendu entre-temps.
// Plutôt que de laisser croire, on le dit — et au-delà de 45 jours on invite
// à reconfirmer auprès de l'agence.
const JOURS_AVANT_PEREMPTION = 45;

function joursDepuis(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

function lienAlerte(a) {
  // Le bien qu'on regarde sert de point de départ : son budget arrondi à la
  // dizaine de milliers, et son terroir. La page d'alertes reste libre de
  // tout changer — c'est une suggestion, pas une sélection faite pour
  // quelqu'un.
  const p = new URLSearchParams();
  if (a.prix) p.set("prix_max", String(Math.ceil(a.prix / 10000) * 10000));
  if (a.region) p.set("region", a.region);
  const q = p.toString();
  return "/alertes" + (q ? "?" + q : "");
}

function fraicheur(a) {
  const jours = joursDepuis(a.revue_le);
  if (jours == null) return "";
  const quand = jours <= 0 ? "aujourd'hui"
    : jours === 1 ? "hier"
    : `il y a ${jours} jours`;
  if (jours > JOURS_AVANT_PEREMPTION) {
    return `<p class="source-ligne perime">Vu en ligne ${quand} — à reconfirmer
      auprès de l'agence avant de vous déplacer.</p>`;
  }
  return `<p class="source-ligne">Annonce constatée en ligne ${quand}.</p>`;
}

/* ---------------- terroirs ciblés ---------------- */

// Les gares desservant les biens, classées par temps de trajet vers Paris.
//
// Ce menu porte DEUX critères : les premières entrées demandent simplement
// « une gare rapide » — c'est ce que veut dire « gare TGV » pour qui cherche
// un repli compatible avec un travail à Paris — et les suivantes désignent
// une gare précise. Un seul contrôle, parce que c'est une seule question.
async function chargerGares() {
  const menu = $("#f-gare");
  if (!menu) return;
  let gares = [];
  try {
    const p = lireFiltres();
    p.delete("tri");
    gares = ((await (await fetch("/api/gares?" + p.toString())).json()).gares) || [];
  } catch (e) { return; }
  const choix = menu.value;
  menu.innerHTML = '<option value="">Toutes les gares</option>';

  for (const [minutes, etiquette] of [[60, "moins d’1 h"], [90, "moins d’1 h 30"],
                                      [120, "moins de 2 h"]]) {
    const nb = gares.filter((g) => g.minutes_paris <= minutes)
                    .reduce((somme, g) => somme + g.nb, 0);
    if (!nb) continue;
    const opt = document.createElement("option");
    opt.value = `max:${minutes}`;
    opt.textContent = `Paris en ${etiquette} de train — ${nb} bien${nb > 1 ? "s" : ""}`;
    menu.appendChild(opt);
  }

  const groupe = document.createElement("optgroup");
  groupe.label = "Une gare en particulier";
  for (const g of gares) {
    const opt = document.createElement("option");
    opt.value = g.nom;
    opt.textContent = `${g.nom} — ${fmtTemps(g.minutes_paris)} (${g.nb})`;
    groupe.appendChild(opt);
  }
  if (groupe.children.length) menu.appendChild(groupe);
  // On rétablit le choix de l'utilisateur : ce menu se reconstruit à chaque
  // rafraîchissement des comptes, et le voir se vider serait déroutant.
  menu.value = choix;
  if (menu.value !== choix) menu.value = "";
}

async function chargerTerroirs() {
  // Les pastilles comptent AVEC les filtres actifs : elles annoncent ce que
  // l'utilisateur trouvera en cliquant. On retire le filtre de région et les
  // paramètres d'affichage, qui n'ont pas de sens pour un comptage.
  let params = "";
  try {
    const p = lireFiltres();
    p.delete("region");
    p.delete("tri");
    params = "?" + p.toString();
  } catch (e) { params = ""; }
  try {
    const data = await (await fetch("/api/regions" + params)).json();
    etat.regions = (data.regions || []).filter((r) => r.cible);
  } catch (e) { etat.regions = []; }
  majTerroirs();
}

function majTerroirs() {
  const c = $("#terroirs");
  if (!c) return;
  c.innerHTML = etat.regions.map((r) => `
    <button class="terroir ${etat.region === r.region ? "actif" : ""}${
              r.nb_biens ? "" : " vide"}"
            data-region="${echap(r.region)}" title="${echap(r.zone)} — ${echap(r.argument)}">
      <span class="idx">${r.rang}</span>
      <span class="nom">${echap(r.region)}</span>
      <span class="score-terroir">${r.total}/100</span>
      <span class="nb">${r.nb_biens} biens</span>
    </button>`).join("");
}

/* ---------------- filtres ---------------- */

function lireFiltres() {
  const p = new URLSearchParams();
  const prix = +$("#f-prix").value;
  if (prix < +$("#f-prix").max) p.set("prix_max", prix);
  const temps = +$("#f-temps").value;
  if (temps < +$("#f-temps").max) p.set("temps_max", temps);
  const score = +$("#f-score").value;
  if (score > 0) p.set("score_min", score);
  const terrain = +$("#f-terrain").value;
  if (terrain > 0) p.set("terrain_min", terrain);
  for (const [id, cle] of [
    ["#f-cave", "cave"], ["#f-puits", "puits"], ["#f-bois", "bois"],
    ["#f-solaire", "solaire"], ["#f-dependances", "dependances"],
    ["#f-potager", "potager"], ["#f-troglodyte", "troglodyte"],
    ["#f-hors-inondation", "hors_inondation"],
  ]) if ($(id).checked) p.set(cle, "1");
  // Une seule liste déroulante porte deux critères : soit une gare précise,
  // soit un temps de trajet maximal. C'est ainsi que la question se pose —
  // « celle-là », ou simplement « une gare rapide ».
  const gare = $("#f-gare").value;
  if (gare.startsWith("max:")) p.set("train_max", gare.slice(4));
  else if (gare) p.set("gare", gare);
  if (etat.region) p.set("region", etat.region);
  p.set("tri", $("#f-tri").value);
  return p;
}

function majAffichagesFiltres() {
  const prix = +$("#f-prix").value;
  $("#aff-prix").textContent = prix >= +$("#f-prix").max ? "tous prix" : euros(prix);
  const temps = +$("#f-temps").value;
  $("#aff-temps").textContent = temps >= +$("#f-temps").max ? "sans limite" : fmtTemps(temps);
  $("#aff-score").textContent = $("#f-score").value > 0 ? `${$("#f-score").value}/100` : "0 (tous)";
}

function reinitialiser() {
  $("#f-prix").value = $("#f-prix").max;
  $("#f-temps").value = $("#f-temps").max;
  $("#f-score").value = 0;
  $("#f-terrain").value = "0";
  $("#f-gare").value = "";
  $("#f-tri").value = "score";
  etat.region = null;
  etat.cadre = false;
  document.querySelectorAll(".atouts input").forEach((c) => (c.checked = false));
  majTerroirs();
  majAffichagesFiltres();
  rafraichir();
}

/* ---------------- rendu de la liste ----------------

   La fiche suit la hiérarchie des portails immobiliers, celle que l'œil de
   l'acheteur connaît déjà : le PRIX d'abord, puis les caractéristiques
   (type, surface, pièces, terrain), puis le lieu. Auparavant le titre de
   l'agence occupait la première place en gros et en gras, et le prix se
   perdait dans une rangée où tout avait le même poids. */

// Titre de l'agence, ramené à une casse lisible.
// « PROPRIÉTÉ DE GRAND CARACTERE ORIGINE 18ème » : les agences écrivent
// souvent en capitales, ce qui crie et se lit mal. On repasse en casse de
// phrase, en rendant sa majuscule à la commune, qui elle est un nom propre.
function casseNormale(texte, commune) {
  const t = (texte || "").trim();
  if (!t) return "";
  const lettres = t.replace(/[^A-Za-zÀ-ÿ]/g, "");
  const majuscules = t.replace(/[^A-ZÀ-Þ]/g, "").length;
  if (!lettres.length || majuscules / lettres.length < 0.6) return t;  // casse normale

  let s = t.toLowerCase().replace(/(^|[.!?…]\s+)([a-zà-ÿ])/g,
                                  (m, avant, c) => avant + c.toUpperCase());
  for (const mot of String(commune || "").split(/[\s-]+/)) {
    if (mot.length < 3) continue;
    s = s.replace(new RegExp(`\\b${mot.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "gi"),
                  mot);
  }
  return s;
}

// Ligne de caractéristiques : « Longère · 165 m² · 6 pièces · terrain 7 500 m² ».
// C'est la ligne que tout acheteur lit en diagonale sur un portail.
function caracteristiques(a) {
  const bouts = [];
  const type = a.type_bien || "maison";
  bouts.push(`<b>${echap(type.charAt(0).toUpperCase() + type.slice(1))}</b>`);
  if (a.surface_m2) bouts.push(`${nombre(a.surface_m2)} m²`);
  if (a.pieces) bouts.push(`${a.pieces} pièce${a.pieces > 1 ? "s" : ""}`);
  if (a.terrain_m2) {
    bouts.push(a.terrain_m2 >= 10000
      ? `terrain ${(a.terrain_m2 / 10000).toLocaleString("fr-FR", {maximumFractionDigits: 1})} ha`
      : `terrain ${nombre(a.terrain_m2)} m²`);
  }
  return bouts.join(" · ");
}

// Accès : la voiture, et le train quand il y a une gare — c'est l'argument
// propre à ce service, il mérite d'être lisible d'un coup d'œil.
function acces(a) {
  const bouts = [];
  if (a.temps_voiture_min != null) bouts.push(`🚗 ${fmtTemps(a.temps_voiture_min)}`);
  if (a.train && a.train.nom && a.train.minutes_paris != null) {
    bouts.push(`🚆 ${fmtTemps(a.train.minutes_paris)} <span class="gare">via ${
      echap(a.train.nom)}</span>`);
  }
  return bouts.length ? `<div class="acces">${bouts.join("<span class='sep'>·</span>")}</div>` : "";
}

function ficheAnnonce(a) {
  const niveau = niveauScore(a.score_total);
  const badges = (a.badges || []).slice(0, 3)
    .map((b) => `<span class="badge">${echap(b)}</span>`).join("");
  const reste = (a.badges || []).length > 3
    ? `<span class="badge sourd">+${a.badges.length - 3}</span>` : "";
  const alertes = (a.alertes || []).slice(0, 1)
    .map((al) => `<span class="alerte">⚠ ${echap(al)}</span>`).join("");
  const prixM2 = a.prix && a.surface_m2 ? Math.round(a.prix / a.surface_m2) : null;

  return `
  <article class="fiche" data-id="${echap(a.id)}" tabindex="0" role="button"
           aria-label="Voir le détail : ${echap(a.titre)}">
    <!-- Une seule pastille sur la photo, et c'est le score de résilience.
         « Nouveau » et « photo de l'agence » l'entouraient de bruit : le
         premier n'apprend rien sur le bien, le second énonce l'évidence —
         une photo d'agence sur un site d'annonces. Ce qui distingue ce
         service, c'est le score ; il est désormais seul et lisible de loin. -->
    <div class="photo" style="background-image:url('${illustration(a)}')">
      ${imgPhoto(a)}
      <span class="score-pastille ${niveau}"
            title="Score de résilience : ${Math.round(a.score_total)} sur 100 — ${
              echap((a.score_detail && a.score_detail.classe) || "")}">
        <b>${Math.round(a.score_total)}</b><i>/100</i>
        <small>résilience</small></span>
    </div>
    <div class="fiche-corps">
      <div class="ligne-prix">
        <span class="prix">${a.prix ? euros(a.prix) : "Prix sur demande"}</span>
        ${baisse(a)}
      </div>
      ${prixM2 ? `<div class="prix-m2">${nombre(prixM2)} €/m²</div>` : ""}
      <div class="specs">${caracteristiques(a)}</div>
      <div class="lieu"><b>${echap(a.commune || "")}</b>${
        a.departement ? ` (${echap(a.departement)})` : ""}</div>
      ${acces(a)}
      <!-- Pas d'accroche commerciale dans la liste : « Belle demeure de
           caractère au cœur d'un village prisé » se répète d'une annonce à
           l'autre et n'aide pas à trancher. Ce qui départage tient dans les
           lignes au-dessus — prix, caractéristiques, lieu, accès — et dans le
           score. Le texte de l'agence reste sur la fiche détaillée, là où on
           vient chercher le détail. -->
      <div class="jetons">${badges}${reste}${alertes}</div>
      ${a.agence ? `<div class="agence-ligne">${echap(a.agence)}</div>` : ""}
    </div>
  </article>`;
}

function rendreListe() {
  const liste = $("#liste");
  if (!etat.annonces.length) {
    liste.innerHTML = `<div class="vide">Aucun bien ne correspond à ces critères.<br>
      Essayez d'élargir le budget ou le temps de route.</div>`;
    return;
  }
  liste.innerHTML = etat.annonces.map(ficheAnnonce).join("");
}

/* ---------------- carte ---------------- */

function initCarte() {
  if (!window.L) {
    $("#carte").innerHTML = `<div class="carte-indispo">Carte indisponible sans connexion internet —
      la liste des biens reste utilisable ci-dessous.</div>`;
    return;
  }
  etat.carte = L.map("carte", { scrollWheelZoom: false }).setView([48.4, 2.7], 7);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 17,
    attribution: "© OpenStreetMap",
  }).addTo(etat.carte);
  L.circleMarker([48.853, 2.3499], {
    radius: 7, color: "#24312a", weight: 2, fillColor: "#fff", fillOpacity: 1,
  }).addTo(etat.carte).bindTooltip("Paris", { permanent: false });
  etat.calque = L.layerGroup().addTo(etat.carte);

  const legende = L.control({ position: "bottomleft" });
  legende.onAdd = () => {
    const div = L.DomUtil.create("div", "legende-carte");
    div.innerHTML = `<b>Score de résilience</b><br>
      <span class="pastille n4"></span>70–100 · excellent<br>
      <span class="pastille n3"></span>55–69 · bon<br>
      <span class="pastille n2"></span>40–54 · moyen<br>
      <span class="pastille n1"></span>0–39 · limité`;
    return div;
  };
  legende.addTo(etat.carte);
}

function rendreCarte() {
  if (!etat.carte) return;
  etat.calque.clearLayers();
  const points = [];
  for (const a of etat.annonces) {
    if (a.lat == null || a.lon == null) continue;
    points.push([a.lat, a.lon]);
    const marqueur = L.circleMarker([a.lat, a.lon], {
      radius: 9,
      color: "#1b4332", weight: 2,
      fillColor: COULEURS_NIVEAU[niveauScore(a.score_total)], fillOpacity: 0.95,
    });
    marqueur.bindPopup(
      `<b>${Math.round(a.score_total)}/100</b> — ${echap(a.titre)}<br>` +
      `${a.prix ? euros(a.prix) : ""} · 🚗 ${fmtTemps(a.temps_voiture_min)}<br>` +
      `<a href="#" data-ouvrir="${echap(a.id)}">Voir la fiche</a>`
    );
    marqueur.addTo(etat.calque);
  }
  if (points.length && !etat.cadre) {
    etat.carte.fitBounds(points, { padding: [30, 30] });
    etat.cadre = true;
  }
}

/* ---------------- fiche détaillée ---------------- */

const ICONES_PILIERS = {
  eau: "💧", abri: "📦", energie: "🔥",
  alimentation: "🥕", risques: "🛡️", situation: "🚗",
};

// Explication de chaque pilier — dépliable en tapant (utile sur mobile, où
// une infobulle au survol n'existe pas).
const EXPLICATIONS_PILIERS = {
  eau: "Puits ou forage, source/captage, récupération d'eau de pluie, cours d'eau à proximité.",
  abri: "Cave ou sous-sol, habitat troglodyte, grange/dépendances, atelier.",
  energie: "Chauffage au bois, panneaux solaires, pompe à chaleur, inertie thermique (pierre/troglodyte), DPE.",
  alimentation: "Pouvoir produire une partie de sa nourriture. On additionne l'espace (la taille du terrain, pour cultiver ou élever) ET les aménagements déjà là — potager, verger, poulailler, serre, vigne, ruches, prairie. Un petit terrain bien équipé peut marquer autant qu'un grand terrain nu. Score à 0 quand l'annonce n'indique ni terrain ni aménagement : on ne peut alors rien prouver.",
  risques: "On part de 20 puis on retire des points : zone inondable, sols argileux, centrale nucléaire ou site Seveso proche, feux de forêt.",
  situation: "Altitude, faible densité de population, hameau isolé, temps de route depuis Paris, et surtout accès en TRAIN : une gare proche rend le refuge atteignable sans voiture (pénurie de carburant, pas de véhicule) et compatible avec un travail à Paris.",
};

function jaugesPiliers(detail) {
  if (!detail || !detail.piliers) return "";
  return Object.entries(detail.piliers).map(([cle, p]) => `
    <details class="pilier">
      <summary class="pilier-tete">
        <span class="nom">${ICONES_PILIERS[cle] || ""} ${echap(p.libelle)}
          <span class="info-i" aria-hidden="true">ⓘ</span></span>
        <div class="jauge" role="meter" aria-valuemin="0" aria-valuemax="${p.max}"
             aria-valuenow="${p.points}" aria-label="${echap(p.libelle)}">
          <div style="width:${Math.min(100, (p.points / p.max) * 100)}%"></div>
        </div>
        <span class="valeur"><b>${p.points}</b>/${p.max}</span>
      </summary>
      <p class="pilier-info">${echap(EXPLICATIONS_PILIERS[cle] || "")}</p>
    </details>`).join("");
}

function tuile(etiquette, valeur, sous) {
  if (valeur == null || valeur === "") return "";
  return `<div class="stat"><span class="etiquette">${etiquette}</span>
    <span class="valeur">${valeur}</span>
    ${sous ? `<span class="sous">${sous}</span>` : ""}</div>`;
}

function ouvrirFiche(id) {
  const a = etat.annonces.find((x) => x.id === id);
  if (!a) return;
  const niveau = niveauScore(a.score_total);
  const detail = a.score_detail || {};
  const listeBadges = a.badges || [];
  const badges = listeBadges.map((b) => `<span class="badge">✓ ${echap(b)}</span>`).join("");
  const alertes = (a.alertes || []).map((al) => `<span class="alerte">⚠ ${echap(al)}</span>`).join("");
  const vigilances = ((detail && detail.vigilances) || [])
    .map((v) => `<li>${echap(v)}</li>`).join("");
  const prixM2 = a.prix && a.surface_m2 ? Math.round(a.prix / a.surface_m2) : null;
  const risques = a.risques || {};
  const nucleaire = risques.nucleaire_km != null
    ? `Centrale nucléaire la plus proche : ${echap(risques.nucleaire_nom || "")} à ${Math.round(risques.nucleaire_km)} km.` : "";

  $("#modale-contenu").innerHTML = `
    <div class="photo-grande" style="background-image:url('${illustration(a)}')">
      ${imgPhoto(a)}
    </div>
    <header class="fiche-entete">
      <div class="score-jeton grand ${niveau}" title="Score de résilience">${Math.round(a.score_total)}<small>/100</small></div>
      <div>
        <!-- Même hiérarchie que la liste : le prix d'abord, puis les
             caractéristiques, puis le lieu. Le titre de l'agence, ramené en
             casse lisible, vient après — c'est une accroche, pas une donnée. -->
        <div class="prix-modale">${a.prix ? euros(a.prix) : "Prix sur demande"}${
          prixM2 ? ` <span class="prix-m2">${nombre(prixM2)} €/m²</span>` : ""}</div>
        <div class="specs">${caracteristiques(a)}</div>
        <div class="lieu">📍 ${echap(a.commune || "")} ${a.code_postal ? `(${echap(a.code_postal)})` : ""}</div>
        <h2 id="modale-titre">${echap(casseNormale(a.titre, a.commune))}</h2>
        <div class="classe-grande">${echap(detail.classe || "")}</div>
      </div>
    </header>

    <!-- Prix, surface et terrain sont déjà en tête : les répéter en tuiles
         faisait dire trois fois la même chose. Ne restent ici que les
         informations qu'on ne lit nulle part ailleurs. -->
    <div class="stats">
      ${tuile("Pièces", a.pieces)}
      ${tuile("Paris en voiture", fmtTemps(a.temps_voiture_min),
              a.distance_km ? "~" + Math.round(a.distance_km * 1.25) + " km · estimé" : "estimé")}
      ${a.train && a.train.nom
        ? tuile("Paris en train", fmtTemps(a.train.minutes_paris),
                `${echap(a.train.nom)} · à ${a.train.km} km`)
        : ""}
      ${tuile("Altitude", a.altitude != null ? Math.round(a.altitude) + " m" : null)}
      ${tuile("DPE", a.dpe ? `<span class="dpe dpe-${echap(a.dpe)}">${echap(a.dpe)}</span>` : "n.c.")}
    </div>

    <!-- Le bloc de mise en relation a été retiré le 17 août 2026. Il
         recueillait l'e-mail du visiteur pour le transmettre à l'agence, et
         l'annonçait lui-même : « rémunéré à la mise en relation qualifiée ».
         Prêter son concours, même à titre accessoire et contre rémunération,
         à la recherche d'un immeuble pour autrui, c'est l'activité que la loi
         Hoguet réserve aux titulaires d'une carte professionnelle. Écrire
         « nous ne sommes pas une agence » ne change rien à ce qui est fait.

         Ce qui le remplace ne met personne en relation : le visiteur choisit
         un budget et des terroirs, et c'est NOUS qui lui écrivons. Aucune
         coordonnée ne part chez une agence, aucune commission n'est perçue,
         et le lien vers l'annonce d'origine reste le seul chemin vers le
         vendeur. -->
    <div class="alerte-bloc">
      <strong>Soyez alerté des prochaines</strong>
      <span>Ce bien vous parle ? Choisissez un budget et des terroirs : nous
        vous prévenons quand une maison y entre au catalogue.</span>
      <a class="btn-alerte" href="${lienAlerte(a)}">Créer mon alerte</a>
    </div>

    <section class="panneau">
      <h4>Le score en détail · ${Math.round(a.score_total)}/100</h4>
      ${jaugesPiliers(detail)}
    </section>

    <section>
      <h4>Atouts détectés${listeBadges.length ? ` (${listeBadges.length})` : ""}</h4>
      ${badges ? `<div class="jetons">${badges}</div>`
               : `<p class="aucun">Aucun atout particulier détecté dans l'annonce.</p>`}
    </section>

    <section>
      <h4>Points de vigilance</h4>
      ${alertes ? `<div class="jetons">${alertes}</div>`
                : `<p class="aucun">✓ Aucun point de vigilance détecté sur le bien.</p>`}
      ${nucleaire ? `<p class="note-detail">${nucleaire}</p>` : ""}
      ${vigilances ? `
        <p class="note-detail"><b>Risques recensés sur la commune</b> (source
        Géorisques). Ils ne disent pas que ce bien est exposé — presque toute
        commune française est concernée par au moins l'un d'eux : à vérifier à
        l'adresse exacte (l'état des risques est obligatoire à la vente).</p>
        <ul class="vigilances">${vigilances}</ul>` : ""}
    </section>

    <section>
      <h4>La commune vue du ciel</h4>
      ${/* Le descriptif rédigé par l'agence ne s'affiche PLUS ici. C'était le
            seul endroit du site où le texte d'un tiers était republié tel
            quel — les pages servies par le serveur écrivent depuis nos
            données depuis le début (voir app/redaction.py). Il reste lu pour
            détecter cave, puits ou poêle et repérer les biens vendus : le
            lire pour analyser n'est pas le rediffuser, et l'API ne le sort
            plus (voir db._row_vers_dict, qui écartait déjà le texte intégral
            pour la même raison).

            À sa place, la seule image que nous ayons de plein droit : une
            orthophoto IGN sous Licence Ouverte. Elle montre ce que la fiche
            analyse — le bâti, les haies, les bois, l'eau — et le fait
            désormais sur TOUTE fiche, plus seulement quand la photo de
            l'agence manque. La légende dit ce qu'elle est : la commune, pas
            la parcelle. */""}
      ${vueDuCiel(a)}
      ${/* Le seul lien qui mène VRAIMENT au bien passe en premier, et il est
            le seul à le promettre. « Voir chez l'agence » pointait sur
            `agence_url`, qui n'est jamais que la racine du site — pour les
            1143 fiches servies, sans exception : le visiteur atterrissait sur
            une page d'accueil, donc une liste, et devait y rechercher
            lui-même le bien qu'il venait de quitter. Le site de l'agence
            garde son lien, mais sous son vrai nom.

            « Source : iad-france-27 » disparaît au passage : c'est notre
            identifiant interne, il ne dit rien à personne d'autre. Le nom de
            l'agence, lui, dit d'où vient l'annonce. */""}
      <p class="source-ligne">Annonce publiée par <b>${echap(a.agence || "l'agence")}</b>${a.url
        ? ` — <a href="${echap(a.url)}" target="_blank" rel="noopener">voir l'annonce d'origine</a>`
        : ""}</p>
      ${a.agence_url ? `<p class="source-ligne"><a href="${echap(a.agence_url)}" target="_blank" rel="noopener">Site de l'agence</a></p>` : ""}
      ${fraicheur(a)}
    </section>`;

  $("#voile").hidden = false;
  document.body.style.overflow = "hidden";
}

function fermerFiche() {
  $("#voile").hidden = true;
  document.body.style.overflow = "";
}

/* ---------------- chargement des données ---------------- */

async function rafraichir() {
  const p = lireFiltres();
  p.set("limit", "500");           // plafond de l'API : on demande tout
  const data = await (await fetch("/api/annonces?" + p.toString())).json();
  etat.annonces = data.items;

  // Le compteur doit décrire CE QUI EST AFFICHÉ. Annoncer « 250 biens
  // trouvés » en n'en listant que 200 est le même travers que les pastilles
  // de terroir qui comptaient sans les filtres : un chiffre qui ne
  // correspond pas à ce qu'il prétend décrire.
  const n = data.total;
  const montres = (data.items || []).length;
  $("#compteur").textContent = `${n} bien${n > 1 ? "s" : ""} trouvé${n > 1 ? "s" : ""}`
    + (montres < n ? ` — les ${montres} premiers affichés` : "");

  rendreListe();
  rendreCarte();
  // Les pastilles de terroir comptent avec les mêmes filtres : elles doivent
  // donc être recalculées à chaque changement. Le menu des gares aussi —
  // annoncer « Creil (13) » quand les filtres n'en laisseraient aucun serait
  // le même mensonge, en plus discret.
  chargerTerroirs();
  chargerGares();
}

async function initialiser() {
  initCarte();
  try {
    const meta = await (await fetch("/api/meta")).json();
    if (meta.prix_max) {
      // plafonné pour qu'une valeur extrême (données réelles imparfaites) ne
      // casse pas le curseur.
      const plafond = Math.min(Math.ceil(meta.prix_max / 50000) * 50000, 2000000);
      $("#f-prix").max = plafond;
      $("#f-prix").value = plafond;
    }
    const agences = ((await (await fetch("/api/agences")).json()).agences) || [];
    if (agences.length) {
      $("#bandeau-source").textContent =
        `${agences.length} agence${agences.length > 1 ? "s" : ""}`;
    }
    await chargerGares();
  } catch (e) { /* la page reste utilisable avec les valeurs par défaut */ }
  await chargerTerroirs();
  appliquerParametresUrl();
  majAffichagesFiltres();
  await rafraichir();
}

/* Les pages servies par le serveur — terroirs, petits prix — envoient vers
   la carte avec un filtre dans l'adresse : `/?region=Normandie`,
   `/?prix_max=100000`. Rien ne les lisait : on arrivait sur le catalogue
   entier, à recommencer la sélection qu'on venait de faire. Un lien qui
   promet un filtre doit l'appliquer, comme un lien qui promet une annonce
   doit y mener. */
function appliquerParametresUrl() {
  const p = new URLSearchParams(location.search);
  const prix = +p.get("prix_max");
  // Au-delà du plafond du curseur, la demande vaut « tous prix » : on borne
  // plutôt que d'ignorer, sinon un lien un peu large ne filtrerait rien.
  if (prix > 0) $("#f-prix").value = Math.min(prix, +$("#f-prix").max);
  const region = p.get("region");
  // `etat.regions` contient des OBJETS, pas des noms : comparer une chaîne à
  // la liste renverrait toujours faux, silencieusement.
  if (region && etat.regions.some((r) => r.region === region)) {
    etat.region = region;
    etat.cadre = false;          // recentrer la carte sur le terroir demandé
    majTerroirs();
  }
}

/* ---------------- événements ---------------- */

const rafraichirDoucement = attenuer(rafraichir);
for (const id of ["#f-prix", "#f-temps", "#f-score"]) {
  $(id).addEventListener("input", () => { majAffichagesFiltres(); rafraichirDoucement(); });
}
for (const id of ["#f-terrain", "#f-gare", "#f-tri"]) $(id).addEventListener("change", rafraichir);
document.querySelectorAll(".atouts input").forEach((c) => c.addEventListener("change", rafraichir));
$("#f-reinit").addEventListener("click", reinitialiser);

$("#terroirs").addEventListener("click", (ev) => {
  const b = ev.target.closest(".terroir");
  if (!b) return;
  etat.region = etat.region === b.dataset.region ? null : b.dataset.region;
  etat.cadre = false;  // recentrer la carte sur le terroir choisi
  majTerroirs();
  rafraichir();
});

$("#liste").addEventListener("click", (ev) => {
  const fiche = ev.target.closest(".fiche");
  if (fiche) ouvrirFiche(fiche.dataset.id);
});
$("#liste").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") {
    const fiche = ev.target.closest(".fiche");
    if (fiche) ouvrirFiche(fiche.dataset.id);
  }
});
document.addEventListener("click", (ev) => {
  const lien = ev.target.closest("[data-ouvrir]");
  if (lien) { ev.preventDefault(); ouvrirFiche(lien.dataset.ouvrir); }
});
$("#modale-fermer").addEventListener("click", fermerFiche);
$("#voile").addEventListener("click", (ev) => { if (ev.target === $("#voile")) fermerFiche(); });
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") fermerFiche(); });

/* filtres repliables sur mobile (l'utilisateur voit d'abord les biens) */
const filtresToggle = $("#filtres-toggle");
if (filtresToggle) {
  const petit = () => window.matchMedia("(max-width: 900px)").matches;
  if (petit()) $(".filtres").classList.add("replie");
  const syncToggle = () =>
    filtresToggle.setAttribute("aria-expanded", String(!$(".filtres").classList.contains("replie")));
  syncToggle();
  filtresToggle.addEventListener("click", () => {
    $(".filtres").classList.toggle("replie");
    syncToggle();
  });
}

initialiser();
