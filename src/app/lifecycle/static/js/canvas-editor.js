/**
 * Interactive canvas: drag stages, connect with editable arrows (Miro/FigJam style).
 * Read-only presentation when body has class page-present (present.html).
 */
(async function () {
  const monthsMeta = await initLifecycleStorage();

  const IS_PRESENT = document.body.classList.contains("page-present");
  const board = document.getElementById("canvas-board");
  const presentScaler = IS_PRESENT ? document.getElementById("present-scaler") : null;
  const boardInner = IS_PRESENT
    ? presentScaler?.querySelector(".canvas-board__inner")
    : board?.querySelector(".canvas-board__inner");
  const groupsLayer = document.getElementById("canvas-groups");
  const nodesLayer = document.getElementById("canvas-nodes");
  const svg = document.getElementById("canvas-svg");
  const labelsLayer = document.getElementById("canvas-labels");
  const handlesLayer = document.getElementById("canvas-handles");
  const groupResizeLayer = document.getElementById("canvas-group-resize");
  const boardResizeLayer = document.getElementById("canvas-board-resize");
  const modeHint = document.getElementById("mode-hint");
  const deleteConnBtn = document.getElementById("btn-delete-conn");
  const deleteStageBtn = document.getElementById("btn-delete-stage");
  const saveBtn = document.getElementById("btn-save");
  const connLabelInput = document.getElementById("conn-label-input");
  const stageNameInput = document.getElementById("stage-name-input");
  const propertiesBar = document.getElementById("canvas-properties");
  const propsStage = document.getElementById("props-stage");
  const propsArrow = document.getElementById("props-arrow");
  const saveToast = document.getElementById("save-toast");

  if (!board || !boardInner || !nodesLayer || !svg || (IS_PRESENT && !presentScaler)) return;

  let layout = getLayout();
  let mode = "select";
  let arrowType = ARROW_BENT;
  let stageShape = SHAPE_STAGE;
  let selectedNodeId = null;
  let selectedGroupId = null;
  let selectedConnId = null;
  let selectedBoard = false;
  let connectFromEp = null;
  let dragState = null;
  let handleDrag = null;
  let groupResizeDrag = null;
  let groupDragState = null;
  let boardResizeDrag = null;
  let labelDrag = null;
  let suppressLabelEdit = false;
  let connIdCounter = Date.now();
  let customStageCounter = Date.now();
  let isDirty = false;

  let availableMonths = monthsMeta.months || [];
  let currentMonth = getSelectedMonth();

  const monthNav = document.getElementById("month-nav");
  const monthLabel = document.getElementById("month-label");
  const monthPrevBtn = document.getElementById("month-prev");
  const monthNextBtn = document.getElementById("month-next");

  const nodeEls = new Map();
  const groupEls = new Map();

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function getConn(id) {
    return layout.connections.find((c) => c.id === id);
  }

  function clientToBoard(clientX, clientY) {
    const boardRect = board.getBoundingClientRect();
    return {
      x: clientX - boardRect.left + board.scrollLeft,
      y: clientY - boardRect.top + board.scrollTop,
    };
  }

  function clientToCanvas(clientX, clientY) {
    const p = clientToBoard(clientX, clientY);
    const bb = getBoardBounds();
    return { x: p.x - bb.x, y: p.y - bb.y };
  }

  function getBoardBounds() {
    const b = layout.boardBounds;
    if (b && typeof b.width === "number" && typeof b.height === "number") {
      return {
        x: Number(b.x) || 0,
        y: Number(b.y) || 0,
        width: Math.max(200, b.width),
        height: Math.max(200, b.height),
      };
    }
    return {
      x: 0,
      y: 0,
      width: DEFAULT_BOARD_WIDTH,
      height: DEFAULT_BOARD_HEIGHT,
    };
  }

  function applyPresentBoardSize() {
    const b = getBoardBounds();
    boardInner.style.left = "0";
    boardInner.style.top = "0";
    boardInner.style.width = b.width + "px";
    boardInner.style.height = b.height + "px";
  }

  function fitPresentToViewport() {
    if (!IS_PRESENT) return;
    const b = getBoardBounds();
    applyPresentBoardSize();
    const pad = 48;
    const availW = Math.max(100, board.clientWidth - pad);
    const availH = Math.max(100, board.clientHeight - pad);
    const scale = Math.min(availW / b.width, availH / b.height);
    boardInner.style.transform = "scale(" + scale + ")";
    boardInner.style.transformOrigin = "0 0";
    if (presentScaler) {
      presentScaler.style.width = Math.ceil(b.width * scale) + "px";
      presentScaler.style.height = Math.ceil(b.height * scale) + "px";
    }
  }

  function schedulePresentFit() {
    requestAnimationFrame(() => {
      fitPresentToViewport();
      requestAnimationFrame(() => {
        fitPresentToViewport();
        updateGroupBoxes();
        drawConnections();
      });
    });
  }

  function applyBoardBounds() {
    const b = getBoardBounds();
    layout.boardBounds = b;
    if (IS_PRESENT) {
      applyPresentBoardSize();
      return;
    }
    boardInner.style.transform = "";
    if (presentScaler) {
      presentScaler.style.width = "";
      presentScaler.style.height = "";
    }
    boardInner.style.left = b.x + "px";
    boardInner.style.top = b.y + "px";
    boardInner.style.width = b.width + "px";
    boardInner.style.height = b.height + "px";
    board.classList.toggle("is-board-selected", selectedBoard && mode === "select");
  }

  function shiftLayoutContent(dx, dy, light) {
    if (!dx && !dy) return;
    for (const id of Object.keys(layout.positions)) {
      layout.positions[id].x += dx;
      layout.positions[id].y += dy;
    }
    for (const id of Object.keys(layout.groupBounds)) {
      const box = layout.groupBounds[id];
      if (box) {
        box.x += dx;
        box.y += dy;
      }
    }
    for (const conn of layout.connections) {
      if (conn.waypoints) {
        conn.waypoints.forEach((w) => {
          w.x += dx;
          w.y += dy;
        });
      }
    }
    if (light) {
      nodeEls.forEach((el, id) => {
        const p = layout.positions[id];
        if (p) {
          el.style.left = p.x + "px";
          el.style.top = p.y + "px";
        }
      });
      updateGroupBoxes();
    } else {
      buildNodes();
      bindNodes();
      updateGroupBoxes();
    }
  }

  function renderNodeContent(el, stat) {
    if (isChannelShape(stat.shape)) {
      el.innerHTML =
        '<div class="stage__name">' + escapeHtml(stat.label) + "</div>";
      return;
    }
    let html =
      '<div class="stage__name">' + escapeHtml(stat.label) + "</div>" +
      '<div class="stage__count">' + formatNumber(stat.count) + "</div>";
    if (stat.id !== "applicant" && stat.percent) {
      html += '<div class="stage__pct">' + stat.percent + "</div>";
    }
    el.innerHTML = html;
  }

  function rectFromBox(box) {
    return {
      left: box.x,
      top: box.y,
      width: box.width,
      height: box.height,
      right: box.x + box.width,
      bottom: box.y + box.height,
      cx: box.x + box.width / 2,
      cy: box.y + box.height / 2,
    };
  }

  function buildNodes() {
    const counts = getCounts(layout);
    const stats = getStageStats(counts, layout);
    const byId = Object.fromEntries(stats.map((s) => [s.id, s]));

    nodesLayer.innerHTML = "";
    nodeEls.clear();

    for (const stage of getAllStages(layout)) {
      const pos = layout.positions[stage.id] || { x: 0, y: 0 };
      const div = document.createElement("div");
      div.className =
        "canvas-node stage stage--" + normalizeShapeType(stage.shape);
      div.setAttribute("data-stage", stage.id);
      if (!IS_PRESENT) {
        div.setAttribute("role", "button");
        div.setAttribute("tabindex", "0");
      }
      div.style.left = pos.x + "px";
      div.style.top = pos.y + "px";
      renderNodeContent(div, byId[stage.id]);
      nodesLayer.appendChild(div);
      nodeEls.set(stage.id, div);
    }
    updateSelectionUI();
    requestAnimationFrame(() => {
      updateGroupBoxes();
      drawGroupResizeHandles();
      drawBoardResizeHandles();
    });
  }

  function buildGroupBoxes() {
    if (!groupsLayer) return;
    groupsLayer.innerHTML = "";
    groupEls.clear();
    for (const g of CANVAS_GROUPS) {
      const div = document.createElement("div");
      div.className = "canvas-group group-box " + (g.className || "");
      div.setAttribute("data-group", g.id);
      div.innerHTML = '<span class="group-box__title">' + escapeHtml(g.title) + "</span>";
      if (!IS_PRESENT) {
        div.addEventListener("pointerdown", (e) => onGroupPointerDown(e, g.id));
      }
      groupsLayer.appendChild(div);
      groupEls.set(g.id, div);
    }
    updateGroupBoxes();
  }

  function bboxForStages(stageIds) {
    let minL = Infinity;
    let minT = Infinity;
    let maxR = -Infinity;
    let maxB = -Infinity;
    for (const id of stageIds) {
      const r = getNodeRect(id);
      if (!r) continue;
      minL = Math.min(minL, r.left);
      minT = Math.min(minT, r.top);
      maxR = Math.max(maxR, r.right);
      maxB = Math.max(maxB, r.bottom);
    }
    if (minL === Infinity) return null;
    return { left: minL, top: minT, right: maxR, bottom: maxB };
  }

  function computeAutoGroupBox(groupId) {
    const g = getGroupDef(groupId);
    if (!g) return null;
    const box = bboxForStages(g.stages);
    if (!box) return null;
    const pad = g.padding || { top: 24, right: 16, bottom: 16, left: 16 };
    return {
      x: box.left - pad.left,
      y: box.top - pad.top,
      width: box.right - box.left + pad.left + pad.right,
      height: box.bottom - box.top + pad.top + pad.bottom,
    };
  }

  function getGroupBox(groupId) {
    const manual = layout.groupBounds?.[groupId];
    if (manual && manual.width >= 40 && manual.height >= 40) {
      return {
        x: manual.x,
        y: manual.y,
        width: manual.width,
        height: manual.height,
      };
    }
    return computeAutoGroupBox(groupId);
  }

  function getGroupRect(groupId) {
    const box = getGroupBox(groupId);
    return box ? rectFromBox(box) : null;
  }

  function getEndpointRect(ep) {
    const p = parseEndpoint(ep);
    if (!p) return null;
    if (p.type === EP_GROUP) return getGroupRect(p.id);
    return getNodeRect(p.id);
  }

  function pointInRect(pt, r) {
    return pt.x >= r.left && pt.x <= r.right && pt.y >= r.top && pt.y <= r.bottom;
  }

  function findEndpointAtPoint(pt) {
    for (const s of getAllStages(layout)) {
      const r = getNodeRect(s.id);
      if (r && pointInRect(pt, r)) return epStage(s.id);
    }
    for (let i = CANVAS_GROUPS.length - 1; i >= 0; i--) {
      const g = CANVAS_GROUPS[i];
      const r = getGroupRect(g.id);
      if (r && pointInRect(pt, r)) return epGroup(g.id);
    }
    return null;
  }

  function updateGroupBoxes() {
    for (const g of CANVAS_GROUPS) {
      const el = groupEls.get(g.id);
      const box = getGroupBox(g.id);
      if (!el || !box) continue;
      el.style.left = box.x + "px";
      el.style.top = box.y + "px";
      el.style.width = box.width + "px";
      el.style.height = box.height + "px";
      if (!IS_PRESENT) {
        el.classList.toggle("is-selected", g.id === selectedGroupId);
        el.classList.toggle("is-connect-source", connectFromEp === epGroup(g.id));
      }
    }
  }

  function updateDeleteButton() {
    if (deleteConnBtn) {
      const enabled = !!selectedConnId;
      deleteConnBtn.disabled = !enabled;
      deleteConnBtn.setAttribute("aria-disabled", enabled ? "false" : "true");
    }
    if (deleteStageBtn) {
      const enabled = !!selectedNodeId;
      deleteStageBtn.disabled = !enabled;
      deleteStageBtn.setAttribute("aria-disabled", enabled ? "false" : "true");
    }
  }

  function updateSaveButton() {
    if (!saveBtn) return;
    saveBtn.classList.toggle("has-unsaved", isDirty);
    saveBtn.textContent = isDirty ? "Save *" : "Save";
  }

  function showSaveToastMessage() {
    if (!saveToast) return;
    saveToast.hidden = false;
    clearTimeout(showSaveToastMessage._t);
    showSaveToastMessage._t = setTimeout(() => {
      saveToast.hidden = true;
    }, 2500);
  }

  function markDirty() {
    isDirty = true;
    updateSaveButton();
    const el = document.getElementById("updated-at");
    if (el) el.textContent = "Unsaved changes · click Save to store in database";
  }

  async function saveAll() {
    try {
      await saveAllDataAsync(layout);
      isDirty = false;
      updateSaveButton();
      showSaveToastMessage();
      const el = document.getElementById("updated-at");
      if (el) {
        el.textContent = "Saved to database · " + new Date().toLocaleString();
      }
    } catch (err) {
      console.error(err);
      const el = document.getElementById("updated-at");
      if (el) el.textContent = "Save failed — check server is running";
    }
  }

  function setStageName(stageId, name) {
    const shape = getStageShapeType(layout, stageId);
    const label =
      (name || "").trim() ||
      (shape === SHAPE_CHANNEL ? "New Channel" : "New Stage");
    if (isCustomStage(layout, stageId)) {
      const s = layout.customStages.find((x) => x.id === stageId);
      if (s) s.label = label;
    } else {
      if (!layout.stageLabels) layout.stageLabels = {};
      layout.stageLabels[stageId] = label;
    }
    const el = nodeEls.get(stageId);
    if (el) {
      const counts = getCounts(layout);
      const stat = getStageStats(counts, layout).find((s) => s.id === stageId);
      if (stat) renderNodeContent(el, stat);
    }
    markDirty();
  }

  function deleteSelectedStage() {
    if (!selectedNodeId) return;
    const id = selectedNodeId;
    const name = getStageLabel(layout, id);
    if (
      !confirm(
        'Delete stage "' + name + '"?\n\nConnected arrows will be removed.'
      )
    ) {
      return;
    }

    const ep = epStage(id);
    layout.connections = layout.connections.filter(
      (c) => c.from !== ep && c.to !== ep
    );

    if (isCustomStage(layout, id)) {
      layout.customStages = (layout.customStages || []).filter((s) => s.id !== id);
      delete layout.positions[id];
      if (layout.stageLabels) delete layout.stageLabels[id];
    } else {
      if (!layout.hiddenStages) layout.hiddenStages = [];
      if (!layout.hiddenStages.includes(id)) layout.hiddenStages.push(id);
    }

    clearSelection();
    markDirty();
    buildGroupBoxes();
    buildNodes();
    bindNodes();
    requestAnimationFrame(() => {
      updateGroupBoxes();
      drawConnections();
    });
  }

  function updatePropertiesBar() {
    if (!propertiesBar) return;

    if (selectedNodeId && propsStage && stageNameInput) {
      propertiesBar.classList.add("is-active");
      propsStage.hidden = false;
      if (propsArrow) propsArrow.hidden = true;
      const shape = getStageShapeType(layout, selectedNodeId);
      const nameLabel = document.getElementById("object-name-label");
      if (nameLabel) {
        nameLabel.textContent =
          shape === SHAPE_CHANNEL ? "Channel name" : "Stage name";
      }
      stageNameInput.placeholder =
        shape === SHAPE_CHANNEL ? "Channel name" : "Stage name";
      stageNameInput.value = getStageLabel(layout, selectedNodeId);
    } else if (selectedConnId && propsArrow && connLabelInput) {
      propertiesBar.classList.add("is-active");
      if (propsStage) propsStage.hidden = true;
      propsArrow.hidden = false;
      const conn = getConn(selectedConnId);
      connLabelInput.value = conn ? conn.label || DEFAULT_CONN_LABEL : "";
    } else {
      propertiesBar.classList.remove("is-active");
      if (propsStage) propsStage.hidden = true;
      if (propsArrow) propsArrow.hidden = true;
    }
  }

  function drawGroupResizeHandles() {
    if (IS_PRESENT || !groupResizeLayer) return;
    groupResizeLayer.innerHTML = "";
    if (!selectedGroupId || mode !== "select" || groupResizeDrag) return;
    const box = getGroupBox(selectedGroupId);
    if (!box) return;
    const handles = [
      { edge: "n", x: box.x + box.width / 2, y: box.y },
      { edge: "s", x: box.x + box.width / 2, y: box.y + box.height },
      { edge: "e", x: box.x + box.width, y: box.y + box.height / 2 },
      { edge: "w", x: box.x, y: box.y + box.height / 2 },
      { edge: "ne", x: box.x + box.width, y: box.y },
      { edge: "nw", x: box.x, y: box.y },
      { edge: "se", x: box.x + box.width, y: box.y + box.height },
      { edge: "sw", x: box.x, y: box.y + box.height },
    ];
    for (const h of handles) {
      const el = document.createElement("div");
      el.className = "group-resize-handle group-resize-handle--" + h.edge;
      el.setAttribute("data-group", selectedGroupId);
      el.setAttribute("data-edge", h.edge);
      el.style.left = h.x + "px";
      el.style.top = h.y + "px";
      groupResizeLayer.appendChild(el);
    }
  }

  function onGroupResizePointerDown(e) {
    const handle = e.target.closest(".group-resize-handle");
    if (!handle || e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const groupId = handle.getAttribute("data-group");
    const edge = handle.getAttribute("data-edge");
    const box = getGroupBox(groupId);
    if (!box) return;
    if (!layout.groupBounds[groupId]) {
      layout.groupBounds[groupId] = { ...box };
    }
    groupResizeDrag = {
      groupId,
      edge,
      startX: e.clientX,
      startY: e.clientY,
      orig: { ...layout.groupBounds[groupId] },
      pointerId: e.pointerId,
    };
    board.setPointerCapture(e.pointerId);
    document.addEventListener("pointermove", onGroupResizePointerMove);
    document.addEventListener("pointerup", onGroupResizePointerUp);
  }

  function onGroupResizePointerMove(e) {
    if (!groupResizeDrag || e.pointerId !== groupResizeDrag.pointerId) return;
    const dx = e.clientX - groupResizeDrag.startX;
    const dy = e.clientY - groupResizeDrag.startY;
    const o = groupResizeDrag.orig;
    const min = 60;
    let x = o.x;
    let y = o.y;
    let w = o.width;
    let h = o.height;
    const edge = groupResizeDrag.edge;
    if (edge.includes("e")) w = Math.max(min, o.width + dx);
    if (edge.includes("w")) {
      w = Math.max(min, o.width - dx);
      x = o.x + o.width - w;
    }
    if (edge.includes("s")) h = Math.max(min, o.height + dy);
    if (edge.includes("n")) {
      h = Math.max(min, o.height - dy);
      y = o.y + o.height - h;
    }
    layout.groupBounds[groupResizeDrag.groupId] = { x, y, width: w, height: h };
    updateGroupBoxes();
    drawGroupResizeHandles();
    drawConnections();
  }

  function onGroupResizePointerUp(e) {
    if (!groupResizeDrag || e.pointerId !== groupResizeDrag.pointerId) return;
    markDirty();
    try {
      board.releasePointerCapture(e.pointerId);
    } catch (_) {}
    groupResizeDrag = null;
    document.removeEventListener("pointermove", onGroupResizePointerMove);
    document.removeEventListener("pointerup", onGroupResizePointerUp);
    drawGroupResizeHandles();
  }

  function drawBoardResizeHandles() {
    if (IS_PRESENT || !boardResizeLayer) return;
    boardResizeLayer.innerHTML = "";
    if (!selectedBoard || mode !== "select" || boardResizeDrag) return;
    const box = getBoardBounds();
    const handles = [
      { edge: "n", x: box.width / 2, y: 0 },
      { edge: "s", x: box.width / 2, y: box.height },
      { edge: "e", x: box.width, y: box.height / 2 },
      { edge: "w", x: 0, y: box.height / 2 },
      { edge: "ne", x: box.width, y: 0 },
      { edge: "nw", x: 0, y: 0 },
      { edge: "se", x: box.width, y: box.height },
      { edge: "sw", x: 0, y: box.height },
    ];
    for (const h of handles) {
      const el = document.createElement("div");
      el.className = "board-resize-handle board-resize-handle--" + h.edge;
      el.setAttribute("data-edge", h.edge);
      el.style.left = h.x + "px";
      el.style.top = h.y + "px";
      boardResizeLayer.appendChild(el);
    }
  }

  function onBoardResizePointerDown(e) {
    const handle = e.target.closest(".board-resize-handle");
    if (!handle || e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const edge = handle.getAttribute("data-edge");
    const o = { ...getBoardBounds() };
    boardResizeDrag = {
      edge,
      startX: e.clientX,
      startY: e.clientY,
      orig: o,
      lastX: o.x,
      lastY: o.y,
      pointerId: e.pointerId,
    };
    board.setPointerCapture(e.pointerId);
    document.addEventListener("pointermove", onBoardResizePointerMove);
    document.addEventListener("pointerup", onBoardResizePointerUp);
  }

  function onBoardResizePointerMove(e) {
    if (!boardResizeDrag || e.pointerId !== boardResizeDrag.pointerId) return;
    const dx = e.clientX - boardResizeDrag.startX;
    const dy = e.clientY - boardResizeDrag.startY;
    const o = boardResizeDrag.orig;
    const min = 200;
    let x = o.x;
    let y = o.y;
    let w = o.width;
    let h = o.height;
    const edge = boardResizeDrag.edge;
    if (edge.includes("e")) w = Math.max(min, o.width + dx);
    if (edge.includes("w")) {
      w = Math.max(min, o.width - dx);
      x = o.x + o.width - w;
    }
    if (edge.includes("s")) h = Math.max(min, o.height + dy);
    if (edge.includes("n")) {
      h = Math.max(min, o.height - dy);
      y = o.y + o.height - h;
    }
    const shiftX = x - boardResizeDrag.lastX;
    const shiftY = y - boardResizeDrag.lastY;
    if (shiftX || shiftY) {
      shiftLayoutContent(shiftX, shiftY, true);
      boardResizeDrag.lastX = x;
      boardResizeDrag.lastY = y;
    }
    layout.boardBounds = { x, y, width: w, height: h };
    applyBoardBounds();
    drawBoardResizeHandles();
    drawConnections();
  }

  function onBoardResizePointerUp(e) {
    if (!boardResizeDrag || e.pointerId !== boardResizeDrag.pointerId) return;
    markDirty();
    try {
      board.releasePointerCapture(e.pointerId);
    } catch (_) {}
    boardResizeDrag = null;
    document.removeEventListener("pointermove", onBoardResizePointerMove);
    document.removeEventListener("pointerup", onBoardResizePointerUp);
    drawBoardResizeHandles();
  }

  function onLabelPointerDown(e) {
    const span = e.target.closest(".canvas-conn-label");
    if (!span || e.button !== 0 || mode !== "select") return;
    if (span.classList.contains("is-editing")) return;
    const connId = span.getAttribute("data-conn-id");
    if (!connId) return;
    e.stopPropagation();
    e.preventDefault();
    if (selectedConnId !== connId) selectConnection(connId);
    const conn = getConn(connId);
    if (!conn) return;
    const points = resolveConnectionPoints(conn);
    const auto = labelPosition(points);
    const lp = getConnLabelPosition(conn, points);
    if (!conn.labelOffset) conn.labelOffset = { dx: 0, dy: 0 };
    if (!conn.labelAnchor) conn.labelAnchor = auto.anchor;
    labelDrag = {
      connId,
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      origDx: conn.labelOffset.dx,
      origDy: conn.labelOffset.dy,
      moved: false,
    };
    span.classList.add("is-dragging");
    board.setPointerCapture(e.pointerId);
    document.addEventListener("pointermove", onLabelPointerMove);
    document.addEventListener("pointerup", onLabelPointerUp);
    document.addEventListener("pointercancel", onLabelPointerUp);
  }

  function onLabelPointerMove(e) {
    if (!labelDrag || e.pointerId !== labelDrag.pointerId) return;
    const conn = getConn(labelDrag.connId);
    if (!conn) return;
    const dx = e.clientX - labelDrag.startX;
    const dy = e.clientY - labelDrag.startY;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) labelDrag.moved = true;
    if (!labelDrag.moved) return;
    const points = resolveConnectionPoints(conn);
    const auto = labelPosition(points);
    const pt = clientToCanvas(e.clientX, e.clientY);
    conn.labelOffset = {
      dx: pt.x - auto.x,
      dy: pt.y - auto.y,
    };
    const span = labelsLayer.querySelector(
      '.canvas-conn-label[data-conn-id="' + labelDrag.connId + '"]'
    );
    if (span) applyLabelStyle(span, getConnLabelPosition(conn, points));
  }

  function onLabelPointerUp(e) {
    if (!labelDrag || e.pointerId !== labelDrag.pointerId) return;
    const conn = getConn(labelDrag.connId);
    const span = labelsLayer.querySelector(
      '.canvas-conn-label[data-conn-id="' + labelDrag.connId + '"]'
    );
    if (span) span.classList.remove("is-dragging");
    if (labelDrag.moved) {
      suppressLabelEdit = true;
      if (conn) markDirty();
    }
    try {
      board.releasePointerCapture(e.pointerId);
    } catch (_) {}
    labelDrag = null;
    document.removeEventListener("pointermove", onLabelPointerMove);
    document.removeEventListener("pointerup", onLabelPointerUp);
    document.removeEventListener("pointercancel", onLabelPointerUp);
    if (conn) drawConnections();
  }

  function getNestedGroupIds(parentGroupId) {
    const parent = getGroupDef(parentGroupId);
    if (!parent) return [parentGroupId];
    const parentStages = new Set(parent.stages);
    const ids = [parentGroupId];
    for (const g of CANVAS_GROUPS) {
      if (g.id === parentGroupId) continue;
      if (g.stages.length && g.stages.every((s) => parentStages.has(s))) {
        ids.push(g.id);
      }
    }
    return ids;
  }

  function pinGroupBounds(groupId) {
    if (!layout.groupBounds) layout.groupBounds = {};
    const box = getGroupBox(groupId);
    if (box) {
      layout.groupBounds[groupId] = {
        x: box.x,
        y: box.y,
        width: box.width,
        height: box.height,
      };
    }
  }

  function onGroupDragPointerMove(e) {
    if (!groupDragState || e.pointerId !== groupDragState.pointerId) return;
    const dx = e.clientX - groupDragState.startX;
    const dy = e.clientY - groupDragState.startY;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) groupDragState.moved = true;

    for (const stageId of groupDragState.stageIds) {
      const orig = groupDragState.origPositions[stageId];
      if (!orig) continue;
      const x = Math.max(0, orig.x + dx);
      const y = Math.max(0, orig.y + dy);
      layout.positions[stageId] = { x, y };
      const nodeEl = nodeEls.get(stageId);
      if (nodeEl) {
        nodeEl.style.left = x + "px";
        nodeEl.style.top = y + "px";
      }
    }

    for (const gid of groupDragState.groupIds) {
      const orig = groupDragState.origGroupBounds[gid];
      if (!orig) continue;
      layout.groupBounds[gid] = {
        x: orig.x + dx,
        y: orig.y + dy,
        width: orig.width,
        height: orig.height,
      };
    }

    updateGroupBoxes();
    drawConnections();
  }

  function onGroupDragPointerUp(e) {
    if (!groupDragState || e.pointerId !== groupDragState.pointerId) return;
    const el = groupEls.get(groupDragState.groupId);
    if (el) el.classList.remove("is-dragging");
    if (groupDragState.moved) markDirty();
    try {
      if (el) el.releasePointerCapture(e.pointerId);
    } catch (_) {}
    groupDragState = null;
    document.removeEventListener("pointermove", onGroupDragPointerMove);
    document.removeEventListener("pointerup", onGroupDragPointerUp);
    document.removeEventListener("pointercancel", onGroupDragPointerUp);
    drawGroupResizeHandles();
  }

  function startGroupDrag(e, groupId) {
    const def = getGroupDef(groupId);
    if (!def) return;

    const groupIds = getNestedGroupIds(groupId);
    const stageIds = [...def.stages];
    const origPositions = {};
    for (const stageId of stageIds) {
      const pos = layout.positions[stageId];
      if (pos) origPositions[stageId] = { x: pos.x, y: pos.y };
    }

    const origGroupBounds = {};
    for (const gid of groupIds) {
      pinGroupBounds(gid);
      const box = layout.groupBounds[gid] || getGroupBox(gid);
      if (box) {
        origGroupBounds[gid] = {
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
        };
      }
    }

    groupDragState = {
      groupId,
      stageIds,
      groupIds,
      startX: e.clientX,
      startY: e.clientY,
      origPositions,
      origGroupBounds,
      pointerId: e.pointerId,
      moved: false,
    };

    const el = groupEls.get(groupId);
    if (el) {
      el.classList.add("is-dragging");
      el.setPointerCapture(e.pointerId);
    }
    document.addEventListener("pointermove", onGroupDragPointerMove);
    document.addEventListener("pointerup", onGroupDragPointerUp);
    document.addEventListener("pointercancel", onGroupDragPointerUp);
  }

  function onGroupPointerDown(e, groupId) {
    if (e.button !== 0) return;
    if (e.target.classList.contains("group-resize-handle")) return;
    e.stopPropagation();

    if (mode === "connect") {
      e.preventDefault();
      const ep = epGroup(groupId);
      if (!connectFromEp) {
        connectFromEp = ep;
        updateSelectionUI();
        updateModeHint();
        drawConnections();
      } else if (connectFromEp !== ep) {
        addConnection(connectFromEp, ep);
        connectFromEp = null;
        updateSelectionUI();
        updateModeHint();
      }
      return;
    }

    if (mode === "add-stage") return;

    selectGroup(groupId);
    startGroupDrag(e, groupId);
    e.preventDefault();
  }

  function selectGroup(id) {
    selectedGroupId = id;
    selectedNodeId = null;
    selectedConnId = null;
    selectedBoard = false;
    connectFromEp = null;
    updateSelectionUI();
    updateDeleteButton();
    updatePropertiesBar();
    drawConnections();
    drawGroupResizeHandles();
    drawBoardResizeHandles();
    applyBoardBounds();
  }

  function selectBoard() {
    selectedBoard = true;
    selectedNodeId = null;
    selectedGroupId = null;
    selectedConnId = null;
    connectFromEp = null;
    updateSelectionUI();
    updateDeleteButton();
    updatePropertiesBar();
    applyBoardBounds();
    drawConnections();
    drawGroupResizeHandles();
    drawBoardResizeHandles();
    updateModeHint();
  }

  function addCustomStage(x, y) {
    const id = "custom-" + ++customStageCounter;
    const isChannel = stageShape === SHAPE_CHANNEL;
    if (!layout.customStages) layout.customStages = [];
    layout.customStages.push({
      id,
      label: isChannel ? "New Channel" : "New Stage",
      shape: stageShape,
      count: 0,
    });
    layout.positions[id] = {
      x: Math.max(0, x - (isChannel ? 70 : 80)),
      y: Math.max(0, y - (isChannel ? 22 : 40)),
    };
    markDirty();
    buildNodes();
    bindNodes();
    selectNode(id);
  }

  function getNodeRect(stageId) {
    const el = nodeEls.get(stageId);
    const pos = layout.positions[stageId];
    if (!el || !pos) return null;

    if (IS_PRESENT) {
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      return {
        left: pos.x,
        top: pos.y,
        width: w,
        height: h,
        right: pos.x + w,
        bottom: pos.y + h,
        cx: pos.x + w / 2,
        cy: pos.y + h / 2,
      };
    }

    const bb = getBoardBounds();
    const boardRect = board.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const left = r.left - boardRect.left + board.scrollLeft - bb.x;
    const top = r.top - boardRect.top + board.scrollTop - bb.y;
    const w = r.width;
    const h = r.height;
    return {
      left,
      top,
      width: w,
      height: h,
      right: left + w,
      bottom: top + h,
      cx: left + w / 2,
      cy: top + h / 2,
    };
  }

  function clamp01(v) {
    return Math.max(0, Math.min(1, v));
  }

  function isStraightConn(conn) {
    return conn.routeType === ARROW_STRAIGHT;
  }

  function isBentConn(conn) {
    return !isStraightConn(conn);
  }

  function anchorOnBorder(rect, side, offset) {
    const t = clamp01(offset ?? 0.5);
    switch (side) {
      case "top":
        return { x: rect.left + rect.width * t, y: rect.top };
      case "bottom":
        return { x: rect.left + rect.width * t, y: rect.bottom };
      case "left":
        return { x: rect.left, y: rect.top + rect.height * t };
      case "right":
        return { x: rect.right, y: rect.top + rect.height * t };
      default:
        return { x: rect.cx, y: rect.cy };
    }
  }

  function pickAnchors(fromRect, toRect) {
    const dx = toRect.cx - fromRect.cx;
    const dy = toRect.cy - fromRect.cy;
    let fromSide, toSide;
    if (Math.abs(dx) >= Math.abs(dy)) {
      fromSide = dx >= 0 ? "right" : "left";
      toSide = dx >= 0 ? "left" : "right";
    } else {
      fromSide = dy >= 0 ? "bottom" : "top";
      toSide = dy >= 0 ? "top" : "bottom";
    }
    return {
      from: anchorOnBorder(fromRect, fromSide, 0.5),
      to: anchorOnBorder(toRect, toSide, 0.5),
      fromSide,
      toSide,
      fromOffset: 0.5,
      toOffset: 0.5,
    };
  }

  function projectToBorder(rect, pt) {
    const topX = Math.max(rect.left, Math.min(rect.right, pt.x));
    const leftY = Math.max(rect.top, Math.min(rect.bottom, pt.y));
    const candidates = [
      {
        side: "top",
        offset: rect.width ? (topX - rect.left) / rect.width : 0.5,
        point: { x: topX, y: rect.top },
        dist: Math.hypot(pt.x - topX, pt.y - rect.top),
      },
      {
        side: "bottom",
        offset: rect.width ? (topX - rect.left) / rect.width : 0.5,
        point: { x: topX, y: rect.bottom },
        dist: Math.hypot(pt.x - topX, pt.y - rect.bottom),
      },
      {
        side: "left",
        offset: rect.height ? (leftY - rect.top) / rect.height : 0.5,
        point: { x: rect.left, y: leftY },
        dist: Math.hypot(pt.x - rect.left, pt.y - leftY),
      },
      {
        side: "right",
        offset: rect.height ? (leftY - rect.top) / rect.height : 0.5,
        point: { x: rect.right, y: leftY },
        dist: Math.hypot(pt.x - rect.right, pt.y - leftY),
      },
    ];
    candidates.sort((a, b) => a.dist - b.dist);
    return candidates[0];
  }

  function setEndpointFromPoint(conn, isStart, pt, epOverride) {
    const ep = epOverride || (isStart ? conn.from : conn.to);
    const r = getEndpointRect(ep);
    if (!r) return;
    const proj = projectToBorder(r, pt);
    if (isStart) {
      conn.from = ep;
      conn.fromAnchor = proj.side;
      conn.fromOffset = proj.offset;
    } else {
      conn.to = ep;
      conn.toAnchor = proj.side;
      conn.toOffset = proj.offset;
    }
  }

  function getConnectionEndpoints(conn, fromR, toR) {
    let fromSide = conn.fromAnchor;
    let toSide = conn.toAnchor;
    let fromOffset = conn.fromOffset;
    let toOffset = conn.toOffset;
    if (!fromSide || !toSide) {
      const picked = pickAnchors(fromR, toR);
      fromSide = fromSide || picked.fromSide;
      toSide = toSide || picked.toSide;
      fromOffset = fromOffset ?? picked.fromOffset;
      toOffset = toOffset ?? picked.toOffset;
    }
    return {
      from: anchorOnBorder(fromR, fromSide, fromOffset ?? 0.5),
      to: anchorOnBorder(toR, toSide, toOffset ?? 0.5),
      fromSide,
      toSide,
    };
  }

  function routePath(from, to, fromSide, toSide) {
    const gap = 14;
    const pts = [from];
    const horizFrom = fromSide === "left" || fromSide === "right";
    const horizTo = toSide === "left" || toSide === "right";

    if (horizFrom && horizTo) {
      const midX = (from.x + to.x) / 2;
      pts.push({ x: midX, y: from.y });
      pts.push({ x: midX, y: to.y });
    } else if (!horizFrom && !horizTo) {
      const midY = (from.y + to.y) / 2;
      pts.push({ x: from.x, y: midY });
      pts.push({ x: to.x, y: midY });
    } else if (horizFrom) {
      const bendX = from.x + (fromSide === "right" ? gap : -gap);
      pts.push({ x: bendX, y: from.y });
      pts.push({ x: bendX, y: to.y });
    } else {
      const bendY = from.y + (fromSide === "bottom" ? gap : -gap);
      pts.push({ x: from.x, y: bendY });
      pts.push({ x: to.x, y: bendY });
    }
    pts.push(to);
    return pts;
  }

  function autoRoutePoints(conn) {
    const fromR = getEndpointRect(conn.from);
    const toR = getEndpointRect(conn.to);
    if (!fromR || !toR) return [];
    const { from, to, fromSide, toSide } = getConnectionEndpoints(conn, fromR, toR);
    return routePath(from, to, fromSide, toSide);
  }

  function ensureWaypoints(conn) {
    if (isStraightConn(conn)) return;
    if (conn.waypoints && conn.waypoints.length) return;
    const pts = autoRoutePoints(conn);
    if (pts.length <= 2) return;
    conn.waypoints = pts.slice(1, -1).map((p) => ({ x: p.x, y: p.y }));
  }

  function resolveConnectionPoints(conn) {
    const fromR = getEndpointRect(conn.from);
    const toR = getEndpointRect(conn.to);
    if (!fromR || !toR) return [];
    const { from, to, fromSide, toSide } = getConnectionEndpoints(conn, fromR, toR);
    if (isStraightConn(conn)) {
      return [from, to];
    }
    if (conn.waypoints && conn.waypoints.length) {
      return [from, ...conn.waypoints.map((p) => ({ x: p.x, y: p.y })), to];
    }
    return routePath(from, to, fromSide, toSide);
  }

  function getEndpointSide(conn, isStart) {
    if (isStart && conn.fromAnchor) return conn.fromAnchor;
    if (!isStart && conn.toAnchor) return conn.toAnchor;
    const fromR = getEndpointRect(conn.from);
    const toR = getEndpointRect(conn.to);
    if (!fromR || !toR) return isStart ? "right" : "left";
    const picked = pickAnchors(fromR, toR);
    return isStart ? picked.fromSide : picked.toSide;
  }

  function distToSegment(p, a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len2 = dx * dx + dy * dy;
    if (len2 === 0) return Math.hypot(p.x - a.x, p.y - a.y);
    let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const px = a.x + t * dx;
    const py = a.y + t * dy;
    return Math.hypot(p.x - px, p.y - py);
  }

  function pointsToPath(points) {
    return points.map((p, i) => (i === 0 ? "M" : "L") + p.x + " " + p.y).join(" ");
  }

  function labelPosition(points) {
    if (points.length < 2) return { x: 0, y: 0, anchor: "left" };
    let bestLen = 0;
    let bestSeg = 0;
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i];
      const b = points[i + 1];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      if (len > bestLen) {
        bestLen = len;
        bestSeg = i;
      }
    }
    const a = points[bestSeg];
    const b = points[bestSeg + 1];
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;
    const offset = 12;
    const perpX = (-dy / len) * offset;
    const perpY = (dx / len) * offset;
    const anchor = bestSeg % 2 === 0 ? "left" : "right";
    const sign = anchor === "left" ? 1 : -1;
    return {
      x: mx + perpX * sign,
      y: my + perpY * sign,
      anchor,
    };
  }

  function getConnLabelPosition(conn, points) {
    const auto = labelPosition(points);
    if (conn.labelOffset) {
      return {
        x: auto.x + (conn.labelOffset.dx || 0),
        y: auto.y + (conn.labelOffset.dy || 0),
        anchor: conn.labelAnchor || auto.anchor,
      };
    }
    return auto;
  }

  function applyLabelStyle(span, lp) {
    span.style.left = lp.x + "px";
    span.style.top = lp.y + "px";
    if (lp.anchor === "left") {
      span.style.transform = "translate(-100%, -50%)";
      span.style.textAlign = "right";
    } else {
      span.style.transform = "translate(0, -50%)";
      span.style.textAlign = "left";
    }
  }

  /** Push start/end handles outward so they are not hidden under stage boxes */
  function getHandleDisplayPosition(conn, pt, idx, pointCount) {
    const isStart = idx === 0;
    const isEnd = idx === pointCount - 1;
    if (!isStart && !isEnd) return pt;
    const offset = 22;
    const side = getEndpointSide(conn, isStart);
    switch (side) {
      case "top":
        return { x: pt.x, y: pt.y - offset };
      case "bottom":
        return { x: pt.x, y: pt.y + offset };
      case "left":
        return { x: pt.x - offset, y: pt.y };
      case "right":
        return { x: pt.x + offset, y: pt.y };
      default:
        return pt;
    }
  }

  function drawConnectionHandles(conn, points) {
    if (IS_PRESENT || !handlesLayer || conn.id !== selectedConnId || mode !== "select") {
      if (handlesLayer) handlesLayer.innerHTML = "";
      return;
    }

    handlesLayer.innerHTML = "";

    points.forEach((pt, idx) => {
      const isEndpoint = idx === 0 || idx === points.length - 1;
      if (!isEndpoint && isStraightConn(conn)) return;

      const displayPt = getHandleDisplayPosition(conn, pt, idx, points.length);
      const handle = document.createElement("div");
      handle.className =
        "conn-handle" + (isEndpoint ? " conn-handle--endpoint" : " conn-handle--bend");
      handle.setAttribute("data-conn-id", conn.id);
      handle.setAttribute("data-handle-type", isEndpoint ? (idx === 0 ? "start" : "end") : "bend");
      if (!isEndpoint) handle.setAttribute("data-bend-index", String(idx - 1));
      handle.style.left = displayPt.x + "px";
      handle.style.top = displayPt.y + "px";
      handle.title = isEndpoint
        ? idx === 0
          ? "Drag along stage border or to another stage"
          : "Drag along stage border or to another stage"
        : "Drag to move bend · double-click line to add another";
      handlesLayer.appendChild(handle);
    });
  }

  function updateConnectionGraphics(connId) {
    const conn = getConn(connId);
    if (!conn) return;
    const points = resolveConnectionPoints(conn);
    if (!points.length) return;
    const pathD = pointsToPath(points);

    svg.querySelectorAll('[data-conn-id="' + connId + '"]').forEach((el) => {
      if (el.tagName.toLowerCase() === "path") {
        el.setAttribute("d", pathD);
      }
    });
    if (IS_PRESENT) {
      svg.querySelectorAll('.canvas-conn-line-flow[data-conn-id="' + connId + '"]').forEach((el) => {
        el.setAttribute("d", pathD);
      });
    }

    const span = labelsLayer.querySelector(
      '.canvas-conn-label[data-conn-id="' + connId + '"]'
    );
    if (span) {
      span.textContent = formatConnectionLabel(conn);
      applyLabelStyle(span, getConnLabelPosition(conn, points));
    }

    if (connId === selectedConnId && handlesLayer) {
      const handles = handlesLayer.querySelectorAll(
        '.conn-handle[data-conn-id="' + connId + '"]'
      );
      points.forEach((pt, idx) => {
        const h = handles[idx];
        if (h) {
          const displayPt = getHandleDisplayPosition(conn, pt, idx, points.length);
          h.style.left = displayPt.x + "px";
          h.style.top = displayPt.y + "px";
        }
      });
    }
  }

  function drawConnections() {
    const bb = getBoardBounds();
    const w = bb.width;
    const h = bb.height;
    svg.setAttribute("width", w);
    svg.setAttribute("height", h);
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    svg.innerHTML =
      '<defs><marker id="arrowhead-canvas" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto" markerUnits="userSpaceOnUse">' +
      '<path d="M 0 0 L 10 5 L 0 10 Z" class="flow-arrow-head" /></marker></defs>';

    labelsLayer.innerHTML = "";

    let selectedPoints = null;
    let selectedConn = null;

    for (const conn of layout.connections) {
      const points = resolveConnectionPoints(conn);
      if (!points.length) continue;
      const pathD = pointsToPath(points);
      const isSelected = !IS_PRESENT && conn.id === selectedConnId;

      if (isSelected) {
        selectedPoints = points;
        selectedConn = conn;
      }

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", pathD);
      path.setAttribute("fill", "none");
      path.setAttribute(
        "class",
        "canvas-conn-line" +
          (isStraightConn(conn) ? " canvas-conn-line--straight" : " canvas-conn-line--bent") +
          (isSelected ? " is-selected" : "")
      );
      path.setAttribute("marker-end", "url(#arrowhead-canvas)");
      path.setAttribute("data-conn-id", conn.id);
      if (IS_PRESENT) path.setAttribute("pathLength", "100");
      svg.appendChild(path);

      if (IS_PRESENT) {
        const flowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
        flowPath.setAttribute("d", pathD);
        flowPath.setAttribute("fill", "none");
        flowPath.setAttribute("pathLength", "100");
        flowPath.setAttribute("class", "canvas-conn-line-flow");
        flowPath.setAttribute("data-conn-id", conn.id);
        const delay = (layout.connections.indexOf(conn) % 8) * 0.18;
        flowPath.style.animationDelay = delay + "s";
        svg.appendChild(flowPath);
      }

      if (!IS_PRESENT) {
        const hit = document.createElementNS("http://www.w3.org/2000/svg", "path");
        hit.setAttribute("d", pathD);
        hit.setAttribute("fill", "none");
        hit.setAttribute("stroke-width", "16");
        hit.setAttribute("class", "canvas-conn-hit" + (isSelected ? " is-selected" : ""));
        hit.setAttribute("data-conn-id", conn.id);
        hit.addEventListener("pointerdown", (e) => {
          if (e.button !== 0 || mode !== "select") return;
          e.stopPropagation();
          e.preventDefault();
          selectConnection(conn.id);
        });
        svg.appendChild(hit);
      }

      const lp = getConnLabelPosition(conn, points);
      const span = document.createElement("span");
      span.className = "canvas-conn-label" + (isSelected ? " is-selected" : "");
      span.setAttribute("data-conn-id", conn.id);
      span.textContent = formatConnectionLabel(conn);
      applyLabelStyle(span, lp);
      if (!IS_PRESENT) {
        span.title = isSelected
          ? "Drag to move label · double-click to edit"
          : "Double-click to edit label";
      }
      labelsLayer.appendChild(span);
    }

    if (!IS_PRESENT) {
      board.classList.toggle("has-conn-selected", !!selectedConnId);
    }

    if (!IS_PRESENT && selectedConn && selectedPoints) {
      if (!handleDrag) {
        drawConnectionHandles(selectedConn, selectedPoints);
      } else {
        updateConnectionGraphics(selectedConn.id);
      }
    } else if (handlesLayer && !handleDrag) {
      handlesLayer.innerHTML = "";
    }

    if (connectFromEp && mode === "connect") {
      const fromR = getEndpointRect(connectFromEp);
      if (fromR) {
        const from = anchorOnBorder(fromR, "right", 0.5);
        const preview = document.createElementNS("http://www.w3.org/2000/svg", "line");
        preview.setAttribute("class", "canvas-conn-preview");
        preview.setAttribute("x1", from.x);
        preview.setAttribute("y1", from.y);
        preview.setAttribute("x2", from.x + 40);
        preview.setAttribute("y2", from.y);
        svg.appendChild(preview);
      }
    }
  }

  function startLabelEdit(connId) {
    const conn = getConn(connId);
    if (!conn) return;

    if (selectedConnId !== connId) {
      selectConnection(connId);
    }

    const beginEdit = () => {
      const span = labelsLayer.querySelector(
        '.canvas-conn-label[data-conn-id="' + connId + '"]'
      );
      if (!span || span.classList.contains("is-editing")) return;

      span.textContent = conn.label || DEFAULT_CONN_LABEL;
      span.contentEditable = "true";
      span.classList.add("is-editing");
      span.focus();
      const range = document.createRange();
      range.selectNodeContents(span);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);

      const finish = () => {
        span.contentEditable = "false";
        span.classList.remove("is-editing");
        const firstLine = span.textContent.trim().split("\n")[0].trim();
        conn.label = firstLine || DEFAULT_CONN_LABEL;
        span.textContent = formatConnectionLabel(conn);
        span.removeEventListener("blur", finish);
        span.removeEventListener("keydown", onKey);
        markDirty();
        if (connLabelInput) connLabelInput.value = conn.label;
        drawConnections();
      };

      const onKey = (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          span.blur();
        }
        if (e.key === "Escape") {
          e.preventDefault();
          span.textContent = formatConnectionLabel(conn);
          span.blur();
        }
      };

      span.addEventListener("blur", finish);
      span.addEventListener("keydown", onKey);
    };

    requestAnimationFrame(beginEdit);
  }


  function updateArrowTypeUI() {
    document.querySelectorAll("[data-arrow-type]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-arrow-type") === arrowType);
    });
    const picker = document.getElementById("arrow-type-picker");
    if (picker) {
      picker.classList.toggle("is-required", mode === "connect");
    }
  }

  function setArrowType(type) {
    arrowType = type === ARROW_STRAIGHT ? ARROW_STRAIGHT : ARROW_BENT;
    updateArrowTypeUI();
    updateModeHint();
  }

  function updateStageShapeUI() {
    document.querySelectorAll("[data-stage-shape]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-stage-shape") === stageShape);
    });
    const picker = document.getElementById("stage-shape-picker");
    if (picker) picker.classList.toggle("is-required", mode === "add-stage");
  }

  function setStageShape(shape) {
    stageShape = normalizeShapeType(shape);
    updateStageShapeUI();
    updateModeHint();
  }

  function setMode(next) {
    mode = next;
    connectFromEp = null;
    document.querySelectorAll("[data-tool]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-tool") === mode);
    });
    board.classList.toggle("mode-connect", mode === "connect");
    board.classList.toggle("mode-select", mode === "select");
    board.classList.toggle("mode-add-stage", mode === "add-stage");
    updateArrowTypeUI();
    updateStageShapeUI();
    updateModeHint();
    updateSelectionUI();
    drawConnections();
    drawGroupResizeHandles();
    drawBoardResizeHandles();
  }

  function updateModeHint() {
    if (!modeHint) return;
    if (mode === "connect") {
      const typeLabel = arrowType === ARROW_STRAIGHT ? "straight" : "bent";
      modeHint.textContent = connectFromEp
        ? "Click target stage or group box to complete the " + typeLabel + " arrow."
        : "Choose Straight/Bent, then click source and target (stage or group).";
    } else if (mode === "add-stage") {
      const shapeLabel = stageShape === SHAPE_CHANNEL ? "channel" : "stage";
      modeHint.textContent =
        "Choose Stage or Channel under Shape type, then click on the canvas to place a new " +
        shapeLabel +
        ".";
    } else if (selectedBoard) {
      modeHint.textContent =
        "Canvas selected — drag edge handles to resize. Click empty space elsewhere to deselect.";
    } else {
      modeHint.textContent =
        "Select a stage, group, or arrow. Drag a group box to move it and its stages together. Save to store.";
    }
  }

  function updateSelectionUI() {
    nodeEls.forEach((el, id) => {
      el.classList.toggle("is-selected", id === selectedNodeId);
      el.classList.toggle(
        "is-connect-source",
        connectFromEp === epStage(id)
      );
    });
    groupEls.forEach((el, id) => {
      el.classList.toggle("is-selected", id === selectedGroupId);
      el.classList.toggle("is-connect-source", connectFromEp === epGroup(id));
    });
  }

  function selectNode(id) {
    selectedNodeId = id;
    selectedGroupId = null;
    selectedConnId = null;
    selectedBoard = false;
    connectFromEp = null;
    updateSelectionUI();
    updateDeleteButton();
    updatePropertiesBar();
    drawConnections();
    drawGroupResizeHandles();
    drawBoardResizeHandles();
    applyBoardBounds();
  }

  function selectConnection(id) {
    selectedConnId = id;
    selectedNodeId = null;
    selectedGroupId = null;
    selectedBoard = false;
    connectFromEp = null;
    updateSelectionUI();
    updateDeleteButton();
    updatePropertiesBar();
    drawConnections();
    drawGroupResizeHandles();
    drawBoardResizeHandles();
    applyBoardBounds();
  }

  function clearSelection() {
    selectedNodeId = null;
    selectedGroupId = null;
    selectedConnId = null;
    selectedBoard = false;
    connectFromEp = null;
    updateSelectionUI();
    updateDeleteButton();
    updatePropertiesBar();
    drawConnections();
    drawGroupResizeHandles();
    drawBoardResizeHandles();
    applyBoardBounds();
  }

  function addConnection(fromEp, toEp) {
    const exists = layout.connections.some((c) => c.from === fromEp && c.to === toEp);
    if (exists) return;
    const id = "conn-" + ++connIdCounter;
    const fromR = getEndpointRect(fromEp);
    const toR = getEndpointRect(toEp);
    const picked = fromR && toR ? pickAnchors(fromR, toR) : { fromSide: "right", toSide: "left" };
    layout.connections.push({
      id,
      from: fromEp,
      to: toEp,
      label: DEFAULT_CONN_LABEL,
      routeType: arrowType,
      fromAnchor: picked.fromSide,
      toAnchor: picked.toSide,
      fromOffset: picked.fromOffset ?? 0.5,
      toOffset: picked.toOffset ?? 0.5,
      waypoints: null,
      transitionRate: null,
    });
    markDirty();
    selectConnection(id);
  }

  function deleteSelectedConnection() {
    if (!selectedConnId) return;
    layout.connections = layout.connections.filter((c) => c.id !== selectedConnId);
    selectedConnId = null;
    updateDeleteButton();
    updatePropertiesBar();
    markDirty();
    drawConnections();
  }

  function addWaypointAt(conn, clientX, clientY) {
    if (isStraightConn(conn)) return;
    ensureWaypoints(conn);
    const pt = clientToBoard(clientX, clientY);
    const points = resolveConnectionPoints(conn);
    let bestSeg = 0;
    let bestDist = Infinity;
    for (let i = 0; i < points.length - 1; i++) {
      const d = distToSegment(pt, points[i], points[i + 1]);
      if (d < bestDist) {
        bestDist = d;
        bestSeg = i;
      }
    }
    if (!conn.waypoints) conn.waypoints = [];
    const insertAt = Math.max(0, Math.min(bestSeg, conn.waypoints.length));
    conn.waypoints.splice(insertAt, 0, { x: Math.round(pt.x), y: Math.round(pt.y) });
    markDirty();
    drawConnections();
  }

  function onHandlePointerDown(e) {
    const handle = e.target.closest(".conn-handle");
    if (!handle || e.button !== 0 || mode !== "select") return;
    const connId = handle.getAttribute("data-conn-id");
    const type = handle.getAttribute("data-handle-type");
    const conn = getConn(connId);
    if (!conn) return;

    e.stopPropagation();
    e.preventDefault();

    if (selectedConnId !== connId) {
      selectConnection(connId);
    }

    if (type === "bend") {
      ensureWaypoints(conn);
    }

    handleDrag = {
      connId,
      type,
      bendIndex: type === "bend" ? Number(handle.getAttribute("data-bend-index")) : -1,
      pointerId: e.pointerId,
    };

    board.setPointerCapture(e.pointerId);
    document.addEventListener("pointermove", onHandlePointerMove);
    document.addEventListener("pointerup", onHandlePointerUp);
    document.addEventListener("pointercancel", onHandlePointerUp);
  }

  function onHandlePointerMove(e) {
    if (!handleDrag || e.pointerId !== handleDrag.pointerId) return;
    const conn = getConn(handleDrag.connId);
    if (!conn) return;

    const pt = clientToBoard(e.clientX, e.clientY);

    if (handleDrag.type === "start" || handleDrag.type === "end") {
      const ep =
        findEndpointAtPoint(pt) ||
        (handleDrag.type === "start" ? conn.from : conn.to);
      setEndpointFromPoint(conn, handleDrag.type === "start", pt, ep);
    } else if (handleDrag.type === "bend") {
      ensureWaypoints(conn);
      if (conn.waypoints[handleDrag.bendIndex]) {
        conn.waypoints[handleDrag.bendIndex] = { x: pt.x, y: pt.y };
      }
    }

    updateConnectionGraphics(handleDrag.connId);
  }

  function onHandlePointerUp(e) {
    if (!handleDrag || e.pointerId !== handleDrag.pointerId) return;
    const conn = getConn(handleDrag.connId);
    if (conn) markDirty();
    try {
      board.releasePointerCapture(e.pointerId);
    } catch (_) {}
    handleDrag = null;
    document.removeEventListener("pointermove", onHandlePointerMove);
    document.removeEventListener("pointerup", onHandlePointerUp);
    document.removeEventListener("pointercancel", onHandlePointerUp);
    drawConnections();
  }

  function onNodePointerDown(e, stageId) {
    if (e.button !== 0) return;
    const el = nodeEls.get(stageId);
    if (!el) return;

    if (mode === "connect") {
      e.preventDefault();
      const ep = epStage(stageId);
      if (!connectFromEp) {
        connectFromEp = ep;
        updateSelectionUI();
        updateModeHint();
        drawConnections();
      } else if (connectFromEp !== ep) {
        addConnection(connectFromEp, ep);
        connectFromEp = null;
        updateSelectionUI();
        updateModeHint();
      }
      return;
    }

    if (mode === "add-stage") return;

    selectNode(stageId);
    const pos = layout.positions[stageId];
    dragState = {
      id: stageId,
      startX: e.clientX,
      startY: e.clientY,
      origX: pos.x,
      origY: pos.y,
      moved: false,
    };
    el.setPointerCapture(e.pointerId);
    el.classList.add("is-dragging");
    e.preventDefault();
  }

  function onNodePointerMove(e) {
    if (!dragState || dragState.id !== e.currentTarget.getAttribute("data-stage")) return;
    const dx = e.clientX - dragState.startX;
    const dy = e.clientY - dragState.startY;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) dragState.moved = true;
    const x = Math.max(0, dragState.origX + dx);
    const y = Math.max(0, dragState.origY + dy);
    layout.positions[dragState.id] = { x, y };
    const el = nodeEls.get(dragState.id);
    el.style.left = x + "px";
    el.style.top = y + "px";
    updateGroupBoxes();
    drawConnections();
  }

  function onNodePointerUp(e) {
    const el = e.currentTarget;
    const stageId = el.getAttribute("data-stage");
    el.classList.remove("is-dragging");
    if (dragState && dragState.id === stageId) {
      if (dragState.moved) {
        markDirty();
        updateGroupBoxes();
      }
      dragState = null;
    }
    try {
      el.releasePointerCapture(e.pointerId);
    } catch (_) {}
  }

  function bindNodes() {
    if (IS_PRESENT) return;
    nodeEls.forEach((el, id) => {
      el.addEventListener("pointerdown", (e) => onNodePointerDown(e, id));
      el.addEventListener("pointermove", onNodePointerMove);
      el.addEventListener("pointerup", onNodePointerUp);
      el.addEventListener("pointercancel", onNodePointerUp);
    });
  }

  function refreshStats() {
    const counts = getCounts(layout);
    const stats = getStageStats(counts, layout);
    const byId = Object.fromEntries(stats.map((s) => [s.id, s]));
    nodeEls.forEach((el, id) => {
      if (byId[id]) renderNodeContent(el, byId[id]);
    });
    refreshPresentSummary(counts);
  }

  function refreshPresentSummary(counts) {
    if (!IS_PRESENT) return;
    const panel = document.getElementById("present-summary");
    if (!panel) return;
    const data = counts || getCounts(layout);
    const metrics = calcPresentationMetrics(data, layout);
    const usersEl = document.getElementById("metric-users");
    const liveCreditEl = document.getElementById("metric-live-credit-holder");
    const liveCustomerEl = document.getElementById("metric-live-customer");
    const activeCustomerEl = document.getElementById("metric-active-customer");
    if (usersEl) usersEl.textContent = formatNumber(metrics.users);
    if (liveCreditEl) liveCreditEl.textContent = formatNumber(metrics.liveCreditHolder);
    if (liveCustomerEl) liveCustomerEl.textContent = formatNumber(metrics.liveCustomer);
    if (activeCustomerEl) activeCustomerEl.textContent = formatNumber(metrics.activeCustomer);
  }

  function updateMonthNavUI() {
    if (!monthNav) return;
    if (!availableMonths.length) {
      monthNav.hidden = true;
      return;
    }
    monthNav.hidden = false;
    if (monthLabel) {
      monthLabel.textContent = currentMonth ? formatJalaliMonth(currentMonth) : "—";
    }
    const idx = currentMonth ? availableMonths.indexOf(currentMonth) : -1;
    if (monthPrevBtn) monthPrevBtn.disabled = idx <= 0;
    if (monthNextBtn) monthNextBtn.disabled = idx < 0 || idx >= availableMonths.length - 1;
  }

  async function loadMonthCounts(month) {
    if (!month) return;
    currentMonth = month;
    setSelectedMonth(month);
    updateMonthNavUI();
    const data = await fetchCountsForMonth(month);
    if (data && typeof data === "object") {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      refreshStats();
    }
  }

  async function navigateMonth(delta) {
    const idx = availableMonths.indexOf(currentMonth);
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= availableMonths.length) return;
    await loadMonthCounts(availableMonths[newIdx]);
  }

  function initMonthNav() {
    if (!monthNav || !availableMonths.length) {
      updateMonthNavUI();
      return;
    }
    currentMonth = getSelectedMonth();
    if (!currentMonth || !availableMonths.includes(currentMonth)) {
      currentMonth = monthsMeta.latest || availableMonths[availableMonths.length - 1];
      setSelectedMonth(currentMonth);
    }
    updateMonthNavUI();
    monthPrevBtn?.addEventListener("click", () => navigateMonth(-1));
    monthNextBtn?.addEventListener("click", () => navigateMonth(1));
  }

  function render() {
    applyBoardBounds();
    buildGroupBoxes();
    buildNodes();
    bindNodes();
    requestAnimationFrame(() => {
      updateGroupBoxes();
      drawConnections();
      if (IS_PRESENT) {
        schedulePresentFit();
      } else {
        drawGroupResizeHandles();
        drawBoardResizeHandles();
      }
    });
    refreshStats();
    if (!IS_PRESENT) {
      updateDeleteButton();
      updatePropertiesBar();
      updateSaveButton();
      const el = document.getElementById("updated-at");
      if (el) {
        el.textContent = isDirty
          ? "Unsaved changes · click Save to store in database"
          : "Click Save to store changes · counts editable in Data gathering";
      }
    }
  }

  if (IS_PRESENT) {
    window.addEventListener("resize", schedulePresentFit);
    window.addEventListener("storage", (e) => {
      if (e.key === STORAGE_KEY) refreshStats();
      if (e.key === SELECTED_MONTH_KEY) {
        const selected = getSelectedMonth();
        if (selected && availableMonths.includes(selected) && selected !== currentMonth) {
          loadMonthCounts(selected);
        }
      }
      if (e.key === LAYOUT_STORAGE_KEY) {
        layout = getLayout();
        render();
      }
    });
    window.addEventListener("focus", async () => {
      const selected = getSelectedMonth();
      if (selected && availableMonths.includes(selected) && selected !== currentMonth) {
        await loadMonthCounts(selected);
      } else {
        refreshStats();
      }
    });
    board.addEventListener("dblclick", () => {
      if (document.fullscreenElement) {
        document.exitFullscreen?.();
      } else {
        document.documentElement.requestFullscreen?.();
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && document.fullscreenElement) {
        document.exitFullscreen?.();
      }
      if (e.key === "f" || e.key === "F") {
        if (document.fullscreenElement) document.exitFullscreen?.();
        else document.documentElement.requestFullscreen?.();
      }
    });
    initMonthNav();
    render();
    return;
  }

  board.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const t = e.target;
    if (t.classList.contains("group-resize-handle")) return;
    if (t.classList.contains("board-resize-handle")) return;

    if (mode === "add-stage") {
      if (
        t === board ||
        t.classList.contains("canvas-board__inner") ||
        t.classList.contains("canvas-groups")
      ) {
        const pt = clientToBoard(e.clientX, e.clientY);
        addCustomStage(pt.x, pt.y);
        e.preventDefault();
      }
      return;
    }

    if (
      t === board ||
      t.classList.contains("canvas-board__inner") ||
      t.classList.contains("canvas-groups")
    ) {
      if (mode === "select") selectBoard();
      if (mode === "connect") {
        connectFromEp = null;
        updateSelectionUI();
        updateModeHint();
        drawConnections();
      }
    }
  });

  svg.addEventListener("dblclick", (e) => {
    const hit = e.target.closest("[data-conn-id]");
    if (!hit || mode !== "select") return;
    e.stopPropagation();
    const conn = getConn(hit.getAttribute("data-conn-id"));
    if (!conn) return;
    selectConnection(conn.id);
    addWaypointAt(conn, e.clientX, e.clientY);
  });

  document.querySelectorAll("[data-tool]").forEach((btn) => {
    btn.addEventListener("click", () => setMode(btn.getAttribute("data-tool")));
  });

  document.querySelectorAll("[data-arrow-type]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setArrowType(btn.getAttribute("data-arrow-type"));
      if (mode !== "connect") setMode("connect");
    });
  });

  deleteConnBtn?.addEventListener("click", deleteSelectedConnection);
  deleteStageBtn?.addEventListener("click", deleteSelectedStage);
  saveBtn?.addEventListener("click", saveAll);

  connLabelInput?.addEventListener("input", () => {
    const conn = selectedConnId ? getConn(selectedConnId) : null;
    if (!conn) return;
    conn.label = connLabelInput.value.trim() || DEFAULT_CONN_LABEL;
    markDirty();
    drawConnections();
  });

  stageNameInput?.addEventListener("input", () => {
    if (!selectedNodeId) return;
    setStageName(selectedNodeId, stageNameInput.value);
  });

  groupResizeLayer?.addEventListener("pointerdown", onGroupResizePointerDown);
  boardResizeLayer?.addEventListener("pointerdown", onBoardResizePointerDown);

  document.querySelectorAll("[data-stage-shape]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setStageShape(btn.getAttribute("data-stage-shape"));
      if (mode !== "add-stage") setMode("add-stage");
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      connectFromEp = null;
      clearSelection();
      updateModeHint();
    }
  });

  window.addEventListener("resize", () =>
    requestAnimationFrame(() => {
      applyBoardBounds();
      updateGroupBoxes();
      drawConnections();
      drawBoardResizeHandles();
    })
  );
  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE_KEY) refreshStats();
    if (e.key === SELECTED_MONTH_KEY) {
      const selected = getSelectedMonth();
      if (selected && availableMonths.includes(selected) && selected !== currentMonth) {
        loadMonthCounts(selected);
      }
    }
    if (e.key === LAYOUT_STORAGE_KEY) {
      layout = getLayout();
      buildNodes();
      bindNodes();
      requestAnimationFrame(() => {
        applyBoardBounds();
        updateGroupBoxes();
        drawConnections();
        drawBoardResizeHandles();
      });
    }
  });
  window.addEventListener("focus", async () => {
    const selected = getSelectedMonth();
    if (selected && availableMonths.includes(selected) && selected !== currentMonth) {
      await loadMonthCounts(selected);
    } else {
      refreshStats();
    }
  });

  handlesLayer?.addEventListener("pointerdown", onHandlePointerDown);

  labelsLayer?.addEventListener("pointerdown", onLabelPointerDown);

  labelsLayer?.addEventListener("dblclick", (e) => {
    const span = e.target.closest(".canvas-conn-label");
    if (!span || mode !== "select") return;
    if (suppressLabelEdit) {
      suppressLabelEdit = false;
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    startLabelEdit(span.getAttribute("data-conn-id"));
  });

  document.getElementById("btn-present")?.addEventListener("click", () => {
    window.open("/lifecycle/present", "_blank", "noopener,noreferrer");
  });

  updateArrowTypeUI();
  updateStageShapeUI();
  updatePropertiesBar();
  updateSaveButton();
  setMode("select");
  initMonthNav();
  render();
})();
