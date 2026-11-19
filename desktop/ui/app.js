/* BasicAnalysis Desktop prototype: shows a results.json (resultsjson.py).
 *
 * It runs in any browser (open index.html) and is the front end of the
 * Tauri application (doc/design/desktop_app.rst). All text from the file is
 * inserted with textContent, never as HTML.
 */
'use strict';

const SUPPORTED_SCHEMA_VERSION = 1;

// Efficiency colours of the report (interactiveplots.EFFICIENCY_COLOR_SCALE).
const COLOR_SCALE = [
  [0.00, '#b2182b'], [0.20, '#ef6548'], [0.40, '#fdbb84'], [0.60, '#fee8a8'],
  [0.75, '#ffffbf'], [0.85, '#d9ef8b'], [0.92, '#b8e186'], [1.00, '#4dac26'],
];
// Positions of the default thresholds on the scale (metrics.SCALE_ANCHORS).
const ANCHORS = { critical: 60, attention: 85, reference: 100 };

function el(tag, attrs, text) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === 'class') node.className = value;
    else node.setAttribute(key, value);
  }
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function scalePosition(value, thresholds) {
  const { critical, attention } = thresholds;
  if (value < critical) return value / critical * ANCHORS.critical;
  if (value < attention) {
    return ANCHORS.critical + (value - critical) / (attention - critical)
      * (ANCHORS.attention - ANCHORS.critical);
  }
  return ANCHORS.attention + (value - attention) / (100 - attention)
    * (ANCHORS.reference - ANCHORS.attention);
}

function efficiencyColor(value, thresholds) {
  const t = Math.max(0, Math.min(1, scalePosition(value, thresholds) / 100));
  for (let i = 1; i < COLOR_SCALE.length; i++) {
    const [p1, c1] = COLOR_SCALE[i - 1];
    const [p2, c2] = COLOR_SCALE[i];
    if (t <= p2) {
      const f = (t - p1) / (p2 - p1);
      const a = hexToRgb(c1), b = hexToRgb(c2);
      const mix = a.map((x, k) => Math.round(x + (b[k] - x) * f));
      return `rgb(${mix.join(',')})`;
    }
  }
  return COLOR_SCALE[COLOR_SCALE.length - 1][1];
}

// Tables whose percentages are efficiencies (coloured as in the report);
// the other percentages (flushing, bandwidth, occupancy) are not.
const EFFICIENCY_MODELS = new Set(['application', 'scalability_io', 'hybrid',
  'hybrid_inner_comm', 'host', 'device', 'openmp_runtime']);
const EFFICIENCY_HWC = new Set(['dev_hwc_sm_utilization', 'dev_hwc_sm_coverage',
  'dev_hwc_sm_issue_eff']);

function isEfficiency(model, metric) {
  if (metric.unit !== '%') return false;
  if (EFFICIENCY_MODELS.has(model.id)) return true;
  if (model.id === 'gpu_hardware_counters') return EFFICIENCY_HWC.has(metric.key);
  return model.id === 'general' && metric.key.endsWith('_eff');
}

function formatValue(value, unit) {
  if (typeof value !== 'number') return value === null ? '' : String(value);
  if (unit === '%') return value.toFixed(2);
  if (Math.abs(value) >= 1000) return value.toFixed(0);
  return value.toFixed(2);
}

function renderRun(results) {
  const box = document.getElementById('run');
  box.replaceChildren(el('h2', {}, 'Run'));
  const grid = el('dl', { class: 'run-grid' });
  const run = results.run || {};
  const ba = results.basicanalysis || {};
  const scaling = run.scaling || {};
  const rows = [
    ['Command', run.command],
    ['Date', run.date],
    ['Folder', run.directory],
    ['BasicAnalysis', `${ba.version || ''}${ba.commit ? ' (' + ba.commit + ')' : ''}`],
    ['Model', run.analysis_kind === 'hybrid' ? 'Hybrid / Heterogeneous' : 'Simple'],
    ['Scaling', scaling.selected ? `${scaling.selected} (${scaling.selection_mode || ''})` : ''],
  ];
  for (const [name, value] of rows) {
    if (!value) continue;
    grid.append(el('dt', {}, name), el('dd', {}, value));
  }
  box.append(grid);
}

function renderTraces(results) {
  document.getElementById('configuration-meaning').textContent =
    results.configuration_meaning
      ? `Configuration: ${results.configuration_meaning} [Tn = trace ID]` : '';
  const table = document.getElementById('traces');
  table.replaceChildren();
  const head = el('thead');
  const hr = el('tr');
  for (const name of ['ID', 'Configuration', 'Trace', 'Mode', 'Processes',
                      'MPI ranks', 'Devices']) {
    hr.append(el('th', { class: ['Processes', 'MPI ranks', 'Devices'].includes(name) ? '' : 'text' }, name));
  }
  head.append(hr);
  const body = el('tbody');
  for (const t of results.traces) {
    const tr = el('tr');
    tr.append(el('td', { class: 'text' }, t.id), el('td', { class: 'text' }, t.label),
              el('td', { class: 'text' }, t.name),
              el('td', { class: 'text' }, t.display_mode), el('td', {}, t.processes),
              el('td', {}, t.mpi_ranks), el('td', {}, t.devices || ''));
    body.append(tr);
  }
  table.append(head, body);
}

function metricByKey(results, modelId, key) {
  const model = results.models.find((m) => m.id === modelId);
  return model && model.metrics.find((m) => m.key === key);
}

function renderSpeedup(results) {
  const card = document.getElementById('speedup-card');
  const speedup = metricByKey(results, 'general', 'speedup');
  const efficiency = metricByKey(results, 'general', 'efficiency');
  if (!speedup || results.traces.length < 2) { card.hidden = true; return; }
  card.hidden = false;
  const ids = results.traces.map((t) => t.id);
  const series = [
    { name: 'Speedup', values: ids.map((id) => speedup.values[id]), color: '#1f77b4' },
    { name: 'Efficiency', values: ids.map((id) => efficiency && efficiency.values[id]), color: '#ff7f0e' },
  ];
  const all = series.flatMap((s) => s.values).filter((v) => typeof v === 'number');
  const maxY = Math.max(1.1, ...all) * 1.1;
  const W = 760, H = 300, L = 50, R = 70, T = 24, B = 54;
  const x = (i) => L + (ids.length === 1 ? 0 : i * (W - L - R) / (ids.length - 1));
  const y = (v) => T + (1 - v / maxY) * (H - T - B);
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('width', '100%');
  svg.style.maxWidth = `${W}px`;
  const add = (tag, attrs, text) => {
    const n = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    svg.append(n);
    return n;
  };
  for (let k = 0; k <= 4; k++) {
    const v = maxY * k / 4;
    add('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'grid' });
    add('text', { x: L - 6, y: y(v) + 4, 'text-anchor': 'end' }, v.toFixed(1));
  }
  results.traces.forEach((t, i) => {
    add('text', { x: x(i), y: H - B + 18, 'text-anchor': 'middle' }, `${t.label} [${t.id}]`);
  });
  add('text', { x: (L + W - R) / 2, y: H - 8, 'text-anchor': 'middle' },
      results.configuration_meaning
        ? `Configuration: ${results.configuration_meaning} [Tn = trace ID]` : '');
  series.forEach((s, k) => {
    const pts = s.values.map((v, i) => (typeof v === 'number' ? [x(i), y(v)] : null)).filter(Boolean);
    if (pts.length > 1) {
      add('polyline', { points: pts.map((p) => p.join(',')).join(' '),
                        fill: 'none', stroke: s.color, 'stroke-width': 2 });
    }
    pts.forEach(([px, py]) => add('circle', { cx: px, cy: py, r: 4, fill: s.color }));
    add('rect', { x: L + 10 + k * 110, y: T - 12, width: 12, height: 4, fill: s.color });
    add('text', { x: L + 26 + k * 110, y: T - 8 }, s.name);
  });
  const box = document.getElementById('speedup');
  box.replaceChildren(svg);
}

function renderModels(results) {
  const tabs = document.getElementById('model-tabs');
  const box = document.getElementById('models');
  tabs.replaceChildren();
  box.replaceChildren();
  const thresholds = ((results.run || {}).options || {}).thresholds
    || { critical: 60, attention: 85 };

  results.models.forEach((model, index) => {
    const card = el('div', { class: 'card' });
    card.hidden = index !== 0;
    const table = el('table', { class: 'data' });
    const head = el('thead');
    const hr = el('tr');
    hr.append(el('th', {}, model.name));
    for (const t of results.traces) hr.append(el('th', {}, `${t.label} [${t.id}]`));
    head.append(hr);
    const body = el('tbody');
    for (const metric of model.metrics) {
      const tr = el('tr');
      const name = el('td', { class: 'metric' }, metric.name);
      name.style.paddingLeft = `${10 + metric.level * 18}px`;
      if (metric.level === 0) name.style.fontWeight = '600';
      tr.append(name);
      for (const t of results.traces) {
        const value = metric.values[t.id];
        const td = el('td', { class: typeof value === 'number' ? 'value' : 'value na' },
                      formatValue(value, metric.unit));
        if (typeof value === 'number' && isEfficiency(model, metric)) {
          td.style.background = efficiencyColor(value, thresholds);
          td.style.color = '#1d2430';
        }
        tr.append(td);
      }
      body.append(tr);
    }
    table.append(head, body);
    card.append(table);
    box.append(card);

    const button = el('button', { type: 'button' }, model.name);
    if (index === 0) button.classList.add('active');
    button.addEventListener('click', () => {
      [...box.children].forEach((c, k) => { c.hidden = k !== index; });
      [...tabs.children].forEach((b, k) => b.classList.toggle('active', k === index));
    });
    tabs.append(button);
  });
}

function show(results) {
  if (results.schema !== 'basicanalysis-results') {
    throw new Error('This file is not a BasicAnalysis results.json.');
  }
  if (results.schema_version > SUPPORTED_SCHEMA_VERSION) {
    alert('This results.json was written by a newer BasicAnalysis; some data may not be shown.');
  }
  renderRun(results);
  renderTraces(results);
  renderSpeedup(results);
  renderModels(results);
  document.getElementById('drop-zone').hidden = true;
  document.getElementById('results').hidden = false;
  document.title = `BasicAnalysis Desktop - ${results.run && results.run.directory || ''}`;
}

function openFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      show(JSON.parse(reader.result));
    } catch (error) {
      alert(`Cannot open ${file.name}: ${error.message}`);
    }
  };
  reader.readAsText(file);
}

document.getElementById('file-input').addEventListener('change', (event) => {
  if (event.target.files.length) openFile(event.target.files[0]);
});

const dropZone = document.getElementById('drop-zone');
['dragenter', 'dragover'].forEach((type) => document.addEventListener(type, (event) => {
  event.preventDefault();
  dropZone.classList.add('over');
}));
['dragleave', 'drop'].forEach((type) => document.addEventListener(type, (event) => {
  event.preventDefault();
  dropZone.classList.remove('over');
}));
document.addEventListener('drop', (event) => {
  if (event.dataTransfer.files.length) openFile(event.dataTransfer.files[0]);
});

// Used by the Tauri application to show a results.json read by the backend.
window.basicanalysisShow = show;
