"use strict";

const CONFIG = { owner: "IngSystemCix", repo: "transcriptor" };
const CACHE_KEY = "transcriptor-release";
const CACHE_TTL = 10 * 60 * 1000; // 10 minutos

const PLATFORMS = {
  windows: { label: "Windows", patterns: [/\.exe$/i] },
  macos: { label: "macOS", patterns: [/(macos|darwin).*\.zip$/i, /transcriptor.*\.zip$/i] },
  linux: { label: "Linux", patterns: [/linux.*\.tar\.gz$/i, /transcriptor.*\.tar\.gz$/i] },
};

const REPO = `https://github.com/${CONFIG.owner}/${CONFIG.repo}`;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

document.documentElement.classList.add("js");

$$("[data-repo]").forEach((a) => (a.href = REPO));
$$("[data-releases]").forEach((a) => (a.href = `${REPO}/releases`));
$$("[data-issues]").forEach((a) => (a.href = `${REPO}/issues`));
$$("[data-dl]").forEach((a) => (a.href = `${REPO}/releases/latest`));
$("#year").textContent = new Date().getFullYear();

function detectOS() {
  const ua = navigator.userAgent;
  if (/iPhone|iPad|Android/i.test(ua)) return null;
  const all = `${ua} ${navigator.userAgentData?.platform ?? navigator.platform ?? ""}`;
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

/* Animación de entrada */
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

/* Última release de GitHub */
const fmtSize = (bytes) => {
  const mb = bytes / 1_048_576;
  return `${mb.toFixed(mb < 100 ? 1 : 0)} MB`;
};

const findAsset = (assets, platformId) =>
  PLATFORMS[platformId].patterns
    .map((pattern) => assets.find((a) => pattern.test(a.name)))
    .find(Boolean);

async function getRelease() {
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY));
    if (cached && Date.now() - cached.time < CACHE_TTL) return cached.data;
  } catch {
    // Sin caché disponible.
  }

  const res = await fetch(`https://api.github.com/repos/${CONFIG.owner}/${CONFIG.repo}/releases/latest`, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error(`GitHub API ${res.status}`);
  const data = await res.json();

  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ time: Date.now(), data }));
  } catch {
    // Ignorar si sessionStorage no está disponible.
  }
  return data;
}

function markUnavailable(btn) {
  btn.removeAttribute("href");
  btn.setAttribute("aria-disabled", "true");
  btn.setAttribute("tabindex", "-1");
  btn.classList.add("is-disabled");
  const label = $("span", btn);
  if (label) label.textContent = "No disponible";
}

async function loadRelease() {
  try {
    const rel = await getRelease();
    $$("[data-version]").forEach((el) => {
      el.textContent = rel.tag_name || "Última versión";
    });

    for (const platformId of Object.keys(PLATFORMS)) {
      const card = $(`[data-platform="${platformId}"]`);
      const btn = $("[data-dl]", card);
      const asset = findAsset(rel.assets || [], platformId);

      if (!asset) {
        markUnavailable(btn);
        continue;
      }

      btn.href = asset.browser_download_url;
      $("[data-size]", card).textContent = fmtSize(asset.size || 0);

      const hash = (asset.digest || "").replace(/^sha256:/i, "");
      const copy = $("[data-copy]", card);
      if (hash && copy) {
        copy.dataset.hash = hash;
        copy.title = `SHA-256: ${hash}`;
        copy.hidden = false;
      }

      if (platformId === os) heroBtn.href = asset.browser_download_url;
    }
  } catch {
    // Si la API falla, se mantienen los enlaces a la página de releases.
  }
}

loadRelease();

/* Copiar SHA-256 */
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-copy]");
  if (!btn || !btn.dataset.hash) return;

  const status = $("#copy-status");
  const label = btn.lastChild;
  const original = label.textContent;
  try {
    await navigator.clipboard.writeText(btn.dataset.hash);
    status.textContent = "SHA-256 copiado al portapapeles";
    label.textContent = "¡Copiado!";
  } catch {
    status.textContent = "No se pudo copiar automáticamente";
    label.textContent = "No se pudo copiar";
  }
  setTimeout(() => (label.textContent = original), 2000);
});