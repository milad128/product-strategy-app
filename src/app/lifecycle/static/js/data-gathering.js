(async function () {
const GROUP_LABELS = {
  acquisition: "Acquisition",
  activation: "Activation",
  engagement: "Engagement",
  custom: "Custom stages",
};

await initLifecycleStorage();

let layout = getLayout();
const formFields = document.getElementById("form-fields");
const toast = document.getElementById("toast");

function showToast(message, type) {
  toast.textContent = message;
  toast.className = "toast show " + type;
  setTimeout(() => toast.classList.remove("show"), 4000);
}

function buildForm(counts) {
  const stages = getAllStages(layout);
  const groups = {};
  for (const s of stages) {
    if (!groups[s.group]) groups[s.group] = [];
    groups[s.group].push(s);
  }

  const order = ["acquisition", "activation", "engagement", "custom"];
  formFields.innerHTML = "";

  for (const groupKey of order) {
    const stagesInGroup = groups[groupKey];
    if (!stagesInGroup?.length) continue;

    const section = document.createElement("div");
    section.className = "field-group";
    section.innerHTML = "<h3>" + (GROUP_LABELS[groupKey] || groupKey) + "</h3>";

    for (const s of stagesInGroup) {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const pct =
        s.id === "applicant"
          ? "100% (baseline)"
          : calcPercent(counts[s.id] ?? 0, counts.applicant || 0);
      const badge = s.isCustom ? ' <span class="hint">(custom)</span>' : "";
      wrap.innerHTML =
        '<label for="f-' + s.id + '">' + s.label + badge + "</label>" +
        '<input type="number" min="0" step="1" id="f-' + s.id + '" name="' + s.id + '" value="' + (counts[s.id] ?? 0) + '" />' +
        '<span class="hint">Share of applicants: ' + pct + "</span>";
      section.appendChild(wrap);
    }
    formFields.appendChild(section);
  }
}

function readForm() {
  const counts = {};
  for (const s of getAllStages(layout)) {
    const input = document.getElementById("f-" + s.id);
    const v = parseInt(input?.value, 10);
    counts[s.id] = Number.isFinite(v) && v >= 0 ? v : 0;
  }
  return counts;
}

function refreshHints() {
  const counts = readForm();
  for (const s of getAllStages(layout)) {
    const input = document.getElementById("f-" + s.id);
    const hint = input?.closest(".field")?.querySelector(".hint");
    if (!hint) continue;
    const pct =
      s.id === "applicant"
        ? "100% (baseline)"
        : "Share of applicants: " + calcPercent(counts[s.id], counts.applicant || 0);
    hint.textContent = pct;
  }
}

let counts = getCounts(layout);
buildForm(counts);

document.getElementById("admin-form").addEventListener("submit", (e) => {
  e.preventDefault();
  counts = readForm();
  if (counts.applicant <= 0) {
    showToast("Applicant User count must be greater than zero.", "info");
    return;
  }
  saveCounts(counts);
  for (const s of layout.customStages || []) {
    if (typeof counts[s.id] === "number") s.count = counts[s.id];
  }
  saveLayout(layout);
  showToast("Saved. Open the Lifecycle page to see updated numbers.", "success");
});

document.getElementById("reset-btn").addEventListener("click", () => {
  if (!confirm("Reset all stage counts to the default sample numbers?")) return;
  counts = getDefaultCounts(layout);
  saveCounts(counts);
  buildForm(counts);
  showToast("Reset to default values.", "success");
});

formFields.addEventListener("input", refreshHints);

const transitionRows = document.getElementById("transition-rows");
const transitionEmpty = document.getElementById("transition-empty");
const transitionForm = document.getElementById("transition-form");

function sortedConnections() {
  return [...layout.connections].sort((a, b) => {
    const af = getEndpointLabel(layout, a.from);
    const bf = getEndpointLabel(layout, b.from);
    if (af !== bf) return af.localeCompare(bf);
    const at = getEndpointLabel(layout, a.to);
    const bt = getEndpointLabel(layout, b.to);
    return at.localeCompare(bt);
  });
}

function buildTransitionTable() {
  const conns = sortedConnections();
  transitionRows.innerHTML = "";
  transitionEmpty.hidden = conns.length > 0;
  document.getElementById("transition-table").hidden = conns.length === 0;

  for (const c of conns) {
    const tr = document.createElement("tr");
    const rateVal =
      c.transitionRate != null && Number.isFinite(c.transitionRate)
        ? c.transitionRate
        : "";
    tr.innerHTML =
      "<td>" + getEndpointLabel(layout, c.from) + "</td>" +
      "<td>" + getEndpointLabel(layout, c.to) + "</td>" +
      '<td class="transition-table__name">' + (c.label || DEFAULT_CONN_LABEL) + "</td>" +
      '<td><input type="number" min="0" max="100" step="0.1" class="transition-rate-input" data-conn-id="' +
      c.id +
      '" value="' +
      rateVal +
      '" placeholder="—" aria-label="Rate for ' +
      (c.label || DEFAULT_CONN_LABEL) +
      '" /></td>';
    transitionRows.appendChild(tr);
  }
}

function readTransitionRates() {
  const rates = {};
  transitionRows.querySelectorAll(".transition-rate-input").forEach((input) => {
    rates[input.getAttribute("data-conn-id")] = parseTransitionRate(input.value);
  });
  return rates;
}

buildTransitionTable();

transitionForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const rates = readTransitionRates();
  for (const c of layout.connections) {
    if (Object.prototype.hasOwnProperty.call(rates, c.id)) {
      c.transitionRate = rates[c.id];
    }
  }
  saveLayout(layout);
  showToast("Transition rates saved. Open Lifecycle to see them on arrows.", "success");
});

document.getElementById("clear-rates-btn").addEventListener("click", () => {
  if (!confirm("Clear all transition rates? Arrow names will stay the same.")) return;
  for (const c of layout.connections) c.transitionRate = null;
  saveLayout(layout);
  buildTransitionTable();
  showToast("All transition rates cleared.", "success");
});

window.addEventListener("storage", (e) => {
  if (e.key === LAYOUT_STORAGE_KEY) {
    layout = getLayout();
    buildTransitionTable();
  }
});

})();
