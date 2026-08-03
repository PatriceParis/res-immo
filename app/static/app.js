/* Refuge Immo — logique de l'interface (vanilla JS, aucune dépendance à installer). */
"use strict";

const $ = (sel) => document.querySelector(sel);

const etat = { annonces: [], carte: null, calque: null, cadre: false };

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
  $("#f-tri").value = "score";
  document.querySelectorAll(".atouts input").forEach((c) => (c.checked = false));
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
    <div class="fiche-haut">
      <div class="score-jeton ${niveau}" title="Score de résilience">${Math.round(a.score_total)}<small>/100</small></div>
      <div>
        <h3>${echap(a.titre)}</h3>
        <div class="lieu">${echap(a.commune || "")} · ${echap(a.departement || "")} · 🚗 ${fmtTemps(a.temps_voiture_min)} de Paris</div>
        <div class="classe">${echap((a.score_detail && a.score_detail.classe) || "")}</div>
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

function jaugesPiliers(detail) {
  if (!detail || !detail.piliers) return "";
  return Object.values(detail.piliers).map((p) => `
    <div class="pilier">
      <span class="nom">${echap(p.libelle)}</span>
      <div class="jauge" role="meter" aria-valuemin="0" aria-valuemax="${p.max}"
           aria-valuenow="${p.points}" aria-label="${echap(p.libelle)}">
        <div style="width:${Math.min(100, (p.points / p.max) * 100)}%"></div>
      </div>
      <span class="valeur">${p.points}/${p.max}</span>
    </div>`).join("");
}

function ouvrirFiche(id) {
  const a = etat.annonces.find((x) => x.id === id);
  if (!a) return;
  const niveau = niveauScore(a.score_total);
  const badges = (a.badges || []).map((b) => `<span class="badge">✓ ${echap(b)}</span>`).join("");
  const alertes = (a.alertes || []).map((al) => `<span class="alerte">⚠ ${echap(al)}</span>`).join("");
  const prixM2 = a.prix && a.surface_m2 ? Math.round(a.prix / a.surface_m2) : null;
  const risques = a.risques || {};
  const nucleaire = risques.nucleaire_km != null
    ? `Centrale nucléaire la plus proche : ${echap(risques.nucleaire_nom || "")} à ${Math.round(risques.nucleaire_km)} km.` : "";

  $("#modale-contenu").innerHTML = `
    <div class="fiche-haut">
      <div class="score-jeton ${niveau}">${Math.round(a.score_total)}<small>/100</small></div>
      <div>
        <h2 id="modale-titre">${echap(a.titre)}</h2>
        <div class="lieu">${echap(a.commune || "")} (${echap(a.code_postal || "")}) · ${echap(a.departement || "")}
          · 🚗 ${fmtTemps(a.temps_voiture_min)} de Paris (~${a.distance_km ? Math.round(a.distance_km * 1.25) : "?"} km)</div>
      </div>
    </div>
    <div class="rangee-prix">
      <span class="prix">${a.prix ? fmtEuros.format(a.prix) : "Prix n.c."}</span>
      ${prixM2 ? `<span>${fmtNombre.format(prixM2)} €/m²</span>` : ""}
      <span>${a.surface_m2 ? fmtNombre.format(a.surface_m2) + " m² habitables" : ""}</span>
      <span>${a.terrain_m2 ? "terrain de " + fmtNombre.format(a.terrain_m2) + " m²" : ""}</span>
      <span>${a.dpe ? "DPE " + echap(a.dpe) : ""}</span>
    </div>

    <h4>Score de résilience — ${echap((a.score_detail && a.score_detail.classe) || "")}</h4>
    ${jaugesPiliers(a.score_detail)}

    ${badges ? `<h4>Atouts détectés</h4><div class="jetons">${badges}</div>` : ""}
    ${alertes ? `<h4>Points de vigilance</h4><div class="jetons">${alertes}</div>` : ""}
    ${nucleaire ? `<p class="source-ligne">${nucleaire}</p>` : ""}

    <h4>L'annonce</h4>
    <p class="description">${echap(a.description)}</p>
    <p class="source-ligne">Source : ${echap(a.source)}${a.url
      ? ` — <a href="${echap(a.url)}" target="_blank" rel="noopener">voir l'annonce d'origine</a>`
      : " (bien fictif, jeu de démonstration)"}</p>`;
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
      const plafond = Math.ceil(meta.prix_max / 50000) * 50000;
      $("#f-prix").max = plafond;
      $("#f-prix").value = plafond;
    }
    const sources = (meta.sources || []).filter(Boolean);
    if (sources.length && !(sources.length === 1 && sources[0] === "démo")) {
      $("#bandeau-source").textContent = "sources : " + sources.join(", ");
    }
  } catch (e) { /* la page reste utilisable avec les valeurs par défaut */ }
  majAffichagesFiltres();
  await rafraichir();
}

/* ---------------- événements ---------------- */

const rafraichirDoucement = attenuer(rafraichir);
for (const id of ["#f-prix", "#f-temps", "#f-score"]) {
  $(id).addEventListener("input", () => { majAffichagesFiltres(); rafraichirDoucement(); });
}
for (const id of ["#f-terrain", "#f-tri"]) $(id).addEventListener("change", rafraichir);
document.querySelectorAll(".atouts input").forEach((c) => c.addEventListener("change", rafraichir));
$("#f-reinit").addEventListener("click", reinitialiser);

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

initialiser();
