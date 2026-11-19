import React from 'react';
import { useAnalysis } from '../App.jsx';

export function TracesTable() {
  const { results } = useAnalysis();
  if (!results) return null;
  const run = results.run || {};
  const ba = results.basicanalysis || {};
  const scaling = run.scaling || {};
  return (
    <div>
      <details className="run">
        <summary>Run: {run.date} · BasicAnalysis {ba.version}{ba.commit ? ` (${ba.commit})` : ''}
          {scaling.selected ? ` · ${scaling.selected} scaling (${scaling.selection_mode})` : ''}</summary>
        <dl className="run-grid">
          <dt>Command</dt><dd>{run.command}</dd>
          <dt>Folder</dt><dd>{run.directory}</dd>
        </dl>
      </details>
      <p className="caption">
        {results.configuration_meaning
          ? `Configuration: ${results.configuration_meaning} [Tn = trace ID]` : ''}
      </p>
      <table className="data">
        <thead>
          <tr>
            <th className="text">ID</th><th className="text">Configuration</th>
            <th className="text">Trace</th><th className="text">Mode</th>
            <th>Processes</th><th>MPI ranks</th><th>Devices</th>
          </tr>
        </thead>
        <tbody>
          {results.traces.map((t) => (
            <tr key={t.id}>
              <td className="text">{t.id}</td><td className="text">{t.label}</td>
              <td className="text">{t.name}</td><td className="text">{t.display_mode}</td>
              <td>{t.processes}</td><td>{t.mpi_ranks}</td><td>{t.devices || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TracesPanel() {
  const { results } = useAnalysis();
  if (!results) return null;
  return <div className="panel"><TracesTable /></div>;
}
