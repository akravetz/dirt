const PROBE_IDS = [1, 2, 3];
const LIVE_WINDOW_S = 60;
const CAPTURE_DURATION_S = 60;
const CAPTURE_POLL_INTERVAL_S = 2;
const CALIBRATION_DURATION_S = 900;
const CALIBRATION_INTERVAL_MS = 2000;

const state = {
  info: null,
  liveStatus: null,
  liveStatusError: null,
  samples: null,
  samplesError: null,
  session: null,
  summary: null,
  pendingPreview: null,
  capture: null,
  refreshing: false,
  probeForms: Object.fromEntries(
    PROBE_IDS.map((probeId) => [
      probeId,
      {
        placement_label: "",
        note: "",
        input_ec_ms_cm_override: "",
        input_ph_override: "",
      },
    ]),
  ),
};

const el = {
  alert: document.querySelector("#alert"),
  controllerUrl: document.querySelector("#controller-url"),
  sessionId: document.querySelector("#session-id"),
  renewCalibration: document.querySelector("#renew-calibration"),
  connectionState: document.querySelector("#connection-state"),
  firmwareVersion: document.querySelector("#firmware-version"),
  samplesState: document.querySelector("#samples-state"),
  calibrationState: document.querySelector("#calibration-state"),
  calibrationInterval: document.querySelector("#calibration-interval"),
  calibrationRemaining: document.querySelector("#calibration-remaining"),
  inputEc: document.querySelector("#input-ec"),
  inputPh: document.querySelector("#input-ph"),
  saveReference: document.querySelector("#save-reference"),
  captureProgress: document.querySelector("#capture-progress"),
  probeGrid: document.querySelector("#probe-grid"),
  acceptedCaptures: document.querySelector("#accepted-captures"),
  summaryTable: document.querySelector("#summary-table"),
  completeSession: document.querySelector("#complete-session"),
  markdownSummary: document.querySelector("#markdown-summary"),
  csvSummary: document.querySelector("#csv-summary"),
  copyMarkdown: document.querySelector("#copy-markdown"),
  copyCsv: document.querySelector("#copy-csv"),
  previewDialog: document.querySelector("#preview-dialog"),
  previewContent: document.querySelector("#preview-content"),
  acceptPreview: document.querySelector("#accept-preview"),
  rejectPreview: document.querySelector("#reject-preview"),
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindEvents();
  renderProbes();
  renderSummary();
  await refreshInfo();
  await refreshLive();
  await ensureSession();
  await refreshSummary();
  window.setInterval(refreshLive, 2000);
}

function bindEvents() {
  el.renewCalibration.addEventListener("click", () => renewCalibration());
  el.saveReference.addEventListener("click", () => saveWetReference());
  el.completeSession.addEventListener("click", () => completeSession());
  el.copyMarkdown.addEventListener("click", () =>
    copyText(el.markdownSummary.value, "Markdown copied"),
  );
  el.copyCsv.addEventListener("click", () =>
    copyText(el.csvSummary.value, "CSV copied"),
  );
  el.acceptPreview.addEventListener("click", () => acceptPreview());
  el.rejectPreview.addEventListener("click", () => rejectPreview());
  el.probeGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-start-capture]");
    if (!button) {
      return;
    }
    startCapture(Number(button.dataset.startCapture));
  });
  el.probeGrid.addEventListener("input", (event) => {
    const field = event.target.dataset.field;
    const probeId = Number(event.target.dataset.probe);
    if (!field || !PROBE_IDS.includes(probeId)) {
      return;
    }
    state.probeForms[probeId][field] = event.target.value;
  });
}

async function apiJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "content-type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }
    throw new Error(`${response.status} ${detail}`);
  }
  return response.json();
}

async function refreshInfo() {
  try {
    state.info = await apiJson("/api/info");
    el.controllerUrl.textContent = `controller: ${state.info.controller_url}`;
  } catch (error) {
    showAlert(`Info request failed: ${error.message}`, "error");
  }
}

async function refreshLive() {
  if (state.refreshing) {
    return;
  }
  state.refreshing = true;
  try {
    const [statusResult, samplesResult] = await Promise.allSettled([
      apiJson("/api/controller/status"),
      apiJson(`/api/controller/samples?window_s=${LIVE_WINDOW_S}`),
    ]);

    if (statusResult.status === "fulfilled") {
      state.liveStatus = statusResult.value;
      state.liveStatusError = null;
    } else {
      state.liveStatus = null;
      state.liveStatusError = statusResult.reason;
    }

    if (samplesResult.status === "fulfilled") {
      state.samples = samplesResult.value;
      state.samplesError = null;
    } else {
      state.samples = null;
      state.samplesError = samplesResult.reason;
    }
    renderStatus();
    if (!probeGridInputFocused()) {
      renderProbes();
    }
    renderCaptureProgress();
  } finally {
    state.refreshing = false;
  }
}

async function ensureSession() {
  if (state.session) {
    return state.session;
  }

  const savedSessionId = window.localStorage.getItem("substrateCalibrationSessionId");
  if (savedSessionId) {
    try {
      const session = await apiJson(`/api/sessions/${encodeURIComponent(savedSessionId)}`);
      setSession(session);
      return session;
    } catch {
      window.localStorage.removeItem("substrateCalibrationSessionId");
    }
  }

  try {
    const session = await apiJson("/api/sessions", {
      method: "POST",
      body: JSON.stringify(referencePayload()),
    });
    setSession(session);
    return session;
  } catch (error) {
    el.sessionId.textContent = "session: unavailable";
    showAlert(`Session creation failed: ${error.message}`, "error");
    return null;
  }
}

function setSession(session) {
  state.session = session;
  window.localStorage.setItem("substrateCalibrationSessionId", session.id);
  el.sessionId.textContent = `session: ${session.id} (${session.status})`;
  el.inputEc.value = valueForInput(session.input_ec_ms_cm);
  el.inputPh.value = valueForInput(session.input_ph);
  el.saveReference.disabled = session.status === "completed";
  el.completeSession.disabled = session.status === "completed";
  el.completeSession.textContent =
    session.status === "completed" ? "Session completed" : "Complete session";
}

async function saveWetReference({ silent = false } = {}) {
  const session = await ensureSession();
  if (!session || session.status === "completed") {
    return;
  }
  try {
    const updated = await apiJson(`/api/sessions/${encodeURIComponent(session.id)}/wet-reference`, {
      method: "PATCH",
      body: JSON.stringify(referencePayload()),
    });
    setSession(updated);
    if (!silent) {
      showAlert("Wet reference saved");
    }
  } catch (error) {
    const message = `Wet reference save failed: ${error.message}`;
    if (!silent) {
      showAlert(message, "error");
    }
    throw new Error(message);
  }
}

async function renewCalibration({ silent = false } = {}) {
  try {
    await apiJson("/api/controller/calibration/start", {
      method: "POST",
      body: JSON.stringify({
        duration_s: CALIBRATION_DURATION_S,
        interval_ms: CALIBRATION_INTERVAL_MS,
      }),
    });
    if (!silent) {
      showAlert("Calibration mode enabled");
    }
    await refreshLive();
  } catch (error) {
    const message = `Calibration mode request failed: ${error.message}`;
    if (!silent) {
      showAlert(message, "error");
    }
    throw new Error(message);
  }
}

async function startCapture(probeId) {
  if (state.capture) {
    return;
  }
  clearAlert();
  const session = await ensureSession();
  if (!session || session.status === "completed") {
    return;
  }

  try {
    await saveWetReference({ silent: true });
    await renewCalibration({ silent: true });
    const baseline = state.samples || (await apiJson(`/api/controller/samples?window_s=${LIVE_WINDOW_S}`));
    const request = captureRequest(probeId);
    state.capture = {
      probeId,
      startedAtMs: Date.now(),
      controllerStartMs: baseline?.controller?.read_ms ?? null,
      durationS: CAPTURE_DURATION_S,
    };
    renderCaptureProgress();
    renderProbes();

    const timer = window.setInterval(refreshLive, 1000);
    try {
      state.pendingPreview = await apiJson(
        `/api/sessions/${encodeURIComponent(session.id)}/captures/preview`,
        {
          method: "POST",
          body: JSON.stringify(request),
        },
      );
      openPreviewDialog();
    } finally {
      window.clearInterval(timer);
      state.capture = null;
      renderCaptureProgress();
      renderProbes();
    }
  } catch (error) {
    state.capture = null;
    showAlert(highRateErrorMessage(error), "error");
    renderCaptureProgress();
    renderProbes();
  }
}

function captureRequest(probeId) {
  const form = state.probeForms[probeId];
  return {
    probe_id: probeId,
    anchor_type: selectedAnchorType(),
    duration_s: CAPTURE_DURATION_S,
    placement_label: blankToNull(form.placement_label),
    note: blankToNull(form.note),
    input_ec_ms_cm_override: optionalNumber(form.input_ec_ms_cm_override),
    input_ph_override: optionalNumber(form.input_ph_override),
    poll_interval_s: CAPTURE_POLL_INTERVAL_S,
  };
}

async function acceptPreview() {
  if (!state.pendingPreview || !state.session) {
    return;
  }
  try {
    const updated = await apiJson(
      `/api/sessions/${encodeURIComponent(state.session.id)}/captures/accept`,
      {
        method: "POST",
        body: JSON.stringify({ capture: state.pendingPreview }),
      },
    );
    state.pendingPreview = null;
    setSession(updated);
    el.previewDialog.close();
    await refreshSummary();
  } catch (error) {
    showAlert(`Accept failed: ${error.message}`, "error");
  }
}

function rejectPreview() {
  state.pendingPreview = null;
  el.previewDialog.close();
}

async function completeSession() {
  const session = await ensureSession();
  if (!session || session.status === "completed") {
    return;
  }
  try {
    const completed = await apiJson(`/api/sessions/${encodeURIComponent(session.id)}/complete`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    setSession(completed);
    await refreshSummary();
    showAlert("Session completed");
  } catch (error) {
    showAlert(`Complete failed: ${error.message}`, "error");
  }
}

async function refreshSummary() {
  if (!state.session) {
    renderSummary();
    return;
  }
  try {
    const response = await apiJson(`/api/sessions/${encodeURIComponent(state.session.id)}/summary`);
    state.summary = response.summary;
  } catch (error) {
    state.summary = state.session.summary;
    showAlert(`Summary refresh failed: ${error.message}`, "error");
  }
  renderSummary();
}

function renderStatus() {
  const status = state.liveStatus?.status;
  const samples = state.samples;
  const statusController = status?.controller;
  const samplesController = samples?.controller;
  const mode = samplesController?.calibration_mode || status?.calibration_mode;

  el.connectionState.textContent = state.liveStatusError
    ? `status failed: ${state.liveStatusError.message}`
    : statusController
      ? `${statusController.device_id} connected`
      : "loading";
  el.connectionState.className = state.liveStatusError ? "danger" : "ok";

  el.firmwareVersion.textContent =
    samplesController?.firmware_version || status?.firmware_version || "unknown";

  if (state.samplesError) {
    el.samplesState.textContent = "high-rate /samples unavailable";
    el.samplesState.className = "danger";
    showAlert(
      `High-rate firmware required or controller connection failed: ${state.samplesError.message}`,
      "error",
    );
  } else if (samples) {
    el.samplesState.textContent = `${sampleCount(samples)} samples in ${samples.controller.window_s}s`;
    el.samplesState.className = "ok";
  } else {
    el.samplesState.textContent = "loading";
    el.samplesState.className = "";
  }

  if (mode) {
    el.calibrationState.textContent = mode.active ? "active" : "inactive";
    el.calibrationState.className = mode.active ? "ok" : "muted";
    el.calibrationInterval.textContent = mode.interval_ms
      ? `${mode.interval_ms} ms`
      : "unknown";
    el.calibrationRemaining.textContent = formatDurationMs(mode.remaining_ms);
  } else {
    el.calibrationState.textContent = "unknown";
    el.calibrationInterval.textContent = "unknown";
    el.calibrationRemaining.textContent = "unknown";
  }
}

function renderProbes() {
  el.probeGrid.innerHTML = PROBE_IDS.map((probeId) => probeCardHtml(probeId)).join("");
  for (const probeId of PROBE_IDS) {
    drawTrace(probeId);
  }
}

function probeGridInputFocused() {
  const active = document.activeElement;
  return active instanceof HTMLInputElement && el.probeGrid.contains(active);
}

function probeCardHtml(probeId) {
  const statusSlot = statusSlotForProbe(probeId);
  const sampleSlot = sampleSlotForProbe(probeId);
  const latest = latestSample(sampleSlot);
  const snapshot = latest || statusLatestSample(statusSlot);
  const stats = statsForSamples(samplesForProbe(probeId));
  const identity = sampleSlot || statusSlot || {};
  const form = state.probeForms[probeId];
  const sourceLabel = latest ? "samples" : statusSlot?.latest_sample ? "status" : "none";
  const captureUnavailable =
    state.capture ||
    !state.session ||
    state.session.status === "completed" ||
    state.samplesError ||
    !state.samples;
  const disabled = captureUnavailable ? "disabled" : "";
  const active = state.capture?.probeId === probeId ? "Capturing" : "Start Capture";
  const rawFrame = latest?.raw_modbus_frame_hex || statusSlot?.latest_raw_modbus_frame_hex || "";

  return `
    <article class="probe-card">
      <div class="probe-title">
        <div class="probe-heading">
          <strong>Probe ${probeId}</strong>
          <span class="chip">${escapeHtml(identity.modbus_address || "0x??")}</span>
          <span class="chip">${escapeHtml(identity.device_id || "not present")}</span>
        </div>
        <span class="chip">${escapeHtml(sourceLabel)}</span>
      </div>

      <div class="metrics">
        ${metricHtml("Moisture", formatNumber(snapshot?.soil_moisture_pct, 2), "%")}
        ${metricHtml("EC", formatNumber(snapshot?.substrate_ec_us_cm, 0), "us/cm")}
        ${metricHtml("pH", formatNumber(snapshot?.substrate_ph, 2), "")}
        ${metricHtml("Temp", formatNumber(snapshot?.substrate_temp_c, 1), "deg C")}
      </div>

      <div class="kv-row">
        <span class="label">Sample age</span>
        <span class="value">${escapeHtml(sampleAgeLabel(latest, statusSlot))}</span>
      </div>
      <div class="trace-wrap">
        <canvas data-trace="${probeId}" width="420" height="108"></canvas>
        <span class="trace-empty" data-trace-empty="${probeId}">no high-rate samples</span>
      </div>
      <div class="noise-row">
        <div><span class="label">Count</span><span class="value">${stats.count}</span></div>
        <div><span class="label">Stddev</span><span class="value">${formatNumber(stats.stddev, 3)}</span></div>
        <div><span class="label">Min / max</span><span class="value">${formatNumber(stats.min, 2)} / ${formatNumber(stats.max, 2)}</span></div>
      </div>

      <details>
        <summary>Raw frame and capture fields</summary>
        <code class="raw-frame">${escapeHtml(rawFrame || "none")}</code>
        <div class="advanced-grid">
          <label>
            Placement
            <input data-probe="${probeId}" data-field="placement_label" value="${escapeAttr(form.placement_label)}" />
          </label>
          <label>
            Note
            <input data-probe="${probeId}" data-field="note" value="${escapeAttr(form.note)}" />
          </label>
          <label>
            Override EC ms/cm
            <input data-probe="${probeId}" data-field="input_ec_ms_cm_override" type="number" min="0" step="0.01" inputmode="decimal" value="${escapeAttr(form.input_ec_ms_cm_override)}" />
          </label>
          <label>
            Override pH
            <input data-probe="${probeId}" data-field="input_ph_override" type="number" min="0" max="14" step="0.01" inputmode="decimal" value="${escapeAttr(form.input_ph_override)}" />
          </label>
        </div>
      </details>

      <button type="button" data-start-capture="${probeId}" ${disabled}>${active}</button>
    </article>
  `;
}

function metricHtml(label, value, unit) {
  const suffix = unit ? ` ${unit}` : "";
  return `
    <div class="metric">
      <span class="label">${label}</span>
      <span class="value">${escapeHtml(value)}${suffix}</span>
    </div>
  `;
}

function drawTrace(probeId) {
  const canvas = document.querySelector(`[data-trace="${probeId}"]`);
  const empty = document.querySelector(`[data-trace-empty="${probeId}"]`);
  if (!canvas) {
    return;
  }
  const samples = samplesForProbe(probeId).filter(
    (sample) => sample.valid && typeof sample.soil_moisture_pct === "number",
  );
  empty.hidden = samples.length > 0;
  const context = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#fbfcfb";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "#d9e0db";
  context.lineWidth = 1;
  for (const y of [27, 54, 81]) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }
  if (samples.length < 2) {
    return;
  }

  const values = samples.map((sample) => sample.soil_moisture_pct);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const reads = samples.map((sample) => sample.read_ms);
  const firstRead = Math.min(...reads);
  const readSpan = Math.max(Math.max(...reads) - firstRead, 1);

  context.fillStyle = getComputedStyle(document.documentElement)
    .getPropertyValue("--trace-fill")
    .trim();
  context.strokeStyle = getComputedStyle(document.documentElement)
    .getPropertyValue("--trace")
    .trim();
  context.lineWidth = 2;
  context.beginPath();
  samples.forEach((sample, index) => {
    const x = ((sample.read_ms - firstRead) / readSpan) * (width - 18) + 9;
    const y =
      height - 10 - ((sample.soil_moisture_pct - min) / span) * (height - 20);
    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  });
  context.stroke();
}

function renderCaptureProgress() {
  if (!state.capture) {
    el.captureProgress.hidden = true;
    el.captureProgress.textContent = "";
    return;
  }
  const elapsedS = Math.min(
    (Date.now() - state.capture.startedAtMs) / 1000,
    state.capture.durationS,
  );
  const percent = Math.round((elapsedS / state.capture.durationS) * 100);
  const samples = captureSamples();
  const stats = statsForSamples(samples);
  el.captureProgress.hidden = false;
  el.captureProgress.innerHTML = `
    Probe ${state.capture.probeId} capture: ${Math.round(elapsedS)}s / ${state.capture.durationS}s (${percent}%)
    <br />Samples: ${stats.count}; moisture mean ${formatNumber(stats.mean, 2)}; stddev ${formatNumber(stats.stddev, 3)}
  `;
}

function captureSamples() {
  if (!state.capture) {
    return [];
  }
  return samplesForProbe(state.capture.probeId).filter((sample) => {
    if (state.capture.controllerStartMs === null) {
      return true;
    }
    return sample.read_ms >= state.capture.controllerStartMs;
  });
}

function openPreviewDialog() {
  if (!state.pendingPreview) {
    return;
  }
  const preview = state.pendingPreview;
  const stats = preview.stats;
  el.previewContent.innerHTML = `
    <p class="muted">Probe ${preview.probe_id} ${escapeHtml(preview.anchor_type)} capture, ${preview.samples.length} samples</p>
    <div class="preview-stats">
      ${previewStatHtml("Moisture", stats.soil_moisture_pct, "%", 2)}
      ${previewStatHtml("EC", stats.substrate_ec_us_cm, "us/cm", 0)}
      ${previewStatHtml("pH", stats.substrate_ph, "", 2)}
      ${previewStatHtml("Temp", stats.substrate_temp_c, "deg C", 1)}
    </div>
  `;
  el.previewDialog.showModal();
}

function previewStatHtml(label, stats, unit, digits) {
  const suffix = unit ? ` ${unit}` : "";
  return `
    <div>
      <strong>${label}</strong>
      <p>mean ${formatNumber(stats.mean, digits)}${suffix}</p>
      <p>min ${formatNumber(stats.min, digits)} / max ${formatNumber(stats.max, digits)}</p>
      <p>stddev ${formatNumber(stats.stddev, 3)}</p>
    </div>
  `;
}

function renderSummary() {
  const session = state.session;
  const summary = state.summary || session?.summary;
  if (!session) {
    el.acceptedCaptures.textContent = "No active session";
    el.summaryTable.textContent = "";
    el.markdownSummary.value = "";
    el.csvSummary.value = "";
    el.completeSession.disabled = true;
    return;
  }

  const capturesByProbe = Object.fromEntries(PROBE_IDS.map((probeId) => [probeId, []]));
  for (const capture of session.accepted_captures || []) {
    capturesByProbe[capture.probe_id] ||= [];
    capturesByProbe[capture.probe_id].push(capture);
  }
  el.acceptedCaptures.innerHTML = PROBE_IDS.map((probeId) =>
    captureListHtml(probeId, capturesByProbe[probeId] || []),
  ).join("");

  if (!summary) {
    el.summaryTable.textContent = "Summary unavailable";
    el.markdownSummary.value = "";
    el.csvSummary.value = "";
    return;
  }

  el.summaryTable.innerHTML = summaryTableHtml(summary);
  el.markdownSummary.value = markdownSummary(summary);
  el.csvSummary.value = csvSummary(summary);
  el.completeSession.disabled = session.status === "completed";
}

function captureListHtml(probeId, captures) {
  const items = captures.length
    ? captures
        .map(
          (capture) => `
            <li>
              ${escapeHtml(capture.anchor_type)}:
              ${formatNumber(capture.stats.soil_moisture_pct.mean, 2)}%
              (${capture.stats.valid_sample_count} samples)
            </li>
          `,
        )
        .join("")
    : "<li>none</li>";
  return `
    <section class="capture-list">
      <h3>Probe ${probeId}</h3>
      <ul>${items}</ul>
    </section>
  `;
}

function summaryTableHtml(summary) {
  const rows = summary.probes
    .map(
      (item) => `
        <tr>
          <td>Probe ${item.probe.probe_id}</td>
          <td>${escapeHtml(item.probe.modbus_address)}</td>
          <td>${formatNumber(item.dry_anchor_mean, 3)}</td>
          <td>${formatNumber(item.wet_anchor_mean, 3)}</td>
          <td>${formatNumber(item.span, 3)}</td>
          <td>${escapeHtml(item.formula || "not ready")}</td>
          <td>${escapeHtml(item.warnings.join("; ") || "none")}</td>
        </tr>
      `,
    )
    .join("");
  return `
    <table>
      <thead>
        <tr>
          <th>Probe</th>
          <th>Address</th>
          <th>Dry mean</th>
          <th>Wet mean</th>
          <th>Span</th>
          <th>Formula</th>
          <th>Warnings</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function markdownSummary(summary) {
  const lines = [
    "| Probe | Address | Dry mean | Wet mean | Span | Formula | Warnings |",
    "|---|---:|---:|---:|---:|---|---|",
  ];
  for (const item of summary.probes) {
    lines.push(
      [
        `Probe ${item.probe.probe_id}`,
        item.probe.modbus_address,
        formatNumber(item.dry_anchor_mean, 3),
        formatNumber(item.wet_anchor_mean, 3),
        formatNumber(item.span, 3),
        item.formula || "not ready",
        item.warnings.join("; ") || "none",
      ].join(" | "),
    );
  }
  return `${lines.join("\n")}\n`;
}

function csvSummary(summary) {
  const rows = [
    ["probe", "address", "dry_mean", "wet_mean", "span", "formula", "warnings"],
    ...summary.probes.map((item) => [
      `Probe ${item.probe.probe_id}`,
      item.probe.modbus_address,
      formatNumber(item.dry_anchor_mean, 3),
      formatNumber(item.wet_anchor_mean, 3),
      formatNumber(item.span, 3),
      item.formula || "not ready",
      item.warnings.join("; ") || "none",
    ]),
  ];
  return `${rows.map((row) => row.map(csvCell).join(",")).join("\n")}\n`;
}

function sampleSlotForProbe(probeId) {
  return state.samples?.slots?.find((slot) => slot.probe_id === probeId) || null;
}

function statusSlotForProbe(probeId) {
  return state.liveStatus?.status?.slots?.find((slot) => slot.probe_id === probeId) || null;
}

function latestSample(slot) {
  if (!slot?.samples?.length) {
    return null;
  }
  return [...slot.samples].sort((left, right) => {
    if (left.read_ms !== right.read_ms) {
      return left.read_ms - right.read_ms;
    }
    return left.seq - right.seq;
  }).at(-1);
}

function statusLatestSample(slot) {
  if (!slot?.latest_sample) {
    return null;
  }
  return slot.latest_sample;
}

function samplesForProbe(probeId) {
  return sampleSlotForProbe(probeId)?.samples || [];
}

function statsForSamples(samples) {
  const values = samples
    .filter((sample) => sample.valid && typeof sample.soil_moisture_pct === "number")
    .map((sample) => sample.soil_moisture_pct);
  if (!values.length) {
    return { count: 0, mean: null, min: null, max: null, stddev: null };
  }
  const mean = values.reduce((total, value) => total + value, 0) / values.length;
  const variance =
    values.reduce((total, value) => total + (value - mean) ** 2, 0) / values.length;
  return {
    count: values.length,
    mean,
    min: Math.min(...values),
    max: Math.max(...values),
    stddev: Math.sqrt(variance),
  };
}

function sampleCount(samplesResponse) {
  return (samplesResponse?.slots || []).reduce(
    (count, slot) => count + (slot.samples?.length || 0),
    0,
  );
}

function selectedAnchorType() {
  return document.querySelector('input[name="anchor-type"]:checked').value;
}

function referencePayload() {
  return {
    input_ec_ms_cm: optionalNumber(el.inputEc.value),
    input_ph: optionalNumber(el.inputPh.value),
  };
}

function optionalNumber(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function blankToNull(value) {
  const trimmed = String(value || "").trim();
  return trimmed ? trimmed : null;
}

function valueForInput(value) {
  return value === null || value === undefined ? "" : String(value);
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  return Number(value).toFixed(digits);
}

function formatDurationMs(value) {
  if (typeof value !== "number") {
    return "unknown";
  }
  if (value <= 0) {
    return "0s";
  }
  const seconds = Math.round(value / 1000);
  if (seconds < 90) {
    return `${seconds}s`;
  }
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function sampleAgeLabel(latest, statusSlot) {
  if (latest && state.samples?.controller?.read_ms !== undefined) {
    return formatDurationMs(Math.max(0, state.samples.controller.read_ms - latest.read_ms));
  }
  if (statusSlot?.latest_sample?.age_ms !== undefined) {
    return `${formatDurationMs(statusSlot.latest_sample.age_ms)} status`;
  }
  return "unknown";
}

function showAlert(message, tone = "info") {
  el.alert.textContent = message;
  el.alert.className = tone === "error" ? "alert error" : "alert";
  el.alert.hidden = false;
}

function clearAlert() {
  el.alert.hidden = true;
  el.alert.textContent = "";
}

function highRateErrorMessage(error) {
  const message = error?.message || String(error);
  if (message.includes("/samples") || message.includes("404") || message.includes("502")) {
    return `High-rate firmware required or controller connection failed: ${message}`;
  }
  return message;
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    showAlert(message);
  } catch (error) {
    showAlert(`Copy failed: ${error.message}`, "error");
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value || "");
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}
