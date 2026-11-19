import React, { useMemo } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { useAnalysis } from '../App.jsx';
import { deeperAnalysisActions, formatValue, guidance, lossStatus } from '../data.js';

const STATUS_TEXT = {
  critical: 'Critical: a large loss. The deeper analysis below helps to find its cause.',
  attention: 'Attention: a moderate loss. The deeper analysis below helps to find its cause.',
  good: 'Good in all the traces.',
};

/** Formula of a metric, rendered from its LaTeX in definitions.yaml
 *  (KaTeX, bundled); the plain-text formula when there is no LaTeX. */
// Names of quantities (Useful, LB, HybridPE, ideal...) in upright text;
// single letters (P, T, i) stay as variables, commands (\\frac) unchanged.
function uprightNames(latex) {
  return latex.replace(/(?<![\\A-Za-z])([A-Za-z]{2,})/g, '\\mathrm{$1}');
}

function Formula({ latex, text }) {
  const rendered = useMemo(() => {
    if (!latex) return null;
    latex = uprightNames(latex);
    try {
      // The LaTeX comes from metrics/definitions.yaml of BasicAnalysis, not
      // from the results file; trust is off (no \\href, \\url...).
      return katex.renderToString(latex, { displayMode: true, throwOnError: false, trust: false });
    } catch {
      return null;
    }
  }, [latex]);
  if (rendered) {
    return <div className="formula-math" title={text || ''} dangerouslySetInnerHTML={{ __html: rendered }} />;
  }
  return text ? <p className="formula">{text}</p> : null;
}

export default function MetricPanel() {
  const { results, selected, activeView, thresholdsFor } = useAnalysis();
  if (!results || !selected) return <div className="panel muted">Select a metric in a table.</div>;
  const model = results.models.find((m) => m.id === selected.modelId);
  const metric = model && model.metrics.find((m) => m.key === selected.key);
  if (!metric) return <div className="panel muted">Select a metric in a table.</div>;
  const info = guidance(metric.key, results) || {};
  const status = lossStatus(model, metric, results, thresholdsFor(activeView));
  const interpretation = info.interpretation || {};
  const actions = deeperAnalysisActions(metric.key);
  return (
    <div className="panel metric-panel">
      <h2>{info.name || metric.name} <span className="model-name">{model.name}</span></h2>
      <div className="values">
        {results.traces.map((t) => (
          <span key={t.id} className="chip">{t.id}: <b>{formatValue(metric.values[t.id], metric.unit)}</b>
            {typeof metric.values[t.id] === 'number' && metric.unit ? ` ${metric.unit}` : ''}</span>
        ))}
      </div>
      {status && <p className={`status ${status}`}>{STATUS_TEXT[status]}</p>}
      {info.definition && <p>{info.definition}</p>}
      <Formula latex={info.latex} text={info.formula} />
      {(interpretation.low || interpretation.high) && (
        <>
          <h3>How to read it</h3>
          <ul>
            {interpretation.low && <li><b>Low:</b> {interpretation.low}</li>}
            {interpretation.high && <li><b>High:</b> {interpretation.high}</li>}
            {interpretation.above_100 && <li><b>Above 100%:</b> {interpretation.above_100}</li>}
          </ul>
        </>
      )}
      {info.causes && info.causes.length > 0 && (
        <><h3>Typical causes</h3><ul>{info.causes.map((c) => <li key={c}>{c}</li>)}</ul></>
      )}
      <h3>Deeper analysis</h3>
      <div className="actions">
        {actions.map((a, i) => (
          <div key={i} className="action">
            <div className="action-head">
              <span className={`tool ${a.tool.split(' ')[0].toLowerCase()}`}>{a.tool}</span>
              {a.cfg && <code>{a.cfg}</code>}
              <button type="button" disabled title={`Planned for Phase ${a.phase}`}>
                Run (Phase {a.phase})
              </button>
            </div>
            <p>{a.what}</p>
          </div>
        ))}
      </div>
      {info.nextSteps && info.nextSteps.length > 0 && (
        <><h3>Next steps</h3><ul>{info.nextSteps.map((s) => <li key={s}>{s}</li>)}</ul></>
      )}
    </div>
  );
}
