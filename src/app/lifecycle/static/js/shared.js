const STORAGE_KEY = "bnpl-lifecycle-data";
const LAYOUT_STORAGE_KEY = "bnpl-lifecycle-layout";
const API_LAYOUT = "/api/lifecycle/layout";
const API_COUNTS = "/api/lifecycle/counts";
const DEFAULT_CONN_LABEL = "Flow rate";
const ARROW_STRAIGHT = "straight";
const ARROW_BENT = "bent";
const DEFAULT_BOARD_WIDTH = 1280;
const DEFAULT_BOARD_HEIGHT = 620;
const EP_STAGE = "stage";
const EP_GROUP = "group";

/** Built-in stage definitions */
const STAGES = [
  { id: "applicant", label: "Applicant User", defaultCount: 8712776, group: "acquisition" },
  { id: "rejected", label: "Rejected User", defaultCount: 1500088, group: "acquisition" },
  { id: "abandoned", label: "Abandoned User", defaultCount: 348736, group: "acquisition" },
  { id: "freshCreditHolder", label: "Fresh Credit Holder User", defaultCount: 87817, group: "activation" },
  { id: "unActivatedCreditHolder", label: "UN-Activated Credit Holder", defaultCount: 4107187, group: "activation" },
  { id: "deadCreditHolder", label: "Dead Credit Holder", defaultCount: 62509, group: "activation" },
  { id: "activeCustomer", label: "Active Customer (6M)", defaultCount: 1812302, group: "engagement" },
  { id: "dormantCustomer", label: "Dormant Customer", defaultCount: 318059, group: "engagement" },
  { id: "softChurned", label: "Soft Churned Customer", defaultCount: 481398, group: "engagement" },
  { id: "creditClosed", label: "Credit Closed Customer", defaultCount: 122249, group: "engagement" },
  { id: "blackList", label: "Black List (fraud / default)", defaultCount: 0, group: "engagement" },
];

/** Group box definitions */
const CANVAS_GROUPS = [
  {
    id: "allocatedUser",
    title: "Allocated User",
    className: "group-box--allocated",
    stages: [
      "freshCreditHolder",
      "unActivatedCreditHolder",
      "activeCustomer",
      "dormantCustomer",
      "softChurned",
    ],
    padding: { top: 32, right: 24, bottom: 24, left: 24 },
  },
  {
    id: "liveCreditHolder",
    title: "Live Credit Holder",
    className: "group-box--nested",
    stages: ["freshCreditHolder", "unActivatedCreditHolder"],
    padding: { top: 28, right: 18, bottom: 18, left: 18 },
  },
  {
    id: "liveCustomer",
    title: "Live Customer",
    className: "group-box--nested live-customer-col",
    stages: ["activeCustomer", "dormantCustomer", "softChurned"],
    padding: { top: 28, right: 18, bottom: 18, left: 18 },
  },
  {
    id: "deadCreditHolderGroup",
    title: "Dead Credit Holder",
    className: "group-box--dead",
    stages: ["deadCreditHolder"],
    padding: { top: 28, right: 18, bottom: 18, left: 18 },
  },
  {
    id: "deadCustomer",
    title: "Dead Customer",
    className: "group-box--dead",
    stages: ["creditClosed", "blackList"],
    padding: { top: 28, right: 18, bottom: 18, left: 18 },
  },
];

const DEFAULT_POSITIONS = {
  rejected: { x: 20, y: 28 },
  applicant: { x: 20, y: 168 },
  abandoned: { x: 20, y: 308 },
  deadCreditHolder: { x: 336, y: 40 },
  freshCreditHolder: { x: 284, y: 176 },
  unActivatedCreditHolder: { x: 284, y: 336 },
  activeCustomer: { x: 564, y: 176 },
  dormantCustomer: { x: 564, y: 300 },
  softChurned: { x: 564, y: 424 },
  creditClosed: { x: 864, y: 40 },
  blackList: { x: 1024, y: 40 },
};

const DEFAULT_GROUP_BOUNDS = {
  deadCreditHolderGroup: { x: 304, y: 8, width: 196, height: 108 },
  allocatedUser: { x: 248, y: 112, width: 760, height: 488 },
  liveCreditHolder: { x: 268, y: 148, width: 240, height: 320 },
  liveCustomer: { x: 548, y: 148, width: 240, height: 420 },
  deadCustomer: { x: 832, y: 8, width: 400, height: 108 },
};

const DEFAULT_CONNECTIONS = [
  { from: "applicant", to: "rejected", label: "Rejection rate", rate: 30.0 },
  { from: "applicant", to: "abandoned", label: "Abandon Rate", rate: 10.0 },
  { from: "abandoned", to: "applicant", label: "Re-Application rate" },
  { from: "applicant", to: "freshCreditHolder", label: "Allocation rate", rate: 60.0 },
  { from: "rejected", to: "freshCreditHolder", label: "Second Chance rate" },
  { from: "freshCreditHolder", to: "unActivatedCreditHolder", label: "30-days Un-activation rate" },
  { from: "freshCreditHolder", to: "activeCustomer", label: "Activation rate" },
  { from: "unActivatedCreditHolder", to: "activeCustomer", label: "Activation Recover rate" },
  { from: "freshCreditHolder", to: "deadCreditHolder", label: "Holder Close rate" },
  { from: "deadCreditHolder", to: "freshCreditHolder", label: "Holder Revenant rate" },
  { from: "activeCustomer", to: "dormantCustomer", label: "6M Dormancy rate" },
  { from: "dormantCustomer", to: "activeCustomer", label: "Dormancy Re-activation rate" },
  { from: "dormantCustomer", to: "softChurned", label: "Soft Churn rate" },
  { from: "softChurned", to: "activeCustomer", label: "Soft Churn Win-back rate" },
  { from: "activeCustomer", to: "creditClosed", label: "Customer Credit Close rate" },
  { from: "activeCustomer", to: "blackList", label: "Hard Churn rate" },
  { from: "creditClosed", to: "activeCustomer", label: "Customer Revenant rate" },
];

function epStage(stageId) {
  return EP_STAGE + ":" + stageId;
}

function epGroup(groupId) {
  return EP_GROUP + ":" + groupId;
}

function parseEndpoint(ep) {
  if (!ep || typeof ep !== "string") return null;
  if (ep.startsWith(EP_STAGE + ":")) {
    return { type: EP_STAGE, id: ep.slice(EP_STAGE.length + 1) };
  }
  if (ep.startsWith(EP_GROUP + ":")) {
    return { type: EP_GROUP, id: ep.slice(EP_GROUP.length + 1) };
  }
  return { type: EP_STAGE, id: ep };
}

function normalizeEndpoint(ep) {
  const p = parseEndpoint(ep);
  if (!p) return ep;
  return p.type === EP_GROUP ? epGroup(p.id) : epStage(p.id);
}

function getGroupDef(groupId) {
  return CANVAS_GROUPS.find((g) => g.id === groupId);
}

/** Parse transition rate (0–100 %) from admin input; null if empty/invalid */
function parseTransitionRate(value) {
  if (value === "" || value == null) return null;
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.min(100, n);
}

/** Format stored rate for display on arrows */
function formatTransitionRate(rate) {
  if (rate == null || !Number.isFinite(rate)) return "";
  return rate.toFixed(1) + "%";
}

/** Arrow label text: transition name + optional rate line */
function formatConnectionLabel(conn) {
  const name = conn.label || DEFAULT_CONN_LABEL;
  const pct = formatTransitionRate(conn.transitionRate);
  return pct ? name + "\n" + pct : name;
}

function getEndpointLabel(layout, ep) {
  const p = parseEndpoint(ep);
  if (!p) return String(ep);
  if (p.type === EP_GROUP) {
    const g = getGroupDef(p.id);
    return g ? g.title : p.id;
  }
  return getStageLabel(layout, p.id);
}

function getStageLabel(layout, stageId) {
  const labels = layout?.stageLabels || {};
  if (labels[stageId]) return labels[stageId];
  const custom = (layout?.customStages || []).find((s) => s.id === stageId);
  if (custom?.label) return custom.label;
  const built = STAGES.find((s) => s.id === stageId);
  return built ? built.label : "Stage";
}

function isCustomStage(layout, stageId) {
  return (layout?.customStages || []).some((s) => s.id === stageId);
}

function getAllStages(layout) {
  const lay = layout || { customStages: [], stageLabels: {}, hiddenStages: [] };
  const labels = lay.stageLabels || {};
  const hidden = new Set(lay.hiddenStages || []);
  const result = [];

  for (const s of STAGES) {
    if (hidden.has(s.id)) continue;
    result.push({
      ...s,
      label: labels[s.id] || s.label,
      isCustom: false,
    });
  }

  for (const s of lay.customStages || []) {
    if (hidden.has(s.id)) continue;
    result.push({
      id: s.id,
      label: s.label || "New Stage",
      defaultCount: s.count ?? 0,
      group: "custom",
      shape: s.shape === "circle" ? "circle" : "rectangle",
      isCustom: true,
    });
  }

  return result;
}

function getDefaultCounts(layout) {
  const counts = {};
  for (const s of getAllStages(layout || { customStages: [] })) {
    counts[s.id] = s.defaultCount;
  }
  return counts;
}

function getCounts(layout) {
  const baseLayout = layout || { customStages: [] };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const counts = getDefaultCounts(baseLayout);
    if (!raw) return counts;
    const parsed = JSON.parse(raw);
    for (const id of Object.keys(counts)) {
      if (typeof parsed[id] === "number" && parsed[id] >= 0) counts[id] = parsed[id];
    }
    for (const s of baseLayout.customStages || []) {
      if (typeof s.count === "number" && s.count >= 0) counts[s.id] = s.count;
    }
    return counts;
  } catch {
    return getDefaultCounts(baseLayout);
  }
}

function saveCounts(counts) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(counts));
  persistCountsToServer(counts);
}

async function initLifecycleStorage() {
  try {
    const [layoutRes, countsRes] = await Promise.all([
      fetch(API_LAYOUT),
      fetch(API_COUNTS),
    ]);
    if (layoutRes.ok) {
      const data = await layoutRes.json();
      if (data && typeof data === "object" && Object.keys(data).length > 0) {
        localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(mergeLayout(data)));
      }
    }
    if (countsRes.ok) {
      const data = await countsRes.json();
      if (data && typeof data === "object" && Object.keys(data).length > 0) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      }
    }
  } catch (err) {
    console.warn("Database unavailable, using browser localStorage.", err);
  }
}

function persistLayoutToServer(layout) {
  return fetch(API_LAYOUT, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(layout),
  }).then((res) => {
    if (!res.ok) throw new Error("layout save failed");
  });
}

function persistCountsToServer(counts) {
  return fetch(API_COUNTS, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(counts),
  }).then((res) => {
    if (!res.ok) throw new Error("counts save failed");
  });
}

function formatNumber(n) {
  return new Intl.NumberFormat("en-US").format(Math.round(n));
}

function calcPercent(count, applicantTotal) {
  if (!applicantTotal || applicantTotal <= 0) return "0%";
  return ((count / applicantTotal) * 100).toFixed(1) + "%";
}

function getStageStats(counts, layout) {
  const applicant = counts.applicant || 0;
  return getAllStages(layout).map((s) => ({
    ...s,
    count: counts[s.id] ?? 0,
    percent: calcPercent(counts[s.id] ?? 0, applicant),
  }));
}

function getDefaultLayout() {
  return {
    boardBounds: { x: 0, y: 0, width: DEFAULT_BOARD_WIDTH, height: DEFAULT_BOARD_HEIGHT },
    positions: JSON.parse(JSON.stringify(DEFAULT_POSITIONS)),
    groupBounds: JSON.parse(JSON.stringify(DEFAULT_GROUP_BOUNDS)),
    customStages: [],
    stageLabels: {},
    hiddenStages: [],
    connections: DEFAULT_CONNECTIONS.map((c, i) => ({
      id: "conn-" + i,
      from: epStage(c.from),
      to: epStage(c.to),
      label: c.label,
      routeType: ARROW_BENT,
      fromOffset: 0.5,
      toOffset: 0.5,
      transitionRate: c.rate != null ? c.rate : null,
    })),
  };
}

function mergeLayout(parsed) {
  const base = getDefaultLayout();
  if (!parsed || typeof parsed !== "object") return base;
  if (parsed.positions) {
    for (const key of Object.keys(parsed.positions)) {
      base.positions[key] = {
        x: Number(parsed.positions[key].x) || 0,
        y: Number(parsed.positions[key].y) || 0,
      };
    }
  }
  if (parsed.boardBounds && typeof parsed.boardBounds === "object") {
    const bb = parsed.boardBounds;
    base.boardBounds = {
      x: Number(bb.x) || 0,
      y: Number(bb.y) || 0,
      width: Math.max(200, Number(bb.width) || DEFAULT_BOARD_WIDTH),
      height: Math.max(200, Number(bb.height) || DEFAULT_BOARD_HEIGHT),
    };
  }
  if (parsed.groupBounds && typeof parsed.groupBounds === "object" && Object.keys(parsed.groupBounds).length > 0) {
    base.groupBounds = parsed.groupBounds;
  }
  if (parsed.stageLabels && typeof parsed.stageLabels === "object") {
    base.stageLabels = parsed.stageLabels;
  }
  if (Array.isArray(parsed.hiddenStages)) {
    base.hiddenStages = parsed.hiddenStages.filter((id) => typeof id === "string");
  }
  if (Array.isArray(parsed.customStages)) {
    base.customStages = parsed.customStages.map((s) => ({
      id: s.id,
      label: s.label || "New Stage",
      shape: s.shape === "circle" ? "circle" : "rectangle",
      count: typeof s.count === "number" ? s.count : 0,
    }));
  }
    if (Array.isArray(parsed.connections) && parsed.connections.length > 0) {
    base.connections = parsed.connections
      .filter((c) => c.from && c.to && c.id)
      .map((c) => ({
        id: c.id,
        from: normalizeEndpoint(c.from),
        to: normalizeEndpoint(c.to),
        label: c.label || DEFAULT_CONN_LABEL,
        routeType: c.routeType === ARROW_STRAIGHT ? ARROW_STRAIGHT : ARROW_BENT,
        fromAnchor: c.fromAnchor || null,
        toAnchor: c.toAnchor || null,
        fromOffset: typeof c.fromOffset === "number" ? c.fromOffset : 0.5,
        toOffset: typeof c.toOffset === "number" ? c.toOffset : 0.5,
        waypoints:
          c.routeType === ARROW_STRAIGHT
            ? null
            : Array.isArray(c.waypoints)
              ? c.waypoints.map((p) => ({
                  x: Number(p.x) || 0,
                  y: Number(p.y) || 0,
                }))
              : null,
        labelOffset:
          c.labelOffset &&
          (typeof c.labelOffset.dx === "number" || typeof c.labelOffset.dy === "number")
            ? {
                dx: Number(c.labelOffset.dx) || 0,
                dy: Number(c.labelOffset.dy) || 0,
              }
            : null,
        labelAnchor: c.labelAnchor === "left" || c.labelAnchor === "right" ? c.labelAnchor : null,
        transitionRate: parseTransitionRate(c.transitionRate),
      }));
  }
  return base;
}

function getLayout() {
  try {
    const raw = localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return getDefaultLayout();
    return mergeLayout(JSON.parse(raw));
  } catch {
    return getDefaultLayout();
  }
}

function saveLayout(layout) {
  localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
  persistLayoutToServer(layout);
}

/** Persist layout and stage counts together (browser cache + database). */
function saveAllData(layout) {
  saveLayout(layout);
  saveCounts(getCounts(layout));
}

async function saveAllDataAsync(layout) {
  const counts = getCounts(layout);
  localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
  localStorage.setItem(STORAGE_KEY, JSON.stringify(counts));
  await Promise.all([persistLayoutToServer(layout), persistCountsToServer(counts)]);
}
