const SNAPSHOT_URL = "./data/feed.json";
const PROXY_BUILDERS = [
  (url) => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
  (url) => `https://corsproxy.io/?${encodeURIComponent(url)}`,
];
const PAGE = 12;
const CVE_RE = /CVE-\d{4}-\d{4,7}/gi;
const VENDORS = [
  ["Microsoft", /\b(microsoft|azure|entra|defender|windows|m365|office 365|active directory)\b/i],
  ["Amazon Web Services", /\b(aws|amazon web services|amazon s3)\b/i],
  ["Google", /\b(google cloud|gcp|google chrome|android)\b/i],
  ["CrowdStrike", /\bcrowdstrike\b|\bfalcon\b/i],
  ["SentinelOne", /\bsentinelone\b/i],
  ["Palo Alto Networks", /\bpalo alto\b|\bunit 42\b/i],
  ["Cisco", /\bcisco\b|\btalos\b/i],
  ["Fortinet", /\bfortinet\b|\bfortigate\b/i],
  ["Okta", /\bokta\b/i],
  ["Cloudflare", /\bcloudflare\b/i],
  ["Apple", /\b(apple|ios|macos|iphone)\b/i],
  ["Linux", /\b(linux|kernel)\b/i],
  ["Kubernetes", /\b(kubernetes|k8s)\b/i],
  ["GitHub", /\bgithub\b/i],
  ["OpenAI", /\bopenai\b|\bchatgpt\b/i],
  ["Ivanti", /\bivanti\b/i],
  ["Citrix", /\bcitrix\b|\bnetscaler\b/i],
  ["VMware", /\bvmware\b/i],
  ["Snowflake", /\bsnowflake\b/i],
  ["Wiz", /\bwiz\b/i],
  ["Elastic", /\belastic(search)?\b/i],
  ["Splunk", /\bsplunk\b/i],
];
const TOPICS = [
  ["vuln", /\b(cve-\d{4}-\d+|vulnerabilit|zero-?day|n-day|rce|advisory|patch tuesday|exploit)\b/i],
  ["ransomware", /\bransomware\b|\bextortion\b/i],
  ["phishing", /\bphish|\bcredential theft\b/i],
  ["endpoint", /\b(edr|xdr|endpoint|malware|trojan|backdoor)\b/i],
  ["cloud", /\b(cloud|aws|gcp|kubernetes|container|s3 bucket)\b/i],
  ["azure", /\b(azure|entra|m365|office 365|active directory)\b/i],
  ["finance", /\b(bank|banking|swift|atm|payment card|pci|fintech|wire fraud)\b/i],
  ["identity", /\b(identity|iam|mfa|sso|okta|entra id)\b/i],
  ["detection", /\b(detection|siem|sigma|yara|telemetry|hunt)\b/i],
  ["ai", /\b(llm|generative ai|machine learning|chatgpt|openai)\b/i],
];

const state = {
  items: [],
  sources: [],
  generatedAt: null,
  origin: "snapshot",
  topic: "all",
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
  hub: document.getElementById("hub"),
  hubCaption: document.getElementById("hub-caption"),
  status: document.getElementById("status"),
  refresh: document.getElementById("refresh"),
  search: document.getElementById("search"),
  searchClear: document.getElementById("search-clear"),
  searchForm: document.getElementById("search-form"),
  searchHints: document.getElementById("search-hints"),
  topics: document.getElementById("topics"),
  sourceFilter: document.getElementById("source-filter"),
  install: document.getElementById("install"),
  sheet: document.getElementById("sheet"),
  sheetBody: document.getElementById("sheet-body"),
  sheetClose: document.getElementById("sheet-close"),
};

let deferredPrompt = null;
let didCenter = false;

function unique(list) {
  return [...new Set(list.filter(Boolean))];
}

function intersect(a = [], b = []) {
  const set = new Set(b);
  return a.filter((value) => set.has(value));
}

function formatWhen(iso) {
  if (!iso) return "date unknown";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "date unknown";
  const delta = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (delta < minute) return "just now";
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

function extractSignals(item) {
  const text = `${item.title || ""} ${item.excerpt || ""}`;
  const cves = unique((text.match(CVE_RE) || []).map((value) => value.toUpperCase()).concat(item.cves || []));
  const vendors = unique([
    ...(item.vendors || []),
    ...VENDORS.filter(([, pattern]) => pattern.test(text)).map(([name]) => name),
  ]);
  const topics = unique([
    item.category,
    ...(item.topics || []),
    ...TOPICS.filter(([, pattern]) => pattern.test(text)).map(([name]) => name),
  ]);
  return { ...item, cves, vendors, topics };
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
  return [...doc.querySelectorAll("item, entry")].slice(0, 8).flatMap((node) => {
    const title = stripHtml(childText(node, ["title"]));
    const url = safeUrl(childLink(node));
    if (!title || !url) return [];
    let excerpt = stripHtml(childText(node, ["description", "summary", "content"]));
    if (excerpt.length > 280) excerpt = `${excerpt.slice(0, 277).replace(/\s+\S*$/, "")}…`;
    return [
      extractSignals({
        id: `${source.id}:${url}`,
        title,
        url,
        sourceId: source.id,
        source: source.name,
        sourceHome: source.home,
        category: source.category,
        publishedAt: parseDate(childText(node, ["pubDate", "published", "updated", "date"])),
        excerpt,
      }),
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
  for (const raw of [...existing, ...incoming]) {
    const item = extractSignals(raw);
    const key = (item.url || "").split("#")[0].replace(/\/$/, "");
    if (!key || map.has(key)) continue;
    map.set(key, item);
  }
  return [...map.values()].sort((a, b) => (b.publishedAt || "").localeCompare(a.publishedAt || ""));
}

function matchesQuery(item, query) {
  if (!query) return true;
  const hay = `${item.title} ${item.excerpt} ${item.source} ${(item.cves || []).join(" ")} ${(item.vendors || []).join(" ")} ${(item.topics || []).join(" ")}`.toLowerCase();
  return query.split(/\s+/).filter(Boolean).every((part) => hay.includes(part));
}

function filteredItems() {
  return state.items.filter((item) => {
    if (state.topic !== "all" && item.category !== state.topic && !(item.topics || []).includes(state.topic)) {
      return false;
    }
    if (state.sourceId !== "all" && item.sourceId !== state.sourceId) return false;
    return matchesQuery(item, state.query.trim().toLowerCase());
  });
}

function strongestLink(a, b) {
  const cves = intersect(a.cves, b.cves);
  if (cves.length) return { kind: "cve", label: cves[0], weight: 4 };
  const vendors = intersect(a.vendors, b.vendors);
  if (vendors.length) return { kind: "vendor", label: vendors[0], weight: 3 };
  if (a.sourceId && a.sourceId === b.sourceId) return { kind: "source", label: a.source, weight: 2 };
  const topics = intersect(a.topics, b.topics).filter((topic) => topic !== "security");
  if (topics.length) return { kind: "topic", label: topics[0], weight: 1 };
  return null;
}

function relationsFor(item, pool) {
  return pool
    .filter((other) => other.id !== item.id)
    .map((other) => {
      const link = strongestLink(item, other);
      return link ? { item: other, ...link } : null;
    })
    .filter(Boolean)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 8);
}

function polar(cx, cy, r, angle) {
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
}

function escapeXml(value) {
  return String(value).replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}

function curve(x1, y1, x2, y2) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const cx = mx - (dy / len) * 28;
  const cy = my + (dx / len) * 28;
  return { d: `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`, lx: cx, ly: cy };
}

function metrics() {
  const mobile = window.innerWidth < 700;
  const size = mobile ? 980 : Math.max(1180, Math.min(window.innerWidth * 1.2, 1400));
  return { size, cx: size / 2, cy: size / 2, r0: mobile ? 250 : 320, gap: mobile ? 150 : 170 };
}

function setPos(el, x, y, delay) {
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  el.style.animationDelay = `${delay}ms`;
}

function mapItems() {
  const filtered = filteredItems();
  const shown = filtered.slice(0, state.bloom);
  const selected = state.items.find((item) => item.id === state.selectedId);
  if (!selected) {
    const extra = shown.length
      ? relationsFor(shown[0], filtered)
          .map((row) => row.item)
          .filter((item) => !shown.some((row) => row.id === item.id))
          .slice(0, 4)
      : [];
    return {
      items: [...shown, ...extra].slice(0, state.bloom + 4),
      leftover: Math.max(0, filtered.length - shown.length),
      related: [],
    };
  }
  const related = relationsFor(selected, state.items);
  const extra = related.map((row) => row.item).filter((item) => !shown.some((row) => row.id === item.id));
  const items = [selected, ...extra, ...shown.filter((item) => item.id !== selected.id)].slice(0, state.bloom + 6);
  return { items, leftover: Math.max(0, filtered.length - shown.length), related };
}

function layout(items, m, selectedId, relatedIds) {
  const positions = new Map();
  const selected = items.find((item) => item.id === selectedId);
  const related = items.filter((item) => relatedIds.has(item.id));
  const rest = items.filter((item) => item.id !== selectedId && !relatedIds.has(item.id));

  if (selected) {
    const focus = { x: m.cx + (window.innerWidth < 700 ? 0 : 220), y: m.cy + (window.innerWidth < 700 ? 40 : 0) };
    positions.set(selected.id, focus);
    related.forEach((item, index) => {
      const angle = -Math.PI * 0.85 + (index / Math.max(related.length, 1)) * Math.PI * 1.7;
      positions.set(item.id, polar(focus.x, focus.y, 188, angle));
    });
  }

  let placed = 0;
  let ring = 0;
  while (placed < rest.length) {
    const take = Math.min(rest.length - placed, 8 + ring * 3);
    for (let i = 0; i < take; i += 1) {
      const angle = -Math.PI / 2 + (i / take) * Math.PI * 2 + ring * 0.18;
      positions.set(rest[placed + i].id, polar(m.cx, m.cy, m.r0 + ring * m.gap, angle));
    }
    placed += take;
    ring += 1;
  }
  return { positions, rings: ring };
}

function renderSky() {
  const m = metrics();
  els.sky.style.width = `${m.size}px`;
  els.sky.style.height = `${m.size}px`;
  els.sky.querySelectorAll(".story, .more, .empty-note").forEach((node) => node.remove());

  const { items, leftover, related } = mapItems();
  const relatedIds = new Set(related.map((row) => row.item.id));
  const { positions, rings } = layout(items, m, state.selectedId, relatedIds);
  const reasonById = new Map(related.map((row) => [row.item.id, row]));

  const paths = [];
  const edgeList = [];
  items.forEach((item) => {
    items.forEach((other) => {
      if (item.id >= other.id) return;
      const link = strongestLink(item, other);
      if (!link) return;
      const strong = Boolean(
        state.selectedId && (item.id === state.selectedId || other.id === state.selectedId)
      );
      if (strong || link.weight >= 2) edgeList.push({ a: item, b: other, link, strong });
    });
  });
  edgeList
    .sort((left, right) => right.link.weight - left.link.weight || Number(right.strong) - Number(left.strong))
    .slice(0, 36)
    .forEach(({ a, b, link, strong }) => {
      const pa = positions.get(a.id);
      const pb = positions.get(b.id);
      if (!pa || !pb) return;
      const { d, lx, ly } = curve(pa.x, pa.y, pb.x, pb.y);
      const color = strong ? "#b85c6e" : "rgba(59,50,44,0.32)";
      paths.push(
        `<path d="${d}" fill="none" stroke="${color}" stroke-width="${strong ? 3 : 1.6}" stroke-linecap="round"></path>`
      );
      if (strong) {
        const label = link.label.length > 18 ? `${link.label.slice(0, 16)}…` : link.label;
        const width = Math.max(72, label.length * 6.2 + 16);
        paths.push(
          `<rect x="${lx - width / 2}" y="${ly - 11}" width="${width}" height="18" rx="9" fill="#fff6ee" stroke="#3b322c" stroke-width="1.5"></rect>`
        );
        paths.push(
          `<text x="${lx}" y="${ly + 4}" text-anchor="middle" font-size="10" font-weight="800" fill="#3b322c">${escapeXml(label)}</text>`
        );
      }
    });

  items.forEach((item, index) => {
    const point = positions.get(item.id);
    if (!point) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `story ${item.category || "security"}`;
    btn.dataset.story = item.id;
    if (item.id === state.selectedId) btn.classList.add("is-selected");
    else if (state.selectedId && relatedIds.has(item.id)) btn.classList.add("is-related");
    else if (state.selectedId) btn.classList.add("is-dim");

    const source = document.createElement("div");
    source.className = "source";
    const name = document.createElement("span");
    name.textContent = item.source;
    const when = document.createElement("span");
    when.textContent = formatWhen(item.publishedAt);
    source.append(name, when);

    const title = document.createElement("strong");
    title.textContent = item.title;
    btn.append(source, title);

    const tags = document.createElement("div");
    tags.className = "tags";
    const labelBits = [...(item.cves || []).slice(0, 1), ...(item.vendors || []).slice(0, 1)];
    if (reasonById.has(item.id)) labelBits.unshift(reasonById.get(item.id).label);
    unique(labelBits).slice(0, 2).forEach((bit) => {
      const chip = document.createElement("span");
      chip.textContent = bit;
      tags.append(chip);
    });
    if (tags.childElementCount) btn.append(tags);
    setPos(btn, point.x, point.y, 80 + index * 16);
    els.sky.append(btn);
  });

  if (leftover > 0 && !state.selectedId) {
    const extra = polar(m.cx, m.cy, m.r0 + rings * m.gap, Math.PI * 0.25);
    const more = document.createElement("button");
    more.type = "button";
    more.className = "more";
    more.dataset.more = "1";
    more.textContent = `+${Math.min(leftover, PAGE)} more`;
    setPos(more, extra.x, extra.y, 200);
    els.sky.append(more);
  }

  if (!items.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = state.items.length
      ? "No stories match. Try a CVE, vendor, or a broader topic."
      : "Could not load stories. Try Refresh.";
    els.sky.append(note);
  }

  els.links.innerHTML = paths.join("");
  setPos(els.hub, m.cx, m.cy, 0);
  els.hubCaption.textContent = state.selectedId ? "related map" : "recent stories";

  const total = filteredItems().length;
  const updated = state.generatedAt ? formatWhen(state.generatedAt) : "just now";
  const origin = state.origin === "live" ? "live feeds" : "saved snapshot";
  els.status.textContent = `${total} stor${total === 1 ? "y" : "ies"} · updated ${updated} · ${origin}. Lines mark shared CVE, vendor, or source.`;
  els.refresh.disabled = state.refreshing;
  els.refresh.textContent = state.refreshing ? "Refreshing…" : "Refresh";
  els.searchClear.hidden = !state.query;

  if (!didCenter) {
    requestAnimationFrame(centerHub);
    didCenter = true;
  }
}

function centerHub() {
  els.wrap.scrollTo({
    left: els.hub.offsetLeft - els.wrap.clientWidth / 2 + els.hub.offsetWidth / 2,
    top: els.hub.offsetTop - els.wrap.clientHeight / 2 + els.hub.offsetHeight / 2,
    behavior: "smooth",
  });
}

function fillSources() {
  const current = state.sourceId;
  els.sourceFilter.replaceChildren();
  const all = document.createElement("option");
  all.value = "all";
  all.textContent = "All sources";
  els.sourceFilter.append(all);
  [...state.sources]
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((source) => {
      const option = document.createElement("option");
      option.value = source.id;
      option.textContent = source.name;
      els.sourceFilter.append(option);
    });
  els.sourceFilter.value = current;
}

function openSheet(item) {
  state.selectedId = item.id;
  const url = safeUrl(item.url);
  const related = relationsFor(item, state.items);
  els.sheet.hidden = false;
  els.sheetBody.replaceChildren();

  const title = document.createElement("h2");
  title.textContent = item.title;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${item.source} · ${formatWhen(item.publishedAt)}`;
  els.sheetBody.append(title, meta);

  if (item.excerpt) {
    const excerpt = document.createElement("p");
    excerpt.textContent = item.excerpt;
    els.sheetBody.append(excerpt);
  }

  const tags = document.createElement("div");
  tags.className = "tags";
  unique([...(item.cves || []), ...(item.vendors || []), ...(item.topics || [])])
    .slice(0, 8)
    .forEach((bit) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.textContent = bit;
      chip.addEventListener("click", () => {
        state.query = bit;
        els.search.value = bit;
        state.bloom = PAGE;
        renderSky();
      });
      tags.append(chip);
    });
  if (tags.childElementCount) els.sheetBody.append(tags);

  if (related.length) {
    const why = document.createElement("div");
    why.className = "why";
    why.textContent = "Related stories — follow a link";
    const list = document.createElement("div");
    list.className = "related";
    related.forEach((row) => {
      const btn = document.createElement("button");
      btn.type = "button";
      const kind = document.createElement("b");
      kind.textContent =
        row.kind === "cve" ? `Same ${row.label}` : row.kind === "vendor" ? `Same vendor: ${row.label}` : row.kind === "source" ? `Same source: ${row.label}` : `Same topic: ${row.label}`;
      const name = document.createElement("span");
      name.textContent = row.item.title;
      btn.append(kind, name);
      btn.addEventListener("click", () => openSheet(row.item));
      list.append(btn);
    });
    els.sheetBody.append(why, list);
  }

  if (url) {
    const go = document.createElement("a");
    go.className = "go";
    go.href = url;
    go.target = "_blank";
    go.rel = "noopener noreferrer";
    go.textContent = "Read at the source";
    els.sheetBody.append(go);
  }

  didCenter = false;
  renderSky();
}

function closeSheet() {
  state.selectedId = null;
  els.sheet.hidden = true;
  els.sheetBody.replaceChildren();
}

function applyPayload(payload, origin) {
  state.sources = payload.sources || [];
  state.items = mergeItems([], payload.items || []);
  state.generatedAt = payload.generatedAt || new Date().toISOString();
  state.origin = origin;
  fillSources();
  try {
    localStorage.setItem("qingqing-news-cache", JSON.stringify({ generatedAt: state.generatedAt, sources: state.sources, items: state.items }));
  } catch {
    /* ignore */
  }
  renderSky();
}

async function refreshLive() {
  if (!state.sources.length) return;
  state.refreshing = true;
  renderSky();
  const results = await Promise.allSettled(
    state.sources.map(async (source) => parseRssXml(await fetchViaProxy(source.feed), source))
  );
  const liveItems = results.flatMap((result) => (result.status === "fulfilled" ? result.value : []));
  if (liveItems.length) {
    state.items = mergeItems(state.items, liveItems);
    state.generatedAt = new Date().toISOString();
    state.origin = "live";
  }
  state.refreshing = false;
  renderSky();
  if (!liveItems.length) els.status.textContent += " Live RSS blocked; showing snapshot.";
}

async function boot() {
  try {
    applyPayload(await fetchSnapshot(), "snapshot");
  } catch {
    try {
      const cached = JSON.parse(localStorage.getItem("qingqing-news-cache") || "null");
      if (cached?.items?.length) applyPayload(cached, "snapshot");
      else throw new Error("empty");
    } catch {
      els.status.textContent = "Could not load the news snapshot.";
    }
  }
  if (navigator.onLine && state.sources.length) {
    refreshLive().catch(() => {
      state.refreshing = false;
      renderSky();
    });
  }
}

function resetView() {
  state.topic = "all";
  state.sourceId = "all";
  state.query = "";
  state.bloom = PAGE;
  els.search.value = "";
  els.sourceFilter.value = "all";
  for (const tab of els.topics.querySelectorAll("[data-topic]")) {
    tab.setAttribute("aria-pressed", String(tab.dataset.topic === "all"));
  }
  closeSheet();
  didCenter = false;
  renderSky();
}

els.sky.addEventListener("click", (event) => {
  const more = event.target.closest("[data-more]");
  if (more) {
    state.bloom += PAGE;
    renderSky();
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
  resetView();
});

els.topics.addEventListener("click", (event) => {
  const button = event.target.closest("[data-topic]");
  if (!button) return;
  state.topic = button.dataset.topic;
  state.bloom = PAGE;
  for (const tab of els.topics.querySelectorAll("[data-topic]")) {
    tab.setAttribute("aria-pressed", String(tab === button));
  }
  didCenter = false;
  renderSky();
});

els.sourceFilter.addEventListener("change", () => {
  state.sourceId = els.sourceFilter.value;
  state.bloom = PAGE;
  didCenter = false;
  renderSky();
});

els.searchForm.addEventListener("submit", (event) => event.preventDefault());
els.search.addEventListener("input", () => {
  state.query = els.search.value;
  state.bloom = PAGE;
  renderSky();
});
els.searchClear.addEventListener("click", () => {
  state.query = "";
  els.search.value = "";
  renderSky();
  els.search.focus();
});
els.searchHints.addEventListener("click", (event) => {
  const button = event.target.closest("[data-q]");
  if (!button) return;
  state.query = button.dataset.q;
  els.search.value = button.dataset.q;
  state.bloom = PAGE;
  els.search.focus();
  renderSky();
});

els.refresh.addEventListener("click", () => refreshLive());
els.sheetClose.addEventListener("click", () => {
  closeSheet();
  didCenter = false;
  renderSky();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeSheet();
    renderSky();
  }
  if ((event.metaKey || event.ctrlKey) && event.key === "k") {
    event.preventDefault();
    els.search.focus();
    els.search.select();
  }
});

window.addEventListener("resize", () => {
  didCenter = false;
  renderSky();
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
    /* optional */
  });
}

boot();
