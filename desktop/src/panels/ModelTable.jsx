import React from 'react';
import { useAnalysis } from '../App.jsx';
import { efficiencyColor, efficiencyTextColor, formatValue, isEfficiency } from '../data.js';

// Family of a metric (coloured stripe of its name), as in the report
// (interactiveplots._metric_family).
function metricFamily(key, label) {
  const l = label.toLowerCase();
  const k = key.toLowerCase();
  if (l.includes('cuda')) return 'cuda';
  if (l.includes('openmp')) return 'openmp';
  if (k === 'dev_offload_eff') return 'host';
  if (l.includes('mpi ') || k.startsWith('mpi_')) return 'mpi';
  if (l.includes('host ') || k.startsWith('host_')) return 'host';
  if (l.includes('device ') || k.startsWith('dev_')) return 'device';
  return 'global';
}

// Label of the report: the stdout label without the HOST/DEVICE prefixes
// in capitals (they are the table headers).
function reportLabel(metric) {
  return String(metric.label || metric.name)
    .replace(/^HOST /, 'Host ').replace(/^DEVICE /, 'Device ');
}

function valueText(value, unit) {
  if (typeof value !== 'number') return value === null || value === undefined ? '-' : String(value);
  const text = formatValue(value, unit);
  return unit === '%' ? `${text}%` : (unit && unit !== 'run average' ? `${text} ${unit}` : text);
}

/** Efficiency table of one model, in the format of the HTML report;
 *  include/exclude select metric keys. */
export default function ModelTable({ modelId, include, exclude, title, viewId }) {
  const { results, selected, setSelected, thresholdsFor } = useAnalysis();
  const model = results.models.find((m) => m.id === modelId);
  if (!model) return null;
  // As the report: only the selected metrics with a value in some trace.
  const metrics = model.metrics.filter((m) => (!include || include(m.key))
    && !(exclude && exclude(m.key))
    && results.traces.some((t) => typeof m.values[t.id] === 'number'));
  if (!metrics.length) return null;
  const thresholds = thresholdsFor(viewId);
  // A table restricted to some metrics starts at its own first level.
  const minLevel = Math.min(...metrics.map((m) => m.level));
  const hierarchical = metrics.some((m) => m.level > minLevel);

  return (
    <div className="metric-table-card">
      <table className="efficiency-table">
        <thead>
          <tr>
            <th className="metric-column-header">{title || model.name}</th>
            {results.traces.map((t) => (
              <th key={t.id} title={`${t.id}: ${t.name}\n${results.configuration_meaning || ''}: ${t.label}`}>
                {t.label} [{t.id}]
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => {
            const depth = metric.level - minLevel;
            const label = reportLabel(metric);
            const family = metricFamily(metric.key, label);
            const efficiency = isEfficiency(model, metric);
            const select = () => setSelected({ modelId: model.id, key: metric.key });
            const isSelected = selected && selected.modelId === model.id && selected.key === metric.key;
            return (
              <tr key={metric.key} className={isSelected ? 'selected' : ''}>
                <td className={`metric-name-cell metric-family-${family}`}
                    style={{ '--metric-depth': depth }} onClick={select}>
                  {hierarchical && depth === 0 ? <strong>{label}</strong>
                    : (depth > 0 ? `↳ ${label}` : label)}
                </td>
                {results.traces.map((t) => {
                  const value = metric.values[t.id];
                  const numeric = typeof value === 'number';
                  return (
                    <td key={t.id} className="metric-value-cell">
                      {numeric && efficiency ? (
                        <button type="button" className="metric-value" onClick={select}
                                title={`${label} — ${t.label} [${t.id}]`}
                                style={{ background: efficiencyColor(value, thresholds),
                                         color: efficiencyTextColor(value, thresholds) }}>
                          {valueText(value, metric.unit)}
                        </button>
                      ) : (
                        <button type="button" className={`metric-value plain${numeric ? '' : ' na'}`}
                                onClick={select}>
                          {valueText(value, metric.unit)}
                        </button>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
