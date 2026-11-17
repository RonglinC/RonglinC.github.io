const SNAPSHOT_URL = "./data/feed.json";
const PROXY_BUILDERS = [
  (url) => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
  (url) => `https://corsproxy.io/?${encodeURIComponent(url)}`,
];
const PAGE = 14;

const state = {
  items: [],
  sources: [],
  generatedAt: null,
  origin: "snapshot",
  category: "all",
  sourceId: "all",
  query: "",
  refreshing: false,
  selectedId: null,
  bloom: PAGE,
};

const els = {
  sky: document.getElementById("sky"),
  wrap: document.getElementById("sky-wrap"),
  links: document.getElementById("links"),
  orbits: document.getElementById("orbits"),
  hub: document.getElementById("hub"),
  hubCaption: document.getElementById("hub-caption"),
  updated: document.getElementById("updated"),
  count: document.getElementById("count"),
  origin: document.getElementById("origin"),
  refresh: document.getElementById("refresh"),
  search: document.getElementById("search"),
  install: document.getElementById("install"),
  offline: document.getElementById("offline"),
  sheet: document.getElementById("sheet"),
  sheetBody: document.getElementById("sheet-body"),
  sheetClose: document.getElementById("sheet-close"),
};

let deferredPrompt = null;
let didCenter = false;

function formatWhen(iso) {
  if (!iso) return "Date unknown";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Date unknown";
  const delta = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (delta < minute) return "Just now";
  if (delta < hour) return `${Math.floor(delta / minute)}m ago`;
  if (delta < day) return `${Math.floor(delta / hour)}h ago`;
  if (delta < 7 * day) return `${Math.floor(delta / day)}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function safeUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") return parsed.href;
  } catch {
    /* ignore */
  }
  return null;
}

function stripHtml(value) {
  const doc = new DOMParser().parseFromString(String(value || ""), "text/html");
  return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
}

function localName(node) {
  return (node.localName || node.nodeName || "").toLowerCase();
}

function childText(node, names) {
  const wanted = new Set(names);
  for (const child of node.children) {
    if (wanted.has(localName(child))) {
      const text = stripHtml(child.textContent);
      if (text) return text;
    }
  }
  return "";
}

function childLink(node) {
  for (const child of node.children) {
    if (localName(child) !== "link") continue;
    const href = child.getAttribute("href") || child.textContent.trim();
    const rel = (child.getAttribute("rel") || "alternate").toLowerCase();
    if (href && href.startsWith("http") && (rel === "alternate" || rel === "")) return href;
  }
  const guid = childText(node, ["guid", "id"]);
  return guid.startsWith("http") ? guid : "";
}

function parseDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function parseRssXml(xmlText, source) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("Invalid feed XML");
  const nodes = [...doc.querySelectorAll("item, entry")];
  return nodes.slice(0, 14).flatMap((node) => {
    const title = stripHtml(childText(node, ["title"]));
    const url = safeUrl(childLink(node));
    if (!title || !url) return [];
    let excerpt = stripHtml(childText(node, ["description", "summary", "content"]));
    if (excerpt.length > 280) excerpt = `${excerpt.slice(0, 277).replace(/\s+\S*$/, "")}…`;
    return [
      {
        id: `${source.id}:${url}`,
        title,
        url,
        sourceId: source.id,
        source: source.name,
        sourceHome: source.home,
        category: source.category,
        publishedAt: parseDate(childText(node, ["pubDate", "published", "updated", "date"])),
        excerpt,
      },
    ];
  });
}

async function fetchSnapshot() {
  const response = await fetch(`${SNAPSHOT_URL}?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Snapshot HTTP ${response.status}`);
  return response.json();
}

async function fetchViaProxy(url) {
  let lastError = null;
  for (const build of PROXY_BUILDERS) {
    try {
      const response = await fetch(build(url), { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const text = await response.text();
      if (!text.includes("<")) throw new Error("Proxy did not return XML");
      return text;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("All proxies failed");
}

function mergeItems(existing, incoming) {
  const map = new Map();
  for (const item of [...existing, ...incoming]) {
    const key = (item.url || "").split("#")[0].replace(/\/$/, "");
    if (!key || map.has(key)) continue;
    map.set(key, item);
  }
  return [...map.values()].sort((a, b) => {
    const av = a.publishedAt || "";
    const bv = b.publishedAt || "";
    if (av === bv) return 0;
    return av < bv ? 1 : -1;
  });
}

function visibleItems() {
  const query = state.query.trim().toLowerCase();
  return state.items.filter((item) => {
    if (state.category !== "all" && item.category !== state.category) return false;
    if (state.sourceId !== "all" && item.sourceId !== state.sourceId) return false;
    if (!query) return true;
    return `${item.title} ${item.excerpt} ${item.source}`.toLowerCase().includes(query);
  });
}

function polar(cx, cy, r, angle) {
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
}

function curve(x1, y1, x2, y2, lift = 28) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  return `M ${x1} ${y1} Q ${mx - (dy / len) * lift} ${my + (dx / len) * lift} ${x2} ${y2}`;
}

function ringLayout(count, cx, cy, radius, start, sweep, offset = 0) {
  const points = [];
  for (let i = 0; i < count; i += 1) {
    const t = count === 1 ? 0.5 : i / count;
    points.push(polar(cx, cy, radius, start + t * sweep + offset));
  }
  return points;
}

function metrics() {
  const mobile = window.innerWidth < 700;
  const size = mobile ? 920 : Math.max(1100, Math.min(window.innerWidth * 1.15, 1360));
  return {
    size,
    cx: size / 2,
    cy: size / 2,
    catR: mobile ? 168 : 210,
    seedR: mobile ? 112 : 138,
    story0: mobile ? 286 : 360,
    storyGap: mobile ? 132 : 158,
  };
}

function setPos(el, x, y, delay) {
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  el.style.setProperty("--delay", `${delay}ms`);
  el.style.animationDelay = `${delay}ms`;
}

function clearSkyNodes() {
  els.sky.querySelectorAll(".moon, .seed, .spark, .bloom, .empty-note").forEach((node) => node.remove());
}

function activeSources() {
  const items = visibleItems();
  const ids = new Set(items.map((item) => item.sourceId));
  return state.sources.filter((source) => {
    if (!ids.has(source.id)) return false;
    if (state.category !== "all" && source.category !== state.category) return false;
    return true;
  });
}

function renderSky() {
  const m = metrics();
  els.sky.style.width = `${m.size}px`;
  els.sky.style.height = `${m.size}px`;
  clearSkyNodes();

  const items = visibleItems();
  const shown = items.slice(0, state.bloom);
  const leftover = items.length - shown.length;
  els.count.textContent = `${items.length} spark${items.length === 1 ? "" : "s"}`;
  els.hubCaption.textContent =
    state.category === "all" ? "all the sparks" : state.category === "ai" ? "AI bloom" : "security bloom";

  const sec = polar(m.cx, m.cy, m.catR, (150 * Math.PI) / 180);
  const ai = polar(m.cx, m.cy, m.catR, (30 * Math.PI) / 180);
  const moons = [
    { id: "security", x: sec.x, y: sec.y, label: "Security", hint: "mint moon", face: "🛡️" },
    { id: "ai", x: ai.x, y: ai.y, label: "AI", hint: "lilac moon", face: "✦" },
  ];

  const paths = [];
  const orbits = [
    `<circle class="orbit" cx="${m.cx}" cy="${m.cy}" r="${m.catR}"></circle>`,
    `<circle class="orbit" cx="${m.cx}" cy="${m.cy}" r="${m.story0}"></circle>`,
    `<circle class="orbit ai" cx="${m.cx}" cy="${m.cy}" r="${m.story0 + m.storyGap}"></circle>`,
  ];

  moons.forEach((moon, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `moon ${moon.id}`;
    btn.dataset.cat = moon.id;
    btn.setAttribute("aria-pressed", String(state.category === moon.id));
    btn.innerHTML = `<span>${moon.face}</span><b>${moon.label}</b><small>${moon.hint}</small>`;
    setPos(btn, moon.x, moon.y, 80 + index * 60);
    els.sky.append(btn);
    paths.push(
      `<path d="${curve(m.cx, m.cy, moon.x, moon.y, 18)}" fill="none" stroke="${
        moon.id === "ai" ? "rgba(199,166,222,.7)" : "rgba(95,183,176,.75)"
      }" stroke-width="2.4"></path>`
    );
  });

  const seeds = activeSources().slice(0, 10);
  const seedStart = state.category === "ai" ? -0.4 : state.category === "security" ? 2.2 : -0.2;
  const seedSweep = state.category === "all" ? Math.PI * 1.6 : Math.PI * 0.9;
  ringLayout(seeds.length, m.cx, m.cy, m.seedR, seedStart, seedSweep).forEach((point, index) => {
    const source = seeds[index];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `seed ${source.category}`;
    btn.dataset.source = source.id;
    btn.title = source.name;
    btn.setAttribute("aria-pressed", String(state.sourceId === source.id));
    btn.textContent = source.name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .slice(0, 3);
    setPos(btn, point.x, point.y, 140 + index * 30);
    els.sky.append(btn);
    paths.push(
      `<path d="${curve(m.cx, m.cy, point.x, point.y, 10)}" fill="none" stroke="rgba(126,191,179,.35)" stroke-width="1.4"></path>`
    );
  });

  const start =
    state.category === "security" ? Math.PI * 0.55 : state.category === "ai" ? -Math.PI * 0.55 : -Math.PI / 2;
  const sweep = state.category === "all" ? Math.PI * 2 : Math.PI * 1.15;
  const origin = state.category === "ai" ? ai : state.category === "security" ? sec : { x: m.cx, y: m.cy };

  const positions = [];
  let placed = 0;
  let ring = 0;
  while (placed < shown.length) {
    const take = Math.min(shown.length - placed, 8 + ring * 4);
    const radius = m.story0 + ring * m.storyGap;
    const pts = ringLayout(take, m.cx, m.cy, radius, start, sweep, ring * 0.16);
    pts.forEach((point) => positions.push(point));
    placed += take;
    ring += 1;
  }

  shown.forEach((item, index) => {
    const point = positions[index];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `spark ${item.category === "ai" ? "ai" : "security"}`;
    btn.dataset.story = item.id;
    btn.setAttribute("aria-pressed", String(state.selectedId === item.id));
    const eyebrow = document.createElement("div");
    eyebrow.className = "eyebrow";
    const cat = document.createElement("span");
    cat.textContent = item.category === "ai" ? "AI" : "Sec";
    const when = document.createElement("span");
    when.textContent = formatWhen(item.publishedAt);
    eyebrow.append(cat, when);
    const title = document.createElement("strong");
    title.textContent = item.title;
    btn.append(eyebrow, title);
    setPos(btn, point.x, point.y, 180 + index * 18);
    els.sky.append(btn);
    const stroke = item.category === "ai" ? "rgba(199,166,222,.55)" : "rgba(95,183,176,.5)";
    paths.push(
      `<path d="${curve(origin.x, origin.y, point.x, point.y, 36)}" fill="none" stroke="${stroke}" stroke-width="1.6"></path>`
    );
  });

  if (leftover > 0) {
    const extra = polar(m.cx, m.cy, m.story0 + ring * m.storyGap, start + sweep * 0.5);
    const more = document.createElement("button");
    more.type = "button";
    more.className = "bloom";
    more.dataset.more = "1";
    more.textContent = `+${Math.min(leftover, PAGE)}`;
    more.title = "Bloom more stories";
    setPos(more, extra.x, extra.y, 220);
    els.sky.append(more);
  }

  if (!shown.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = state.items.length ? "No sparks match that hunt." : "The sky is quiet. Try Refresh.";
    els.sky.append(note);
  }

  els.links.innerHTML = paths.join("");
  els.orbits.innerHTML = orbits.join("");
  setPos(els.hub, m.cx, m.cy, 0);

  if (!didCenter) {
    requestAnimationFrame(centerHub);
    didCenter = true;
  }
}

function centerHub() {
  const hub = els.hub;
  els.wrap.scrollTo({
    left: hub.offsetLeft - els.wrap.clientWidth / 2 + hub.offsetWidth / 2,
    top: hub.offsetTop - els.wrap.clientHeight / 2 + hub.offsetHeight / 2,
    behavior: "smooth",
  });
}

function openSheet(item) {
  state.selectedId = item.id;
  const url = safeUrl(item.url);
  els.sheet.hidden = false;
  els.sheetBody.replaceChildren();
  const pill = document.createElement("span");
  pill.className = `pill ${item.category === "ai" ? "ai" : "security"}`;
  pill.textContent = item.category === "ai" ? "AI spark" : "Security spark";
  const title = document.createElement("h2");
  title.textContent = item.title;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${item.source} · ${formatWhen(item.publishedAt)}`;
  els.sheetBody.append(pill, title, meta);
  if (item.excerpt) {
    const excerpt = document.createElement("p");
    excerpt.textContent = item.excerpt;
    els.sheetBody.append(excerpt);
  }
  if (url) {
    const go = document.createElement("a");
    go.className = "go";
    go.href = url;
    go.target = "_blank";
    go.rel = "noopener noreferrer";
    go.textContent = "Read at the source →";
    els.sheetBody.append(go);
  }
  renderSky();
}

function closeSheet() {
  state.selectedId = null;
  els.sheet.hidden = true;
  els.sheetBody.replaceChildren();
}

function renderStatus() {
  els.updated.textContent = state.generatedAt ? `Updated ${formatWhen(state.generatedAt)}` : "Not yet";
  els.origin.textContent = state.origin === "live" ? "Live bloom" : "Same-origin snapshot";
  els.offline.hidden = navigator.onLine;
  els.refresh.disabled = state.refreshing;
  els.refresh.textContent = state.refreshing ? "Blooming…" : "Refresh";
}

function render() {
  renderSky();
  renderStatus();
}

function applyPayload(payload, origin) {
  state.sources = payload.sources || [];
  state.items = mergeItems([], payload.items || []);
  state.generatedAt = payload.generatedAt || new Date().toISOString();
  state.origin = origin;
  try {
    localStorage.setItem("pulse-news-cache", JSON.stringify(payload));
  } catch {
    /* ignore quota */
  }
  render();
}

async function refreshLive() {
  if (!state.sources.length) return;
  state.refreshing = true;
  renderStatus();
  const results = await Promise.allSettled(
    state.sources.map(async (source) => parseRssXml(await fetchViaProxy(source.feed), source))
  );
  const liveItems = results.flatMap((result) => (result.status === "fulfilled" ? result.value : []));
  if (liveItems.length) {
    state.items = mergeItems(state.items, liveItems);
    state.generatedAt = new Date().toISOString();
    state.origin = "live";
    try {
      localStorage.setItem(
        "pulse-news-cache",
        JSON.stringify({ generatedAt: state.generatedAt, sources: state.sources, items: state.items })
      );
    } catch {
      /* ignore */
    }
  }
  state.refreshing = false;
  render();
  if (!liveItems.length) els.origin.textContent = "Snapshot (live RSS blocked)";
}

async function boot() {
  els.hubCaption.textContent = "gathering sparks";
  try {
    applyPayload(await fetchSnapshot(), "snapshot");
  } catch (error) {
    try {
      const cached = JSON.parse(localStorage.getItem("pulse-news-cache") || "null");
      if (cached?.items?.length) {
        applyPayload(cached, "snapshot");
        els.origin.textContent = "Offline cache";
      } else {
        throw error;
      }
    } catch {
      els.hubCaption.textContent = "could not load";
    }
  }

  if (navigator.onLine && state.sources.length) {
    refreshLive().catch(() => {
      state.refreshing = false;
      renderStatus();
    });
  }
}

els.sky.addEventListener("click", (event) => {
  const moon = event.target.closest("[data-cat]");
  if (moon) {
    const next = moon.dataset.cat;
    state.category = state.category === next ? "all" : next;
    state.sourceId = "all";
    state.bloom = PAGE;
    closeSheet();
    didCenter = false;
    render();
    return;
  }
  const seed = event.target.closest("[data-source]");
  if (seed) {
    const next = seed.dataset.source;
    state.sourceId = state.sourceId === next ? "all" : next;
    state.bloom = PAGE;
    render();
    return;
  }
  const more = event.target.closest("[data-more]");
  if (more) {
    state.bloom += PAGE;
    render();
    return;
  }
  const spark = event.target.closest("[data-story]");
  if (spark) {
    const item = state.items.find((row) => row.id === spark.dataset.story);
    if (item) openSheet(item);
  }
});

els.hub.addEventListener("click", (event) => {
  event.stopPropagation();
  state.category = "all";
  state.sourceId = "all";
  state.bloom = PAGE;
  state.query = "";
  els.search.value = "";
  closeSheet();
  didCenter = false;
  render();
});


els.search.addEventListener("input", () => {
  state.query = els.search.value;
  state.bloom = PAGE;
  renderSky();
  renderStatus();
});

els.refresh.addEventListener("click", () => refreshLive());
els.sheetClose.addEventListener("click", () => {
  closeSheet();
  renderSky();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeSheet();
    renderSky();
  }
});

window.addEventListener("resize", () => {
  didCenter = false;
  renderSky();
});
window.addEventListener("online", () => {
  els.offline.hidden = true;
});
window.addEventListener("offline", () => {
  els.offline.hidden = false;
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event;
  els.install.hidden = false;
});

els.install.addEventListener("click", async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  els.install.hidden = true;
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {
    /* PWA optional */
  });
}

boot();
