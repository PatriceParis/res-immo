/* Refuge Immo — logique de l'interface (vanilla JS, aucune dépendance à installer). */
"use strict";

const $ = (sel) => document.querySelector(sel);

const etat = { annonces: [], carte: null, calque: null, cadre: false, region: null, regions: [] };

/* ---------------- utilitaires ---------------- */

const fmtEuros = new Intl.NumberFormat("fr-FR", {
  style: "currency", currency: "EUR", maximumFractionDigits: 0,
});
const fmtNombre = new Intl.NumberFormat("fr-FR");

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

// URL de la vraie photo relayée par NOTRE domaine (/api/photo) : sinon les CDN
// des agences bloquent le hotlink et rien ne s'affiche. "" si pas de photo.
function photoProxy(a) {
  const u = photoReelle(a);
  return u ? "/api/photo?u=" + encodeURIComponent(u) : "";
}

// Balise <img> de la vraie photo, posée sur l'illustration : onerror bascule
// sur l'illustration si l'image ne charge pas (jamais d'image cassée).
function imgPhoto(a) {
  const src = photoProxy(a);
  if (!src) return "";
  return `<img class="vraie-photo" src="${src}" alt="" loading="lazy"
    decoding="async" onerror="this.remove()">`;
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

function nbPhotos(a) {
  return 6 + empreinte(a.id || a.titre || "x") % 7;  // 6 à 12 photos « au dossier »
}

/* ---------------- terroirs ciblés ---------------- */

async function chargerTerroirs() {
  try {
    const data = await (await fetch("/api/regions")).json();
    etat.regions = (data.regions || []).filter((r) => r.cible);
  } catch (e) { etat.regions = []; }
  majTerroirs();
}

function majTerroirs() {
  const c = $("#terroirs");
  if (!c) return;
  c.innerHTML = etat.regions.map((r) => `
    <button class="terroir ${etat.region === r.region ? "actif" : ""}"
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
    ["#f-potager", "potager"], ["#f-hors-inondation", "hors_inondation"],
  ]) if ($(id).checked) p.set(cle, "1");
  if ($("#f-agence").value) p.set("agence", $("#f-agence").value);
  if (etat.region) p.set("region", etat.region);
  p.set("tri", $("#f-tri").value);
  return p;
}

function majAffichagesFiltres() {
  const prix = +$("#f-prix").value;
  $("#aff-prix").textContent = prix >= +$("#f-prix").max ? "tous prix" : fmtEuros.format(prix);
  const temps = +$("#f-temps").value;
  $("#aff-temps").textContent = temps >= +$("#f-temps").max ? "sans limite" : fmtTemps(temps);
  $("#aff-score").textContent = $("#f-score").value > 0 ? `${$("#f-score").value}/100` : "0 (tous)";
}

function reinitialiser() {
  $("#f-prix").value = $("#f-prix").max;
  $("#f-temps").value = $("#f-temps").max;
  $("#f-score").value = 0;
  $("#f-terrain").value = "0";
  $("#f-agence").value = "";
  $("#f-tri").value = "score";
  etat.region = null;
  etat.cadre = false;
  document.querySelectorAll(".atouts input").forEach((c) => (c.checked = false));
  majTerroirs();
  majAffichagesFiltres();
  rafraichir();
}

/* ---------------- rendu de la liste ---------------- */

function ficheAnnonce(a) {
  const niveau = niveauScore(a.score_total);
  const badges = (a.badges || []).slice(0, 4)
    .map((b) => `<span class="badge">✓ ${echap(b)}</span>`).join("");
  const reste = (a.badges || []).length > 4
    ? `<span class="badge">+ ${a.badges.length - 4}</span>` : "";
  const alertes = (a.alertes || []).slice(0, 2)
    .map((al) => `<span class="alerte">⚠ ${echap(al)}</span>`).join("");
  const prixM2 = a.prix && a.surface_m2 ? Math.round(a.prix / a.surface_m2) : null;

  return `
  <article class="fiche" data-id="${echap(a.id)}" tabindex="0" role="button"
           aria-label="Voir le détail : ${echap(a.titre)}">
    <div class="photo" style="background-image:url('${illustration(a)}')">
      ${imgPhoto(a)}
      <span class="photo-compte">📷 1 / ${nbPhotos(a)}</span>
    </div>
    <div class="fiche-haut">
      <div class="score-jeton ${niveau}" title="Score de résilience">${Math.round(a.score_total)}<small>/100</small></div>
      <div>
        <h3>${echap(a.titre)}</h3>
        <div class="lieu">${echap(a.commune || "")} · ${echap(a.departement || "")} · 🚗 ${fmtTemps(a.temps_voiture_min)} de Paris</div>
        <div class="classe">${echap((a.score_detail && a.score_detail.classe) || "")}</div>
        ${a.agence ? `<div class="agence-ligne">🏢 ${echap(a.agence)}</div>` : ""}
      </div>
    </div>
    <div class="chiffres">
      <span class="prix">${a.prix ? fmtEuros.format(a.prix) : "Prix n.c."}</span>
      ${prixM2 ? `<span>${fmtNombre.format(prixM2)} €/m²</span>` : ""}
      <span><b>${a.surface_m2 ? fmtNombre.format(a.surface_m2) + " m²" : "—"}</b> hab.</span>
      <span>terrain <b>${a.terrain_m2 ? fmtNombre.format(a.terrain_m2) + " m²" : "—"}</b></span>
      ${a.pieces ? `<span><b>${a.pieces}</b> p.</span>` : ""}
    </div>
    <div class="jetons">${badges}${reste}${alertes}</div>
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
      `${a.prix ? fmtEuros.format(a.prix) : ""} · 🚗 ${fmtTemps(a.temps_voiture_min)}<br>` +
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
  const prixM2 = a.prix && a.surface_m2 ? Math.round(a.prix / a.surface_m2) : null;
  const risques = a.risques || {};
  const nucleaire = risques.nucleaire_km != null
    ? `Centrale nucléaire la plus proche : ${echap(risques.nucleaire_nom || "")} à ${Math.round(risques.nucleaire_km)} km.` : "";

  $("#modale-contenu").innerHTML = `
    <div class="photo-grande" style="background-image:url('${illustration(a)}')">
      ${imgPhoto(a)}
      <span class="photo-compte">📷 1 / ${nbPhotos(a)} photos</span>
    </div>
    <header class="fiche-entete">
      <div class="score-jeton grand ${niveau}" title="Score de résilience">${Math.round(a.score_total)}<small>/100</small></div>
      <div>
        <h2 id="modale-titre">${echap(a.titre)}</h2>
        <div class="lieu">📍 ${echap(a.commune || "")} ${a.code_postal ? `(${echap(a.code_postal)})` : ""} · ${echap(a.departement || "")}</div>
        ${a.agence ? `<div class="agence-ligne">🏢 ${echap(a.agence)}</div>` : ""}
        <div class="classe-grande">${echap(detail.classe || "")}</div>
      </div>
    </header>

    <div class="stats">
      ${tuile("Prix", a.prix ? fmtEuros.format(a.prix) : "n.c.",
              prixM2 ? fmtNombre.format(prixM2) + " €/m²" : "")}
      ${tuile("Surface", a.surface_m2 ? fmtNombre.format(a.surface_m2) + " m²" : null)}
      ${tuile("Terrain", a.terrain_m2 ? fmtNombre.format(a.terrain_m2) + " m²" : null)}
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

    <div class="mise-en-relation">
      <div class="galerie" aria-hidden="true">
        <div class="vignette" style="background-image:${photoProxy(a) ? `url('${photoProxy(a)}'),` : ""}url('${illustration(a)}')"></div>
        <div class="vignette verrou">🔒</div>
        <div class="vignette verrou">🔒</div>
        <div class="vignette verrou">＋${Math.max(1, nbPhotos(a) - 4)}</div>
      </div>
      <div class="mer-corps">
        <strong>${nbPhotos(a) - 1} autres photos + le dossier complet</strong>
        <span>Gratuit pour vous : on vous met en relation avec ${a.agence ? echap(a.agence) : "l'agence"}
          pour recevoir toutes les photos, le DPE détaillé et organiser la visite.</span>
        <button class="btn-mer" id="btn-mer">Recevoir les photos &amp; être recontacté</button>
      </div>
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
                : `<p class="aucun">✓ Aucun point de vigilance détecté.</p>`}
      ${nucleaire ? `<p class="note-detail">${nucleaire}</p>` : ""}
    </section>

    <section>
      <h4>L'annonce</h4>
      <p class="description">${echap(a.description)}</p>
      ${a.agence_url ? `<p class="source-ligne">Mandat : <b>${echap(a.agence)}</b> — <a href="${echap(a.agence_url)}" target="_blank" rel="noopener">voir chez l'agence</a></p>` : ""}
      <p class="source-ligne">Source : ${echap(a.source)}${a.url
        ? ` — <a href="${echap(a.url)}" target="_blank" rel="noopener">voir l'annonce d'origine</a>`
        : ""}</p>
    </section>`;

  const btn = $("#btn-mer");
  if (btn) btn.addEventListener("click", () => {
    btn.parentElement.innerHTML = `
      <strong>Être mis en relation avec ${a.agence ? echap(a.agence) : "l'agence"}</strong>
      <div class="mer-form">
        <input type="email" id="mer-mail" placeholder="Votre e-mail" aria-label="Votre e-mail">
        <button class="btn-mer" id="mer-envoi">Être recontacté</button>
      </div>
      <p class="mer-note" id="mer-note">Modèle : la plateforme est gratuite pour vous ;
        elle est rémunérée à la mise en relation qualifiée avec l'agence.</p>`;
    $("#mer-envoi").addEventListener("click", () => {
      const mail = ($("#mer-mail").value || "").trim();
      $("#mer-note").textContent = mail.includes("@")
        ? "✓ Demande enregistrée (démonstration). Dans la version réelle, l'agence vous recontacte sous 48 h avec le dossier complet."
        : "Indiquez un e-mail valide pour être recontacté.";
    });
  });

  $("#voile").hidden = false;
  document.body.style.overflow = "hidden";
}

function fermerFiche() {
  $("#voile").hidden = true;
  document.body.style.overflow = "";
}

/* ---------------- chargement des données ---------------- */

async function rafraichir() {
  const reponse = await fetch("/api/annonces?" + lireFiltres().toString());
  const data = await reponse.json();
  etat.annonces = data.items;
  $("#compteur").textContent = `${data.total} bien${data.total > 1 ? "s" : ""} trouvé${data.total > 1 ? "s" : ""}`;
  rendreListe();
  rendreCarte();
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
        `${agences.length} agence${agences.length > 1 ? "s" : ""} · annonces réelles`;
    }
    const sel = $("#f-agence");
    for (const ag of agences) {
      const opt = document.createElement("option");
      opt.value = ag.agence;
      opt.textContent = `${ag.agence} (${ag.nb})`;
      sel.appendChild(opt);
    }
  } catch (e) { /* la page reste utilisable avec les valeurs par défaut */ }
  await chargerTerroirs();
  majAffichagesFiltres();
  await rafraichir();
}

/* ---------------- événements ---------------- */

const rafraichirDoucement = attenuer(rafraichir);
for (const id of ["#f-prix", "#f-temps", "#f-score"]) {
  $(id).addEventListener("input", () => { majAffichagesFiltres(); rafraichirDoucement(); });
}
for (const id of ["#f-terrain", "#f-agence", "#f-tri"]) $(id).addEventListener("change", rafraichir);
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
