"use strict";

const MELBOURNE_CBD = [-37.8136, 144.9631];
const DEFAULT_ZOOM = 11;
const USER_ZOOM = 13;
const STATUS_FADE_MS = 4000;

const statusEl = document.getElementById("status");
let statusTimer = null;

function showStatus(text, sticky = false) {
  statusEl.textContent = text;
  statusEl.hidden = false;
  if (statusTimer) clearTimeout(statusTimer);
  if (!sticky) {
    statusTimer = setTimeout(() => { statusEl.hidden = true; }, STATUS_FADE_MS);
  }
}

const map = L.map("map", {
  center: MELBOURNE_CBD,
  zoom: DEFAULT_ZOOM,
  zoomControl: false,
  attributionControl: true,
});

L.control.zoom({ position: "bottomright" }).addTo(map);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &middot; ' +
    'Data: <a href="https://www.health.vic.gov.au/food-safety/food-safety-register-of-convictions" target="_blank" rel="noopener">Vic Food Safety Register</a> (CC BY 4.0)',
}).addTo(map);

const warningIcon = L.divIcon({
  className: "warning-marker-wrapper",
  html: '<div class="warning-marker" aria-hidden="true"></div>',
  iconSize: [36, 36],
  iconAnchor: [18, 18],
  popupAnchor: [0, -16],
});

const userIcon = L.divIcon({
  className: "user-dot-wrapper",
  html: '<div class="user-dot" aria-hidden="true"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-AU", { day: "numeric", month: "long", year: "numeric" });
}

function popupHtml(c) {
  const rows = [
    ["Date", formatDate(c.date)],
    ["Court", c.court],
    ["Decision", c.decision],
    ["Sentence", c.sentence],
    ["Prosecutor", c.prosecutor],
    ["Convicted", c.convicted],
  ].filter(([, v]) => v);

  const dl = rows
    .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`)
    .join("");

  const offence = c.offence
    ? `<details><summary>Offence details</summary><p class="offence-text">${escapeHtml(c.offence)}</p></details>`
    : "";

  const source = c.source_url
    ? `<a class="source" href="${escapeHtml(c.source_url)}" target="_blank" rel="noopener">View on official register &rarr;</a>`
    : "";

  return `
    <div class="popup">
      <h3>${escapeHtml(c.name || "Unknown business")}</h3>
      <p class="address">${escapeHtml(c.address)}</p>
      <dl>${dl}</dl>
      ${offence}
      ${source}
    </div>
  `;
}

async function loadConvictions() {
  showStatus("Loading conviction data…", true);
  let data;
  try {
    const r = await fetch("convictions.json", { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    data = await r.json();
  } catch (e) {
    showStatus(`Failed to load data: ${e.message}`, true);
    return;
  }

  const group = L.featureGroup();
  for (const c of data) {
    if (typeof c.lat !== "number" || typeof c.lng !== "number") continue;
    const m = L.marker([c.lat, c.lng], {
      icon: warningIcon,
      title: c.name || c.address,
      alt: `Conviction: ${c.name || c.address}`,
    });
    m.bindPopup(popupHtml(c), { maxWidth: 360, autoPan: true });
    group.addLayer(m);
  }
  group.addTo(map);

  showStatus(`${data.length} conviction${data.length === 1 ? "" : "s"} loaded`);
}

function locateUser() {
  if (!("geolocation" in navigator)) {
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;
      L.marker([latitude, longitude], { icon: userIcon, interactive: false, keyboard: false }).addTo(map);
      map.setView([latitude, longitude], USER_ZOOM, { animate: true });
    },
    (err) => {
      const reason = err.code === err.PERMISSION_DENIED ? "permission denied" : err.message;
      showStatus(`Location unavailable (${reason}). Showing Melbourne overview.`);
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 60_000 },
  );
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch((e) => {
      console.warn("Service worker registration failed:", e);
    });
  });
}

loadConvictions();
locateUser();
