import React, { useMemo } from 'react';
import { useAnalysis } from '../App.jsx';
import Plot from './Plot.jsx';

function metric(results, modelId, key) {
  const model = results.models.find((m) => m.id === modelId);
  return model && model.metrics.find((m) => m.key === key);
}

export function ScalingPlot() {
  const { results, selected } = useAnalysis();
  const plot = useMemo(() => {
    if (!results) return null;
    const ticks = results.traces.map((t) => `${t.label} [${t.id}]`);
    const series = (m, name, axis) => m && ({
      x: ticks, y: results.traces.map((t) => (typeof m.values[t.id] === 'number' ? m.values[t.id] : null)),
      name, type: 'scatter', mode: 'lines+markers', yaxis: axis,
    });
    const speedup = series(metric(results, 'general', 'speedup'), 'Speedup', 'y');
    const sel = selected && metric(results, selected.modelId, selected.key);
    const selSeries = sel && sel.unit === '%' ? series(sel, `${sel.name} (%)`, 'y2') : null;
    const data = [speedup, selSeries].filter(Boolean);
    const layout = {
      xaxis: { title: { text: results.configuration_meaning
        ? `Configuration: ${results.configuration_meaning} [Tn = trace ID]` : '', font: { size: 11 } },
        type: 'category' },
      yaxis: { title: { text: 'Speedup' }, rangemode: 'tozero' },
      yaxis2: { title: { text: '%' }, overlaying: 'y', side: 'right', rangemode: 'tozero' },
      legend: { orientation: 'h', y: 1.12 },
    };
    return { data, layout };
  }, [results, selected]);
  if (!results) return null;
  if (results.traces.length < 2) {
    return <p className="muted">Scaling needs two or more traces.</p>;
  }
  return <Plot data={plot.data} layout={plot.layout} />;
}

export default function ScalingPanel() {
  return <div className="panel fill"><ScalingPlot /></div>;
}
