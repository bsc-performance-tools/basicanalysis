// Data of the analyzer: results.json (resultsjson.py), the metric guidance
// (metrics/definitions.yaml), efficiency colours, and the deeper-analysis
// actions offered for each metric with a loss.
import yaml from 'js-yaml';
import definitionsText from '../../metrics/definitions.yaml?raw';

export const SUPPORTED_SCHEMA_VERSION = 1;

const DEFINITIONS = yaml.load(definitionsText).metrics;

// Efficiency colours of the report (interactiveplots.EFFICIENCY_COLOR_SCALE).
const COLOR_SCALE = [
  [0.00, '#b2182b'], [0.20, '#ef6548'], [0.40, '#fdbb84'], [0.60, '#fee8a8'],
  [0.75, '#ffffbf'], [0.85, '#d9ef8b'], [0.92, '#b8e186'], [1.00, '#4dac26'],
];
const ANCHORS = { critical: 60, attention: 85, reference: 100 };

export function thresholdsOf(results) {
  return ((results.run || {}).options || {}).thresholds || { critical: 60, attention: 85 };
}

function scalePosition(value, { critical, attention }) {
  if (value < critical) return value / critical * ANCHORS.critical;
  if (value < attention) {
    return ANCHORS.critical + (value - critical) / (attention - critical)
      * (ANCHORS.attention - ANCHORS.critical);
  }
  return ANCHORS.attention + (value - attention) / (100 - attention)
    * (ANCHORS.reference - ANCHORS.attention);
}

export function efficiencyColor(value, thresholds) {
  const t = Math.max(0, Math.min(1, scalePosition(value, thresholds) / 100));
  for (let i = 1; i < COLOR_SCALE.length; i++) {
    const [p1, c1] = COLOR_SCALE[i - 1];
    const [p2, c2] = COLOR_SCALE[i];
    if (t <= p2) {
      const f = (t - p1) / (p2 - p1);
      const a = parseInt(c1.slice(1), 16), b = parseInt(c2.slice(1), 16);
      const mix = [16, 8, 0].map((s) => {
        const x = (a >> s) & 255, y = (b >> s) & 255;
        return Math.round(x + (y - x) * f);
      });
      return `rgb(${mix.join(',')})`;
    }
  }
  return COLOR_SCALE[COLOR_SCALE.length - 1][1];
}

/** Text colour of a coloured value, as in the report: white on the darkest
 *  colours of the scale. */
export function efficiencyTextColor(value, thresholds) {
  const p = scalePosition(value, thresholds);
  return (p < 25 || p >= 95) ? 'white' : '#333333';
}

// Tables whose percentages are efficiencies (coloured); the others
// (flushing, bandwidth, occupancy) are indicators.
const EFFICIENCY_MODELS = new Set(['application', 'scalability_io', 'hybrid',
  'hybrid_inner_comm', 'host', 'device', 'openmp_runtime']);
const EFFICIENCY_HWC = new Set(['dev_hwc_sm_utilization', 'dev_hwc_sm_coverage',
  'dev_hwc_sm_issue_eff']);

export function isEfficiency(model, metric) {
  if (metric.unit !== '%') return false;
  if (EFFICIENCY_MODELS.has(model.id)) return true;
  if (model.id === 'gpu_hardware_counters') return EFFICIENCY_HWC.has(metric.key);
  return model.id === 'general' && metric.key.endsWith('_eff');
}

export function formatValue(value, unit) {
  if (typeof value !== 'number') return value === null || value === undefined ? '' : String(value);
  if (unit === '%') return value.toFixed(2);
  if (Math.abs(value) >= 1000) return value.toFixed(0);
  return value.toFixed(2);
}

/** Worst status of an efficiency metric over the traces: 'critical',
 *  'attention', 'good', or null (not an efficiency or no value). */
export function lossStatus(model, metric, results, thresholds) {
  if (!isEfficiency(model, metric)) return null;
  const { critical, attention } = thresholds || thresholdsOf(results);
  let status = null;
  for (const trace of results.traces) {
    const value = metric.values[trace.id];
    if (typeof value !== 'number') continue;
    if (value < critical) return 'critical';
    if (value < attention) status = 'attention';
    else if (!status) status = 'good';
  }
  return status;
}

function templateRuntime(results) {
  const mode = (results.traces[0] || {}).display_mode || '';
  const parts = mode.split('+');
  return parts.length > 1 ? parts[parts.length - 1] : 'OpenMP';
}

function resolveTemplate(text, runtime) {
  return String(text)
    .replaceAll('{runtime_family}', runtime.toLowerCase())
    .replaceAll('{runtime}', runtime)
    .replaceAll('{{', '{').replaceAll('}}', '}');
}

/** Guidance of a metric from definitions.yaml: name, definition, formula,
 *  interpretation, typical causes, next steps (templates resolved). */
export function guidance(metricKey, results) {
  const entry = DEFINITIONS[metricKey]
    || Object.values(DEFINITIONS).find((e) => (e.aliases || []).includes(metricKey));
  if (!entry) return null;
  const runtime = templateRuntime(results);
  const field = (name) => {
    if (entry[name] !== undefined) return entry[name];
    if (entry[`${name}_template`] !== undefined) {
      const value = entry[`${name}_template`];
      return Array.isArray(value) ? value.map((v) => resolveTemplate(v, runtime))
        : resolveTemplate(value, runtime);
    }
    return undefined;
  };
  const formula = entry.formula || {};
  return {
    name: field('name'),
    definition: field('definition'),
    formula: formula.text || (formula.text_template && resolveTemplate(formula.text_template, runtime)),
    interpretation: entry.interpretation || {},
    causes: field('typical_causes') || [],
    nextSteps: field('next_steps') || [],
  };
}

// --------------------------------------------------------------------
// Deeper analysis: the BSC tool and configuration for each kind of loss
// (doc/design/desktop_app.rst, "Guided deeper analysis"). In this
// prototype the actions are shown, not run: Paraver is Phase 3, Dimemas
// and the Clustering tools Phase 5.
// --------------------------------------------------------------------

const PARAVER = 'Paraver';
const DIMEMAS = 'Dimemas';
const CLUSTERING = 'Clustering tools';

const ACTIONS = [
  {
    match: /(^|_)load_balance$/,
    actions: [
      { tool: PARAVER, cfg: 'cfgs-report/useful_duration.cfg', phase: 3,
        what: 'Useful computation per process and thread: who computes longer.' },
      { tool: CLUSTERING, phase: 5,
        what: 'Clusters of the computation bursts: which code region is imbalanced.' },
    ],
  },
  {
    match: /(^|_)(comm_eff|serial_eff|transfer_eff)$/,
    exclude: /^dev_/,
    actions: [
      { tool: PARAVER, cfg: 'cfgs-report/MPI_call.cfg', phase: 3,
        what: 'MPI calls over time: where the processes wait.' },
      { tool: DIMEMAS, phase: 5,
        what: 'Replay with an ideal network and with bandwidth/latency sweeps: how much of the loss is due to the network (Transfer) and how much to dependencies (Serialization).' },
    ],
  },
  {
    match: /(^|_)(comp_scale|ipc_scale|inst_scale)$/,
    actions: [
      { tool: CLUSTERING, phase: 5,
        what: 'Clustering of IPC × Instructions and metrics per cluster: which region loses IPC or executes more instructions.' },
      { tool: PARAVER, cfg: 'cfgs-report/2dh_duration_IPC.cfg', phase: 3,
        what: 'Histogram of burst duration versus IPC.' },
      { tool: PARAVER, cfg: 'cfgs-report/2dh_useful_instructions.cfg', phase: 3,
        what: 'Histogram of useful instructions per burst.' },
    ],
  },
  {
    match: /^dev_(comm_eff|orches_eff|load_balance|parallel_eff|offload_eff)$|^host_parallel_eff$/,
    actions: [
      { tool: PARAVER, cfg: 'cfgs-report/cuda_kernel.cfg', phase: 3,
        what: 'Kernels and memory transfers on the GPU streams, and the host CUDA calls.' },
    ],
  },
  {
    match: /^omp_|^omp_talp_|^hybrid_eff$/,
    actions: [
      { tool: PARAVER, cfg: 'cfgs-report/parallel_functions_useful.cfg', phase: 3,
        what: 'Parallel functions and useful time of the threads.' },
    ],
  },
  {
    match: /^io_/,
    actions: [
      { tool: PARAVER, cfg: 'cfgs-report/io_calls.cfg', phase: 3,
        what: 'I/O calls over time and per process.' },
    ],
  },
];

export function deeperAnalysisActions(metricKey) {
  const result = [];
  for (const rule of ACTIONS) {
    if (rule.match.test(metricKey) && !(rule.exclude && rule.exclude.test(metricKey))) {
      result.push(...rule.actions);
    }
  }
  if (!result.length) {
    result.push({ tool: PARAVER, cfg: 'cfgs-report/useful_duration.cfg', phase: 3,
                  what: 'Timeline of useful computation, to start a detailed analysis.' });
  }
  return result;
}

export function checkResults(results) {
  if (!results || results.schema !== 'basicanalysis-results') {
    throw new Error('This file is not a BasicAnalysis results.json.');
  }
  return results.schema_version > SUPPORTED_SCHEMA_VERSION
    ? 'This results.json was written by a newer BasicAnalysis; some data may not be shown.'
    : null;
}
