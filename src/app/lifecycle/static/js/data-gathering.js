(async function () {
const GROUP_LABELS = {
  acquisition: "Acquisition",
  activation: "Activation",
  engagement: "Engagement",
  custom: "Custom stages",
};

const monthsMeta = await initLifecycleStorage();

let layout = getLayout();
const formFields = document.getElementById("form-fields");
const toast = document.getElementById("toast");
const monthSelect = document.getElementById("month-select");
const importResult = document.getElementById("import-result");

function showToast(message, type) {
  toast.textContent = message;
  toast.className = "toast show " + type;
  setTimeout(() => toast.classList.remove("show"), 4000);
}

function showImportResult(message, isError) {
  importResult.hidden = false;
  importResult.textContent = message;
  importResult.className = "import-hint " + (isError ? "import-hint--error" : "import-hint--success");
}

function populateMonthPicker(months, selected) {
  monthSelect.innerHTML = "";
  if (!months || !months.length) {
    monthSelect.disabled = true;
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No imported months yet";
    monthSelect.appendChild(opt);
    return;
  }
  monthSelect.disabled = false;
  for (const month of months) {
    const opt = document.createElement("option");
    opt.value = month;
    opt.textContent = formatJalaliMonth(month);
    if (month === selected) opt.selected = true;
    monthSelect.appendChild(opt);
  }
}

async function loadMonth(month) {
  if (!month) return;
  setSelectedMonth(month);
  const data = await fetchCountsForMonth(month);
  if (data) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    buildForm(data);
  }
}

function stagePercentHint(counts, stageId) {
  if (stageId === "applicant") return "";
  const totalUser = calcTotalUser(counts, layout);
  return "Share of total users: " + calcPercent(counts[stageId] ?? 0, totalUser);
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
      if (isChannelShape(s.shape)) continue;
      const wrap = document.createElement("div");
      wrap.className = "field";
      const pct = stagePercentHint(counts, s.id);
      const badge = s.isCustom ? ' <span class="hint">(custom)</span>' : "";
      wrap.innerHTML =
        '<label for="f-' + s.id + '">' + s.label + badge + "</label>" +
        '<input type="number" min="0" step="1" id="f-' + s.id + '" name="' + s.id + '" value="' + (counts[s.id] ?? 0) + '" />' +
        (pct ? '<span class="hint">' + pct + "</span>" : "");
      section.appendChild(wrap);
    }
    if (section.children.length > 1) {
      formFields.appendChild(section);
    }
  }
}

function readForm() {
  const counts = { ...getCounts(layout) };
  for (const s of getAllStages(layout)) {
    if (isChannelShape(s.shape)) continue;
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
    const pct = stagePercentHint(counts, s.id);
    hint.textContent = pct;
    hint.hidden = !pct;
  }
}

let selectedMonth = getSelectedMonth() || monthsMeta.latest || null;
populateMonthPicker(monthsMeta.months || [], selectedMonth);

let counts = getCounts(layout);
buildForm(counts);

monthSelect.addEventListener("change", async () => {
  const month = monthSelect.value;
  if (!month) return;
  selectedMonth = month;
  await loadMonth(month);
});

document.getElementById("import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById("counts-file");
  const file = fileInput.files?.[0];
  if (!file) {
    showImportResult("Choose a file to import.", true);
    return;
  }

  const btn = document.getElementById("import-btn");
  btn.disabled = true;
  showImportResult("Importing…", false);

  try {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(API_COUNTS_IMPORT, { method: "POST", body });
    const payload = await res.json();
    if (!res.ok) throw new Error(payload.detail || "Import failed");

    selectedMonth = payload.latest_month;
    setSelectedMonth(selectedMonth);
    populateMonthPicker(payload.months, selectedMonth);
    await loadMonth(selectedMonth);

    let msg =
      "Imported " +
      payload.imported +
      " month(s). Latest: " +
      formatJalaliMonth(payload.latest_month) +
      ".";
    if (payload.warnings && payload.warnings.length) {
      msg += " Warnings: " + payload.warnings.join(" ");
    }
    showImportResult(msg, false);
    showToast("Monthly counts imported.", "success");
    fileInput.value = "";
  } catch (err) {
    showImportResult(String(err.message || err), true);
    showToast("Import failed.", "info");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("admin-form").addEventListener("submit", (e) => {
  e.preventDefault();
  counts = readForm();
  const month = monthSelect.value || selectedMonth;
  if (counts.applicant <= 0) {
    showToast(
      "Applicant count is zero — saved anyway. Add applicant when available.",
      "info"
    );
  }
  saveCounts(counts, month);
  for (const s of layout.customStages || []) {
    if (typeof counts[s.id] === "number") s.count = counts[s.id];
  }
  saveLayout(layout);
  showToast(
    "Saved for " + (month ? formatJalaliMonth(month) : "current snapshot") + ".",
    "success"
  );
});

document.getElementById("reset-btn").addEventListener("click", () => {
  if (!confirm("Reset all stage counts to the default sample numbers?")) return;
  counts = getDefaultCounts(layout);
  saveCounts(counts, monthSelect.value || selectedMonth);
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
