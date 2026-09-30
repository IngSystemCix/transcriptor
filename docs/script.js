"use strict";

/* ── Configuración: cambia solo esto si renombras el repositorio ── */
const CONFIG = { owner: "IngSystemCix", repo: "transcriptor" };

/* Cómo reconocer, dentro de la Release, el archivo de cada sistema (ver deploy.yaml) */
const PLATFORMS = {
  windows: { label: "Windows", pattern: /\.exe$/i },
  macos: { label: "macOS", pattern: /macos.*\.zip$/i },
  linux: { label: "Linux", pattern: /linux.*\.tar\.gz$/i },
};

const REPO = `https://github.com/${CONFIG.owner}/${CONFIG.repo}`;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

document.documentElement.classList.add("js");

/* Enlaces al repositorio (una sola fuente de verdad) */
$$("[data-repo]").forEach((a) => (a.href = REPO));
$$("[data-releases]").forEach((a) => (a.href = `${REPO}/releases`));
$$("[data-issues]").forEach((a) => (a.href = `${REPO}/issues`));
$$("[data-dl]").forEach((a) => (a.href = `${REPO}/releases/latest`));
$("#year").textContent = new Date().getFullYear();

/* Sistema del visitante */
function detectOS() {
  const ua = navigator.userAgent;
  const all = `${ua} ${navigator.userAgentData?.platform ?? navigator.platform ?? ""}`;
  if (/iPhone|iPad|Android/i.test(ua)) return null; // móviles: no hay versión
  if (/Win/i.test(all)) return "windows";
  if (/Mac/i.test(all)) return "macos";
  if (/Linux|X11/i.test(all)) return "linux";
  return null;
}
const os = detectOS();
const heroBtn = $("[data-hero-download]");
if (os) {
  $("[data-os-label]").textContent = `Descargar para ${PLATFORMS[os].label}`;
  const card = $(`[data-platform="${os}"]`);
  card.classList.add("rec");
  $(".badge", card).hidden = false;
}

/* Menú móvil */
const burger = $(".burger");
const nav = $("#nav");
const closeNav = () => {
  nav.classList.remove("open");
  burger.setAttribute("aria-expanded", "false");
  burger.setAttribute("aria-label", "Abrir menú");
};
burger.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  burger.setAttribute("aria-expanded", String(open));
  burger.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
});
nav.addEventListener("click", (e) => e.target.closest("a") && closeNav());
document.addEventListener("keydown", (e) => e.key === "Escape" && closeNav());

/* Aparición al hacer scroll */
const items = $$(".reveal");
if ("IntersectionObserver" in window) {
  const io = new IntersectionObserver(
    (entries) =>
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      }),
    { threshold: 0.12 }
  );
  items.forEach((el) => io.observe(el));
} else {
  items.forEach((el) => el.classList.add("in"));
}

/* Última release desde la API de GitHub (con caché de sesión) */
const fmtSize = (bytes) => `${(bytes / 1_048_576).toFixed(0)} MB`;

async function getRelease() {
  const key = "transcriptor-release";
  try {
    const cached = JSON.parse(sessionStorage.getItem(key));
    if (cached) return cached;
  } catch {
    /* sin caché disponible */
  }
  const res = await fetch(`https://api.github.com/repos/${CONFIG.owner}/${CONFIG.repo}/releases/latest`, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error(`GitHub API ${res.status}`);
  const data = await res.json();
  try {
    sessionStorage.setItem(key, JSON.stringify(data));
  } catch {
    /* ignorar */
  }
  return data;
}

function markUnavailable(btn) {
  btn.removeAttribute("href");
  btn.setAttribute("aria-disabled", "true");
  btn.classList.add("is-disabled");
  $("span", btn).textContent = "No disponible en esta versión";
}

async function loadRelease() {
  try {
    const rel = await getRelease();
    $$("[data-version]").forEach((el) => (el.textContent = rel.tag_name));

    for (const [id, { pattern }] of Object.entries(PLATFORMS)) {
      const card = $(`[data-platform="${id}"]`);
      const btn = $("[data-dl]", card);
      const asset = rel.assets.find((a) => pattern.test(a.name));
      if (!asset) {
        markUnavailable(btn);
        continue;
      }
      btn.href = asset.browser_download_url;
      $("[data-size]", card).textContent = fmtSize(asset.size);
      const hash = asset.digest?.replace(/^sha256:/, "");
      if (hash) {
        const copy = $("[data-copy]", card);
        copy.dataset.hash = hash;
        copy.hidden = false;
      }
      if (id === os) heroBtn.href = asset.browser_download_url;
    }
  } catch {
    /* Sin conexión o límite de la API: se mantienen los enlaces a /releases/latest */
  }
}
loadRelease();

/* Botón principal sin versión disponible: lleva a la sección de descargas */
heroBtn.addEventListener("click", () => closeNav());

/* Copiar SHA-256 */
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-copy]");
  if (!btn) return;
  const status = $("#copy-status");
  try {
    await navigator.clipboard.writeText(btn.dataset.hash);
    status.textContent = "SHA-256 copiado al portapapeles";
  } catch {
    status.textContent = "No se pudo copiar automáticamente";
  }
});