import React from 'react';
import { useAnalysis } from '../App.jsx';
import { efficiencyColor, thresholdsOf } from '../data.js';

// Same limits as the slider of the HTML report (interactiveplots.py).
const STEP = 0.5;

function sliderGradient(thresholds) {
  const stops = [];
  for (let v = 0; v <= 100; v += 2.5) stops.push(`${efficiencyColor(v, thresholds)} ${v}%`);
  return `linear-gradient(to right, ${stops.join(', ')})`;
}

/** Efficiency interpretation of a view, with the two-handle threshold
 *  slider of the report: the thresholds of this view only. */
export default function Thresholds({ viewId }) {
  const { results, thresholdsFor, setThresholds, customThresholds } = useAnalysis();
  const defaults = thresholdsOf(results);
  const current = thresholdsFor(viewId);
  const custom = !!customThresholds[viewId];
  const { critical, attention } = current;

  const change = (name, raw) => {
    let value = Number(raw);
    const next = { ...current };
    if (name === 'critical') value = Math.min(value, attention - STEP);
    else value = Math.max(value, critical + STEP);
    next[name] = value;
    const isDefault = next.critical === defaults.critical && next.attention === defaults.attention;
    setThresholds(viewId, isDefault ? null : next);
  };

  return (
    <div className="interpretation">
      <h3>Efficiency interpretation</h3>
      <p className="small">Use the efficiency scale to identify the metrics requiring closer analysis.</p>
      <div className="scale-labels" style={{ gridTemplateColumns: `${critical}fr ${attention - critical}fr ${100 - attention}fr` }}>
        <span><b>Critical</b> &lt; {critical}%</span>
        <span><b>Attention</b> {critical}% – {attention}%</span>
        <span><b>Good</b> ≥ {attention}%</span>
      </div>
      <div className="threshold-controls">
        <span className="threshold-label">Thresholds</span>
        <div className="threshold-slider">
          <div className="threshold-track" style={{ background: sliderGradient(current) }} />
          <input type="range" min={STEP} max={100 - STEP} step={STEP} value={critical}
                 aria-label="Critical below (%)" onChange={(e) => change('critical', e.target.value)} />
          <input type="range" min={1} max={100} step={STEP} value={attention}
                 aria-label="Good from (%)" onChange={(e) => change('attention', e.target.value)} />
          <output className="threshold-bubble" style={{ left: `${critical}%` }}>{critical}%</output>
          <output className="threshold-bubble" style={{ left: `${attention}%` }}>{attention}%</output>
        </div>
        <button type="button" onClick={() => setThresholds(viewId, null)} disabled={!custom}>Reset</button>
      </div>
      {custom && (
        <p className="threshold-note">This view uses custom thresholds ({critical} / {attention});
          the report thresholds are {defaults.critical} / {defaults.attention}.</p>
      )}
      <p className="tiny"><b>Above reference (&gt; 100%):</b> values are displayed using the upper end of
        the colour scale and should be interpreted according to the selected metric.</p>
      <p className="tiny guidance-line"><b>Analysis guidance:</b> start with the lowest-efficiency metrics
        and follow their child metrics to identify the main factor contributing to the efficiency loss.</p>
    </div>
  );
}
