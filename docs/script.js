"use strict";

const CONFIG = { owner: "IngSystemCix", repo: "transcriptor" };

const PLATFORMS = {
  windows: {
    label: "Windows",
    patterns: [/\.exe$/i, /windows.*\.exe$/i, /transcriptor.*\.exe$/i],
  },
  macos: {
    label: "macOS",
    patterns: [/macos.*\.zip$/i, /darwin.*\.zip$/i, /transcriptor.*\.zip$/i],
  },
  linux: {
    label: "Linux",
    patterns: [/linux.*\.tar\.gz$/i, /ubuntu.*\.tar\.gz$/i, /transcriptor.*\.tar\.gz$/i],
  },
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
  const all = `${ua} ${navigator.userAgentData?.platform ?? navigator.platform ?? ""}`;
  if (/iPhone|iPad|Android/i.test(ua)) return null;
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

const fmtSize = (bytes) => `${(bytes / 1_048_576).toFixed(0)} MB`;

function findAsset(assets, platformId) {
  const { patterns } = PLATFORMS[platformId];
  return assets.find((asset) => patterns.some((pattern) => pattern.test(asset.name)));
}

async function getRelease() {
  const key = "transcriptor-release";
  try {
    const cached = JSON.parse(sessionStorage.getItem(key));
    if (cached) return cached;
  } catch {
    // Sin caché disponible.
  }

  const res = await fetch(`https://api.github.com/repos/${CONFIG.owner}/${CONFIG.repo}/releases/latest`, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error(`GitHub API ${res.status}`);
  const data = await res.json();

  try {
    sessionStorage.setItem(key, JSON.stringify(data));
  } catch {
    // Ignorar si localStorage no está disponible.
  }
  return data;
}

function markUnavailable(btn) {
  btn.removeAttribute("href");
  btn.setAttribute("aria-disabled", "true");
  btn.classList.add("is-disabled");
  const label = $("span", btn);
  if (label) label.textContent = "No disponible";
}

async function loadRelease() {
  try {
    const rel = await getRelease();
    $$('[data-version]').forEach((el) => {
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
        copy.hidden = false;
      }

      if (platformId === os) heroBtn.href = asset.browser_download_url;
    }
  } catch {
    // Si la API falla, se mantienen los enlaces generales a la página de releases.
  }
}

loadRelease();

heroBtn.addEventListener("click", () => closeNav());

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-copy]");
  if (!btn || !btn.dataset.hash) return;

  const status = $("#copy-status");
  try {
    await navigator.clipboard.writeText(btn.dataset.hash);
    status.textContent = "SHA-256 copiado al portapapeles";
  } catch {
    status.textContent = "No se pudo copiar automáticamente";
  }
});