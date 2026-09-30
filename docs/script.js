"use strict";

/* ── Configuración: cambia solo esto si renombras el repositorio o el archivo ── */
const CONFIG = {
  owner: "IngSystemCix",
  repo: "transcriptor",
  asset: "Transcriptor.exe", // nombre del archivo subido a la Release
};

const REPO = `https://github.com/${CONFIG.owner}/${CONFIG.repo}`;
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const setText = (attr, value) => $$(`[data-${attr}]`).forEach((el) => (el.textContent = value));

document.documentElement.classList.add("js");

/* Enlaces al repositorio (una sola fuente de verdad) */
$$("[data-repo]").forEach((a) => (a.href = REPO));
$$("[data-releases]").forEach((a) => (a.href = `${REPO}/releases`));
$$("[data-issues]").forEach((a) => (a.href = `${REPO}/issues`));
$$("[data-download]").forEach((a) => (a.href = `${REPO}/releases/latest`));
$("#year").textContent = new Date().getFullYear();

/* Aviso si no es Windows */
if (!/Windows/i.test(navigator.userAgent)) $("#os-note").hidden = false;

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
const fmtDate = (iso) =>
  new Intl.DateTimeFormat("es", { day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));

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

async function loadRelease() {
  try {
    const rel = await getRelease();
    const asset = rel.assets.find((a) => a.name === CONFIG.asset) || rel.assets.find((a) => a.name.endsWith(".exe"));
    setText("version", rel.tag_name);
    setText("date", fmtDate(rel.published_at));
    if (!asset) return;
    $$("[data-download]").forEach((a) => (a.href = asset.browser_download_url));
    setText("size", fmtSize(asset.size));
    setText("downloads", asset.download_count.toLocaleString("es"));
    const hash = asset.digest?.replace(/^sha256:/, "");
    if (hash) {
      setText("hash", hash);
      $("#hash-row").hidden = false;
    }
  } catch {
    /* Sin conexión o límite de la API: se mantienen los enlaces a /releases/latest */
  }
}
loadRelease();

/* Copiar SHA-256 */
$("#copy-hash").addEventListener("click", async () => {
  const status = $("#copy-status");
  try {
    await navigator.clipboard.writeText($("[data-hash]").textContent);
    status.textContent = "SHA-256 copiado al portapapeles";
  } catch {
    status.textContent = "No se pudo copiar automáticamente";
  }
});