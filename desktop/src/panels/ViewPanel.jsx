import React, { useMemo } from 'react';
import { useAnalysis } from '../App.jsx';
import Thresholds from './Thresholds.jsx';
import { buildViews, idealValues, seriesValues } from '../views.js';
import ModelTable from './ModelTable.jsx';
import Plot from './Plot.jsx';

const PLOT_COLORS = ['#1f5f99', '#e07b1a', '#2a9d5c', '#8e44ad', '#c0392b'];

function traceTicks(results) {
  return results.traces.map((t) => `${t.label} [${t.id}]`);
}

/** Trend plot of some metrics across the traces, in trace-ID order, with
 *  the ideal line for Speedup and Efficiency (as in the report). */
function TrendPlot({ results, section }) {
  const ticks = traceTicks(results);
  const series = section.series.map((ref) => seriesValues(results, ref)).filter(Boolean);
  if (!series.length) return null;
  const data = series.map((sr, i) => ({
    x: ticks, y: sr.values, name: sr.name, type: 'scatter', mode: 'lines+markers+text',
    text: section.ideal ? sr.values.map((v) => (v === null ? '' : v.toFixed(2))) : undefined,
    textposition: 'top center', line: { color: PLOT_COLORS[i % PLOT_COLORS.length], width: 2.5 },
  }));
  if (section.ideal) {
    data.push({ x: ticks, y: idealValues(results, section.ideal), name: 'Ideal', type: 'scatter',
                mode: 'lines', line: { dash: 'dash', color: '#7f8c9a', width: 2 } });
  }
  const layout = {
    xaxis: { type: 'category', title: { text: results.configuration_meaning
      ? `Configuration: ${results.configuration_meaning} [Tn = trace ID]` : '', font: { size: 10 } } },
    yaxis: { title: { text: section.yTitle || '' }, rangemode: 'tozero' },
    legend: { orientation: 'h', y: 1.15 },
    showlegend: true,
    margin: { l: 60, r: 20, t: 40, b: 70 },
  };
  return (
    <div className="plot-block">
      {section.title && <h3>{section.title}</h3>}
      {section.description && <p className="view-description">{section.description}</p>}
      <div className="plot-frame"><Plot data={data} layout={layout} /></div>
    </div>
  );
}

function OverviewTable({ results, name }) {
  const table = (results.overview || {})[name];
  if (!table) return <p className="muted">Not available in this results.json.</p>;
  return (
    <table className="data">
      <thead><tr>{table.columns.map((c, i) => <th key={c} className={i < 3 ? 'text' : ''}>{c}</th>)}</tr></thead>
      <tbody>
        {table.rows.map((row) => (
          <tr key={row[0]}>{row.map((v, i) => (
            <td key={i} className={i < 3 ? 'text' : ''}>{v === null || v === undefined ? '-' : String(v)}</td>
          ))}</tr>
        ))}
      </tbody>
    </table>
  );
}

function RunInfo({ results }) {
  const run = results.run || {};
  const modes = [...new Set(results.traces.map((t) => t.display_mode))];
  return (
    <div className="run-info">
      <p><b>Command:</b> <code>{run.command}</code></p>
      <p><b>Trace mode:</b> {modes.join(', ')}</p>
    </div>
  );
}

function Paraver({ results }) {
  return (
    <>
      <p>Use the recommended Paraver views to inspect the execution in greater detail and
        investigate the behaviour highlighted by the BasicAnalysis metrics.</p>
      <table className="data">
        <thead><tr><th className="text">Trace</th><th className="text">Recommended view</th><th>Action</th></tr></thead>
        <tbody>
          {results.traces.map((t) => (
            <tr key={t.id}>
              <td className="text">{t.id} {t.name}</td>
              <td className="text">Useful Duration timeline <code>useful_duration.cfg</code></td>
              <td><button type="button" disabled title="Planned for Phase 3">Open (Phase 3)</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function ScalingModel({ results }) {
  const sc = (results.run || {}).scaling || {};
  const rows = [
    ['Detected scaling', sc.detected || (results.traces.length > 1 ? '-' : 'not applicable')],
    ['Scaling used', sc.selected],
    ['How it was chosen', sc.selection_mode],
    ['Changed by the user', sc.overridden ? 'yes' : 'no'],
  ];
  return (
    <>
      <p className="view-description">Scaling behaviour detected from the analyzed executions and the
        model used to compute the scalability metrics.</p>
      <table className="data compact">
        <tbody>{rows.filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => (
          <tr key={k}><td className="text">{k}</td><td className="text"><b>{String(v)}</b></td></tr>
        ))}</tbody>
      </table>
      {sc.status_message && <p className="muted">{sc.status_message}</p>}
    </>
  );
}

function Section({ results, section, viewId }) {
  switch (section.type) {
    case 'heading': return <h2>{section.text}</h2>;
    case 'h3': return <h3>{section.text}</h3>;
    case 'guide':
      return (
        <details className="guide-note">
          <summary>How to read this view</summary>
          {section.paragraphs.map((p) => <p key={p}>{p}</p>)}
        </details>
      );
    case 'text': return <>{section.paragraphs.map((p) => <p key={p} className="guidance small">{p}</p>)}</>;
    case 'note':
      return (
        <div className="scope-note">
          {section.title && <b>{section.title}</b>}
          {section.paragraphs.map((p) => <p key={p}>{p}</p>)}
        </div>
      );
    case 'list':
      return (
        <div>
          {section.intro && <p>{section.intro}</p>}
          <ul>{section.items.map((i) => <li key={i}>{i}</li>)}</ul>
          {section.outro && <p className="muted">{section.outro}</p>}
        </div>
      );
    case 'run': return <RunInfo results={results} />;
    case 'table': return <OverviewTable results={results} name={section.table} />;
    case 'model':
      return (
        <section>
          <ModelTable modelId={section.modelId} include={section.include} viewId={viewId}
                      exclude={section.exclude} title={section.title} />
        </section>
      );
    case 'interpretation': return <Thresholds viewId={viewId} />;
    case 'paraver': return <Paraver results={results} />;
    case 'scalingModel': return <ScalingModel results={results} />;
    case 'plot': return <TrendPlot results={results} section={section} />;
    case 'plotPair':
      return (
        <div className="plot-pair">
          {section.plots.map((p) => <TrendPlot key={p.title} results={results} section={p} />)}
        </div>
      );
    default: return null;
  }
}

/** One view of the left menu, with the sections of the report. */
export default function ViewPanel({ params }) {
  const { results } = useAnalysis();
  const views = useMemo(() => (results ? buildViews(results) : []), [results]);
  if (!results) return null;
  const view = views.find((v) => v.id === params.viewId) || views[0];
  const firstTable = view.sections.findIndex((x) => x.type === 'model' || x.type === 'plot'
    || x.type === 'plotPair');
  return (
    <div className="panel view">
      <h1>{view.title || view.label}</h1>
      {view.sections.map((section, i) => (
        <React.Fragment key={i}>
          {/* The meaning of the column headers, before the first metric table. */}
          {i === firstTable && results.configuration_meaning && (
            <p className="trace-columns">Trace columns: <b>{results.configuration_meaning}</b> [Trace ID]
              <span className="muted"> — hover a column header for its trace</span></p>
          )}
          <Section results={results} section={section} viewId={view.id} />
        </React.Fragment>
      ))}
    </div>
  );
}
