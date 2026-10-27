/* Frozen player: renders one analysis + page-data, no framework. */

"use strict";

function getData(id) {
  const el = document.getElementById(id);
  return JSON.parse(el ? el.textContent : "{}");
}

/* Pure logic: also exercised by the node test, keep DOM-free. */

function parseQuery(qs, nSteps) {
  const out = { step: null, frame: null };
  const query = String(qs).replace(/^\?/, "");
  const params = new Map();
  for (const part of query.split("&")) {
    if (!part) continue;
    const eq = part.indexOf("=");
    const key = decodeURIComponent(eq < 0 ? part : part.slice(0, eq));
    const val = eq < 0 ? "" : decodeURIComponent(part.slice(eq + 1));
    if (!params.has(key)) params.set(key, val);
  }
  if (params.has("step")) {
    const raw = Number(params.get("step"));
    if (Number.isInteger(raw) && nSteps > 0) {
      out.step = Math.max(0, Math.min(nSteps - 1, raw));
    }
  }
  if (params.has("frame")) {
    const raw = Number(params.get("frame"));
    if (Number.isInteger(raw) && raw >= 0) out.frame = raw;
  }
  return out;
}

function collectNotices(page) {
  /* One-line fallbacks per step when a run lacks what the step needs. */
  const notes = {};
  if (!page.has_timescale) notes.clock = "notice.no_timescale";
  (page.flights || []).forEach((flight, i) => {
    if (flight.chart && flight.chart.notice) {
      notes["motion-" + i + "-chart"] = flight.chart.notice;
    }
    if (flight.ghost_missing) notes["motion-" + i + "-ghost"] = "notice.no_ghost";
    if (flight.overlay && flight.overlay.notice) {
      notes["motion-" + i + "-overlay"] = flight.overlay.notice;
    }
  });
  return notes;
}

/* Rendering (browser only below this line). */

let ANALYSIS = {};
let PAGE = {};
let TEXTS = {};
let VIDEO = null;
let CANVAS = null;
let CTX = null;
let CURRENT_STEP = 0;
let PREV_FRAME = -1;

function t(key) {
  return Object.prototype.hasOwnProperty.call(TEXTS, key) ? TEXTS[key] : key;
}

function esc(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fps() {
  return ANALYSIS.clip.fps;
}

function frameNow() {
  if (!VIDEO || !VIDEO.duration) return 0;
  return Math.round(VIDEO.currentTime * fps());
}

function seekFrame(frame) {
  const n = ANALYSIS.clip.frames;
  const clamped = Math.max(0, Math.min(n - 1, frame));
  PREV_FRAME = clamped;
  VIDEO.currentTime = clamped / fps();
  draw();
  updateReadout();
}

function updateReadout() {
  const el = document.getElementById("frame-readout");
  const f = frameNow();
  el.textContent = "f" + f + " / " + ANALYSIS.clip.frames
    + " · " + (f / fps()).toFixed(2) + "s";
}

function goStep(i, seek) {
  CURRENT_STEP = Math.max(0, Math.min(PAGE.steps.length - 1, i));
  const step = PAGE.steps[CURRENT_STEP];
  document.querySelectorAll("#steps-list button").forEach((btn, j) => {
    if (j === CURRENT_STEP) btn.setAttribute("aria-current", "true");
    else btn.removeAttribute("aria-current");
  });
  const target = document.getElementById("step-" + step.id);
  if (target) target.scrollIntoView({ block: "start", behavior: "smooth" });
  if (seek !== false && Number.isInteger(step.frame)) seekFrame(step.frame);
  const url = "?step=" + CURRENT_STEP + "&frame=" + frameNow();
  history.replaceState(null, "", url);
}

function motionEvents(i) {
  const flight = PAGE.flights[i];
  const events = [{ key: "motion.takeoff", frame: flight.start }];
  if (Number.isInteger(flight.apex)) {
    events.push({ key: "motion.apex", frame: flight.apex });
  }
  events.push({ key: "motion.end", frame: flight.end });
  return events;
}

function draw() {
  if (!CTX || !VIDEO.videoWidth) return;
  const vw = VIDEO.videoWidth;
  const vh = VIDEO.videoHeight;
  if (CANVAS.width !== vw || CANVAS.height !== vh) {
    CANVAS.width = vw;
    CANVAS.height = vh;
  }
  CTX.clearRect(0, 0, vw, vh);
  const frame = frameNow();
  drawMasks(frame, vw, vh);
  const step = PAGE.steps[CURRENT_STEP];
  if (step && step.id === "scale") drawScaleBar(vw, vh);
  if (step && step.id.indexOf("motion-") === 0) {
    const i = Number(step.id.slice("motion-".length));
    drawFlight(i, frame, vw, vh);
  }
}

function scaleXY(vw, vh) {
  return { x: vw / ANALYSIS.clip.width, y: vh / ANALYSIS.clip.height };
}

function drawMasks(frame, vw, vh) {
  const s = scaleXY(vw, vh);
  const masks = ANALYSIS.masks || {};
  CTX.lineWidth = Math.max(1, vw / 400);
  CTX.strokeStyle = "#22d3ee";
  CTX.fillStyle = "rgba(34, 211, 238, 0.18)";
  for (const obj of Object.keys(masks)) {
    const runs = masks[obj][String(frame)];
    if (!runs) continue;
    CTX.beginPath();
    for (const run of runs) {
      const y = run[0] * s.y;
      const h = Math.max(1, s.y);
      CTX.rect(run[1] * s.x, y, (run[2] - run[1]) * s.x, h);
    }
    CTX.fill();
    CTX.stroke();
  }
}

function drawScaleBar(vw, vh) {
  const scale = ANALYSIS.scale || {};
  if (!Number.isFinite(scale.extent_px)) return;
  const s = scaleXY(vw, vh);
  const ref = (ANALYSIS.reference || [])[0];
  const label = ref ? ref.value_m + " m" : "";
  const y = vh - 24;
  const x0 = 24;
  const len = scale.extent_px * s.x;
  CTX.strokeStyle = "#fbbf24";
  CTX.lineWidth = Math.max(2, vw / 300);
  CTX.beginPath();
  CTX.moveTo(x0, y);
  CTX.lineTo(x0 + len, y);
  CTX.moveTo(x0, y - 6);
  CTX.lineTo(x0, y + 6);
  CTX.moveTo(x0 + len, y - 6);
  CTX.lineTo(x0 + len, y + 6);
  CTX.stroke();
  CTX.fillStyle = "#fbbf24";
  CTX.font = `${Math.round(Math.max(12, vw / 40))}px sans-serif`;
  CTX.fillText(label, x0, y - 10);
}

function drawFlight(i, frame, vw, vh) {
  const flight = PAGE.flights[i];
  if (!flight || !flight.overlay || flight.overlay.notice) return;
  const s = scaleXY(vw, vh);
  const overlay = flight.overlay;
  const frames = overlay.frames || [];
  const upto = frames.filter((f) => f <= frame);
  const pos = (k) => {
    const p = overlay.track[k];
    return [p[0] * s.x, p[1] * s.y];
  };
  const line = (pts, color, width, dash) => {
    if (!pts || pts.length < 2) return;
    CTX.strokeStyle = color;
    CTX.lineWidth = width;
    CTX.setLineDash(dash || []);
    CTX.beginPath();
    pts.forEach((p, k) => {
      const q = [p[0] * s.x, p[1] * s.y];
      if (k === 0) CTX.moveTo(q[0], q[1]);
      else CTX.lineTo(q[0], q[1]);
    });
    CTX.stroke();
    CTX.setLineDash([]);
  };
  line(overlay.fit, "rgba(37, 99, 235, 0.9)", Math.max(1.5, vw / 350), []);
  line(overlay.ghost, "rgba(244, 114, 182, 0.8)", Math.max(1, vw / 450), [6, 4]);
  if (upto.length > 1) {
    line(upto.map((f) => overlay.track[frames.indexOf(f)]), "#22c55e",
      Math.max(1.5, vw / 350), []);
  }
  const here = frames.indexOf(frame);
  const idx = here >= 0 ? here : upto.length - 1;
  if (idx >= 0) {
    const p = pos(idx);
    CTX.fillStyle = "#22c55e";
    CTX.beginPath();
    CTX.arc(p[0], p[1], Math.max(3, vw / 160), 0, 2 * Math.PI);
    CTX.fill();
  }
}

function chartSVG(chart) {
  const finite = (arr) => arr.filter((v) => Number.isFinite(v));
  const all = finite(chart.h.concat(chart.h_fit, chart.h_ghost));
  if (!all.length) return "";
  let lo = Math.min.apply(null, all);
  let hi = Math.max.apply(null, all);
  if (hi - lo < 1e-9) { lo -= 0.05; hi += 0.05; }
  const pad = (hi - lo) * 0.12;
  lo -= pad;
  hi += pad;
  const W = 560;
  const H = 300;
  const L = 56;
  const B = 34;
  const T = 10;
  const tMax = Math.max.apply(null, chart.t);
  const X = (time) => L + (time / (tMax || 1)) * (W - L - 12);
  const Y = (h) => T + (1 - (h - lo) / (hi - lo)) * (H - T - B);
  const dots = chart.t.map((time, k) => {
    if (!Number.isFinite(chart.h[k])) return "";
    return `<circle cx="${X(time).toFixed(1)}" cy="${Y(chart.h[k]).toFixed(1)}" r="3.2" fill="#22c55e"/>`;
  }).join("");
  const pathOf = (arr) => {
    let d = "";
    chart.t.forEach((time, k) => {
      if (!Number.isFinite(arr[k])) return;
      d += (d ? "L" : "M") + X(time).toFixed(1) + " " + Y(arr[k]).toFixed(1);
    });
    return d;
  };
  const fitPath = pathOf(chart.h_fit);
  const ghostPath = pathOf(chart.h_ghost);
  const ghostLegend = ghostPath
    ? `<text x="${L + 190}" y="${H - 14}" font-size="11" fill="#f472b6}">- - ${esc(t("motion.ghost"))}</text>`
    : `<text x="${L + 190}" y="${H - 14}" font-size="11" fill="#888">${esc(t("motion.legend_noghost"))}</text>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img">`
    + `<line x1="${L}" y1="${T}" x2="${L}" y2="${H - B}" stroke="#888"/>`
    + `<line x1="${L}" y1="${H - B}" x2="${W - 6}" y2="${H - B}" stroke="#888"/>`
    + `<text x="6" y="${T + 8}" font-size="11" fill="#888">${esc(t("motion.height_axis"))}</text>`
    + `<text x="${W - 52}" y="${H - 8}" font-size="11" fill="#888">${esc(t("motion.time_axis"))}</text>`
    + (ghostPath ? `<path d="${ghostPath}" fill="none" stroke="#f472b6" stroke-width="2" stroke-dasharray="6 4"/>` : "")
    + `<path d="${fitPath}" fill="none" stroke="#2563eb" stroke-width="2"/>`
    + dots
    + `<circle cx="${L + 8}" cy="${H - 18}" r="3.2" fill="#22c55e"/>`
    + `<text x="${L + 16}" y="${H - 14}" font-size="11">${esc(t("motion.measured"))}</text>`
    + `<text x="${L + 110}" y="${H - 14}" font-size="11" fill="#2563eb">— ${esc(t("motion.fit"))}</text>`
    + ghostLegend
    + `</svg>`;
}

function verdictSVG() {
  const verdict = ANALYSIS.verdict || {};
  const worlds = verdict.worlds || {};
  const names = Object.keys(worlds);
  const g = Number(verdict.g);
  const err = Number(verdict.g_err || 0);
  const top = Math.max.apply(null, [g + 2 * err].concat(names.map((n) => worlds[n]))) * 1.12;
  const W = 560;
  const H = 120;
  const L = 56;
  const X = (v) => L + (v / (top || 1)) * (W - L - 12);
  let inner = `<line x1="${L}" y1="60" x2="${W - 6}" y2="60" stroke="#888"/>`;
  names.forEach((name) => {
    const x = X(worlds[name]).toFixed(1);
    inner += `<line x1="${x}" y1="44" x2="${x}" y2="76" stroke="#888" stroke-width="2"/>`
      + `<text x="${x}" y="94" font-size="11" text-anchor="middle">${esc(name)} ${worlds[name]}</text>`;
  });
  inner += `<line x1="${X(g - err).toFixed(1)}" y1="60" x2="${X(g + err).toFixed(1)}" y2="60" stroke="#111" stroke-width="5"/>`
    + `<circle cx="${X(g).toFixed(1)}" cy="60" r="6" fill="#111"/>`
    + `<text x="${X(g).toFixed(1)}" y="30" font-size="11" text-anchor="middle">${esc(t("verdict.measured"))} ${g.toFixed(2)} ± ${err.toFixed(2)}</text>`
    + `<text x="${W - 6}" y="112" font-size="11" text-anchor="end" fill="#888">${esc(t("verdict.axis_note"))}</text>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img">${inner}</svg>`;
}

function ledeKey(id) {
  if (id === "first-look") return "steps.firstlook.body";
  return "steps." + id.split("-")[0] + ".body";
}

function renderStep(step) {
  const notes = collectNotices(PAGE);
  const id = step.id;
  let body = "";
  if (id === "first-look") body = renderFirstLook();
  else if (id === "reference") body = renderReference();
  else if (id === "scale") body = renderScale();
  else if (id.indexOf("motion-") === 0) {
    body = renderMotion(Number(id.slice("motion-".length)), notes);
  } else if (id === "clock") body = renderClock(notes.clock);
  else if (id === "errors") body = renderErrors();
  else if (id === "verdict") body = renderVerdict();
  else if (id === "howmade") body = renderHowMade();
  return `<section class="step" id="step-${esc(id)}"><h2>${esc(step.title)}</h2>`
    + `<p class="lede">${esc(t(ledeKey(id)))}</p>${body}</section>`;
}

function renderFirstLook() {
  const fl = ANALYSIS.first_look || {};
  const eye = fl.by_eye || {};
  const clip = ANALYSIS.clip || {};
  return `<dl class="facts">`
    + `<dt>claim</dt><dd>${esc(fl.what || "")}</dd>`
    + `<dt>where</dt><dd>${esc(fl.where || "")}</dd>`
    + `<dt>when</dt><dd>${esc(fl.when || "")}</dd>`
    + `<dt>by eye</dt><dd class="num">${esc(String(eye.value ?? ""))} ${esc(eye.unit || "")} (${esc(eye.quantity || "")})</dd>`
    + `<dt>fps</dt><dd class="num">${esc(String(clip.fps ?? ""))} · ${esc(String(clip.frames ?? ""))} frames · ${esc(String(clip.duplicates_found ?? ""))} duplicates</dd>`
    + `<dt>notes</dt><dd>${esc(clip.notes || "")}</dd>`
    + `</dl>`;
}

function renderReference() {
  const refs = ANALYSIS.reference || [];
  return refs.map((ref, i) => {
    const sheet = (PAGE.sheets || [])[i];
    const img = sheet && sheet.sheet
      ? `<img src="${esc(sheet.sheet)}" alt="${esc(t("steps.reference.sheet"))}" loading="lazy">`
      : `<p class="notice">${esc(t("notice.no_sheet"))}</p>`;
    const mc = ref.mask_check || {};
    return `<div class="ref-card"><h3>${esc(ref.name || "")}</h3>`
      + `<dl class="facts">`
      + `<dt>extent</dt><dd>${esc(ref.extent || "")}</dd>`
      + `<dt>size</dt><dd class="num">${esc(String(ref.value_m ?? ""))} ± ${esc(String(ref.tolerance_m ?? ""))} m</dd>`
      + `<dt>source</dt><dd><a href="${esc(ref.source_url || "")}">${esc(ref.source_url || "")}</a> (${esc(ref.source_type || "")})</dd>`
      + `</dl><blockquote>${esc(ref.quote || "")}</blockquote>`
      + `<p><strong>${esc(t("steps.reference.mask_check"))}:</strong> ${esc(mc.verdict || "")} — ${esc(mc.covers || "")}</p>`
      + img + `</div>`;
  }).join("");
}

function renderScale() {
  const scale = ANALYSIS.scale || {};
  const ref = (ANALYSIS.reference || [])[0] || {};
  const mPer = scale.m_per_px !== undefined ? scale.m_per_px : scale.m_per_ref;
  const mPerErr = scale.m_per_px_err !== undefined ? scale.m_per_px_err : scale.m_per_ref_err;
  const second = scale.second || {};
  return `<dl class="facts">`
    + `<dt>frame</dt><dd class="num">${esc(String(scale.frame ?? ""))}</dd>`
    + `<dt>extent</dt><dd class="num">${esc(String(scale.extent_px ?? ""))} ± ${esc(String(scale.extent_px_err ?? ""))} px ↔ ${esc(String(ref.value_m ?? ""))} m</dd>`
    + `<dt>scale</dt><dd class="num">${esc(String(mPer ?? ""))} ± ${esc(String(mPerErr ?? ""))} m/unit</dd>`
    + `</dl>`
    + `<p><strong>${esc(t("steps.scale.second"))}:</strong> ${esc(second.name || "")} `
    + `<span class="num">${esc(String(second.m_per_px ?? ""))} ± ${esc(String(second.m_per_px_err ?? ""))}</span> `
    + `(${esc(t("steps.scale.agree"))} <span class="num">${esc(String(second.agree_sigma ?? ""))}σ</span>)</p>`;
}

function renderMotion(i, notes) {
  const flight = PAGE.flights[i];
  const events = motionEvents(i).map((ev) => {
    const label = ev.frame === flight.start ? t("motion.takeoff")
      : ev.frame === flight.end ? t("motion.end") : t(ev.key);
    return `<button type="button" data-seek="${ev.frame}">${esc(label)} f${ev.frame}</button>`;
  }).join("");
  const chartNote = notes["motion-" + i + "-chart"];
  const overlayNote = notes["motion-" + i + "-overlay"];
  const ghostNote = notes["motion-" + i + "-ghost"];
  const chart = chartNote
    ? `<p class="notice">${esc(t(chartNote))}</p>`
    : chartSVG(flight.chart);
  const overlay = overlayNote ? `<p class="notice">${esc(t(overlayNote))}</p>` : "";
  const ghost = ghostNote && !chartNote ? `<p class="notice">${esc(t(ghostNote))}</p>` : "";
  const hypo = flight.hypothesis || {};
  return `<div class="event-row">${events}</div>`
    + overlay + chart + ghost
    + `<dl class="facts">`
    + `<dt>hypothesis</dt><dd>${esc(hypo.name || "")} <span class="num">${esc(String(hypo.value ?? ""))} m/s²</span></dd>`
    + `<dt>rise</dt><dd class="num">${esc(String(flight.rise_m ?? ""))} m in ${esc(String(flight.duration_s ?? ""))} s</dd>`
    + `<dt>g</dt><dd class="num">${esc(String(flight.accel ?? ""))} ± ${esc(String(flight.accel_err ?? ""))} m/s²</dd>`
    + `</dl><p>${esc(flight.notes || "")}</p>`;
}

function renderClock(clockNotice) {
  const ts = ANALYSIS.timescale;
  const overall = ANALYSIS.overall || {};
  const top = clockNotice ? `<p class="notice">${esc(t(clockNotice))}</p>` : "";
  const table = !ts ? "" : `<dl class="facts">`
    + `<dt>${esc(t("clock.method"))}</dt><dd>${esc(ts.method || "")}</dd>`
    + `<dt>${esc(t("clock.reading"))}</dt><dd class="num">${esc(String(ts.value ?? ""))} ± ${esc(String(ts.err ?? ""))} ${esc(ts.unit || "")} (${esc(ts.verdict || "")})</dd>`
    + `<dt>${esc(t("clock.natural"))}</dt><dd class="num">${esc((ts.expected_range || []).join("–"))} ${esc(ts.unit || "")}</dd>`
    + `</dl>`;
  return top + table
    + `<p><strong>${esc(t("clock.implies"))}:</strong> ${esc(overall.text || "")}</p>`;
}

function renderErrors() {
  const budget = ANALYSIS.error_budget || {};
  const names = Object.keys(budget);
  if (!names.length) return "";
  const max = Math.max.apply(null, names.map((n) => Number(budget[n]) || 0)) || 1;
  const head = `<div class="bar-row"><strong>${esc(t("errors.term"))}</strong>`
    + `<span></span><strong class="num">${esc(t("errors.share"))}</strong></div>`;
  return `<div class="bars">` + head + names.map((n) => {
    const share = (Number(budget[n]) || 0) / max;
    return `<div class="bar-row"><span>${esc(n)}</span>`
      + `<span class="bar-track"><span class="bar-fill" style="display:block;width:${(share * 100).toFixed(1)}%"></span></span>`
      + `<span class="num">${(Number(budget[n]) * 100).toFixed(1)}%</span></div>`;
  }).join("") + `</div>`;
}

function renderVerdict() {
  const overall = ANALYSIS.overall || {};
  const verdict = ANALYSIS.verdict || {};
  let extra = "";
  if (PAGE.ruled_out_line) extra += `<p>${esc(PAGE.ruled_out_line)}</p>`;
  if (PAGE.legacy_line) extra += `<p class="notice">${esc(PAGE.legacy_line)}</p>`;
  return `<p class="notice"><strong>${esc(PAGE.headline)}</strong> `
    + `<span class="num">${esc(PAGE.key_number)}</span></p>`
    + verdictSVG()
    + `<p>${esc(overall.text || "")}</p>`
    + `<p>${esc(verdict.text || "")}</p>`
    + extra;
}

function renderHowMade() {
  const hm = PAGE.howmade || {};
  const rows = [
    [t("howmade.model"), hm.model || ""],
    [t("howmade.turns"), String(hm.turns ?? "")],
    [t("howmade.sam"), `${hm.sam_calls ?? ""} / ${hm.sam_frames ?? ""}`],
    [t("howmade.searches"), String(hm.searches ?? "")],
    [t("howmade.maskchecks"), String(hm.mask_checks ?? "")],
    [t("howmade.cost"), "$" + Number(hm.cost_usd || 0).toFixed(2)],
    [t("howmade.wall"), Math.round(Number(hm.wall_s || 0)) + "s"],
  ].map(([k, v]) => `<dt>${esc(k)}</dt><dd class="num">${esc(v)}</dd>`).join("");
  const log = hm.runlog_href
    ? `<p><a href="${esc(hm.runlog_href)}">${esc(t("steps.howmade.runlog"))}</a>: <span class="mono">${esc(PAGE.run_tag || "")}</span></p>`
    : `<p class="notice">${esc(t("notice.no_summary"))}</p>`;
  return `<dl class="facts">${rows}</dl>` + log;
}

function boot() {
  ANALYSIS = getData("analysis");
  PAGE = getData("page-data");
  TEXTS = PAGE.texts || {};
  VIDEO = document.getElementById("clip");
  CANVAS = document.getElementById("overlay");
  CTX = CANVAS.getContext("2d");
  document.getElementById("kicker").textContent = t("app.kicker");
  document.title = PAGE.headline + " — physics-proof";
  const headline = document.getElementById("headline");
  headline.textContent = PAGE.headline;
  headline.className = PAGE.color || "grey";
  document.getElementById("key-number").textContent =
    t("header.measured") + ": " + PAGE.key_number;
  document.getElementById("btn-play").textContent = t("controls.play");
  document.getElementById("btn-back").textContent = t("controls.step_back");
  document.getElementById("btn-fwd").textContent = t("controls.step_fwd");
  document.getElementById("btn-prev").textContent = t("controls.prev_step");
  document.getElementById("btn-next").textContent = t("controls.next_step");
  document.getElementById("steps-heading").textContent = t("controls.step_label");
  const list = document.getElementById("steps-list");
  PAGE.steps.forEach((step, i) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = step.title;
    btn.addEventListener("click", () => goStep(i));
    li.appendChild(btn);
    list.appendChild(li);
  });
  const wrap = document.getElementById("steps");
  PAGE.steps.forEach((step) => {
    const div = document.createElement("div");
    div.innerHTML = renderStep(step);
    wrap.appendChild(div);
  });
  document.querySelectorAll("[data-seek]").forEach((btn) => {
    btn.addEventListener("click", () => {
      VIDEO.pause();
      document.getElementById("btn-play").textContent = t("controls.play");
      seekFrame(Number(btn.getAttribute("data-seek")));
    });
  });
  document.getElementById("btn-play").addEventListener("click", () => {
    if (VIDEO.paused) {
      VIDEO.play();
      document.getElementById("btn-play").textContent = t("controls.pause");
    } else {
      VIDEO.pause();
      document.getElementById("btn-play").textContent = t("controls.play");
    }
  });
  document.getElementById("btn-back").addEventListener("click", () => {
    VIDEO.pause();
    seekFrame(frameNow() - 1);
  });
  document.getElementById("btn-fwd").addEventListener("click", () => {
    VIDEO.pause();
    seekFrame(frameNow() + 1);
  });
  document.getElementById("btn-prev").addEventListener("click", () => goStep(CURRENT_STEP - 1));
  document.getElementById("btn-next").addEventListener("click", () => goStep(CURRENT_STEP + 1));
  VIDEO.addEventListener("seeked", () => { draw(); updateReadout(); });
  VIDEO.addEventListener("loadedmetadata", () => { draw(); updateReadout(); });
  VIDEO.addEventListener("timeupdate", () => {
    const f = frameNow();
    const step = PAGE.steps[CURRENT_STEP];
    if (step && step.id.indexOf("motion-") === 0 && !VIDEO.paused) {
      const i = Number(step.id.slice("motion-".length));
      const frames = motionEvents(i).map((ev) => ev.frame);
      if (frames.indexOf(f) >= 0 && f !== PREV_FRAME) VIDEO.pause();
    }
    PREV_FRAME = f;
    draw();
    updateReadout();
  });
  const query = parseQuery(window.location.search, PAGE.steps.length);
  const startStep = query.step === null ? 0 : query.step;
  CURRENT_STEP = startStep;
  const initFrame = query.frame === null ? PAGE.steps[startStep].frame : query.frame;
  const go = () => {
    goStep(startStep, false);
    seekFrame(Math.max(0, Math.min(ANALYSIS.clip.frames - 1, initFrame)));
  };
  if (VIDEO.readyState >= 1) go();
  else VIDEO.addEventListener("loadedmetadata", go, { once: true });
  (function loop() {
    if (VIDEO && !VIDEO.paused) { draw(); updateReadout(); }
    requestAnimationFrame(loop);
  })();
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", boot);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseQuery, collectNotices };
}
