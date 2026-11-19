import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { DockviewReact, themeLight } from 'dockview-react';
import { checkResults, thresholdsOf } from './data.js';
import { buildViews } from './views.js';
import Sidebar from './Sidebar.jsx';
import ViewPanel from './panels/ViewPanel.jsx';
import PanelBoundary from './panels/PanelBoundary.jsx';
import { openParaver, openResultsDialog, isTauri, paraverCommand } from './backend.js';
import TracesPanel from './panels/TracesPanel.jsx';
import ModelPanel from './panels/ModelPanel.jsx';
import ScalingPanel from './panels/ScalingPanel.jsx';
import MetricPanel from './panels/MetricPanel.jsx';

// The open results and the selected metric, shared by all the panels.
const AnalysisContext = createContext(null);
export const useAnalysis = () => useContext(AnalysisContext);

// Every panel is wrapped so that an error stays inside it.
const guarded = (Component) => function GuardedPanel(props) {
  return <PanelBoundary><Component {...props} /></PanelBoundary>;
};

const components = {
  traces: guarded(TracesPanel),
  model: guarded(ModelPanel),
  scaling: guarded(ScalingPanel),
  metric: guarded(MetricPanel),
  view: guarded(ViewPanel),
};

function initialMetric(results) {
  const app = results.models.find((m) => m.id === 'application') || results.models[0];
  return app && app.metrics.length ? { modelId: app.id, key: app.metrics[0].key } : null;
}

// Main area: the view chosen in the left menu (as a page of the HTML
// report). Right: the details of the selected metric with the deeper
// analysis. Any view can also be opened beside, in its own panel.
function layoutPanels(api, results) {
  api.clear();
  const first = buildViews(results)[0];
  api.addPanel({ id: 'main', component: 'view', title: first.label, params: { viewId: first.id } });
  api.addPanel({
    id: 'metric', component: 'metric', title: 'Metric details and deeper analysis',
    position: { direction: 'right' }, initialWidth: 520,
  });
}

export default function App() {
  const [results, setResults] = useState(null);
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState('');
  const [resultsDir, setResultsDir] = useState(null);
  const [activeView, setActiveView] = useState('overview');
  const beside = useRef(0);
  const apiRef = useRef(null);
  const fileInput = useRef(null);

  const show = useCallback((data, source) => {
    try {
      const warning = checkResults(data);
      setResults(data);
      setSelected(initialMetric(data));
      setMessage(warning || `Opened ${source}`);
      setActiveView('overview');
      if (apiRef.current) layoutPanels(apiRef.current, data);
    } catch (error) {
      setMessage(error.message);
    }
  }, []);

  const open = async () => {
    if (isTauri()) {
      try {
        const opened = await openResultsDialog();
        if (opened) { setResultsDir(opened.path); show(opened.results, opened.path); }
      } catch (error) {
        setMessage(String(error));
      }
    } else {
      fileInput.current.click();
    }
  };

  const readFile = (file) => {
    const reader = new FileReader();
    reader.onload = () => {
      try { show(JSON.parse(reader.result), file.name); } catch (error) { setMessage(error.message); }
    };
    reader.readAsText(file);
  };

  // Used by tests and by the backend to show a results.json directly.
  window.basicanalysisShow = (data) => show(data, 'results.json');

  // Browser mode: ?results=<url of a results.json on the same server>.
  useEffect(() => {
    const url = new URLSearchParams(window.location.search).get('results');
    if (!url || isTauri()) return;
    const select = new URLSearchParams(window.location.search).get('select');
    fetch(url).then((r) => r.json()).then((data) => {
      show(data, url);
      if (select) {
        const [modelId, key] = select.split(':');
        setSelected({ modelId, key });
      }
      // Test hook: ?clicks=scaling,scaling,overview clicks the menu in order.
      const clicks = (new URLSearchParams(window.location.search).get('clicks') || '').split(',').filter(Boolean);
      clicks.forEach((id, i) => setTimeout(() => {
        const view = buildViews(data).find((v) => v.id === id);
        if (view) { console.log(`click ${id}`); openView(view); }
      }, 500 * (i + 1)));
      // Test hook: ?thresholds=runtime:50:80 sets the thresholds of a view.
      const th = new URLSearchParams(window.location.search).get('thresholds');
      if (th) {
        const [tv, tc, ta] = th.split(':');
        setTimeout(() => setThresholds(tv, { critical: Number(tc), attention: Number(ta) }), 300);
      }
      const viewId = new URLSearchParams(window.location.search).get('view');
      if (viewId) {
        const view = buildViews(data).find((v) => v.id === viewId);
        if (view) setTimeout(() => openView(view), 0);
      }
    })
      .catch((error) => setMessage(`Cannot open ${url}: ${error.message}`));
  }, [show]);

  const views = useMemo(() => (results ? buildViews(results) : []), [results]);

  const openView = (view) => {
    const api = apiRef.current;
    let panel = api && api.getPanel('main');
    if (!panel) {
      api.addPanel({ id: 'main', component: 'view', title: view.label, params: { viewId: view.id },
                     position: api.getPanel('metric') ? { referencePanel: 'metric', direction: 'left' } : undefined });
      panel = api.getPanel('main');
    } else {
      panel.api.updateParameters({ viewId: view.id });
      panel.api.setTitle(view.label);
    }
    panel.api.setActive();
    setActiveView(view.id);
  };

  const openViewBeside = (view) => {
    const api = apiRef.current;
    beside.current += 1;
    api.addPanel({
      id: `view-${view.id}-${beside.current}`, component: 'view', title: view.label,
      params: { viewId: view.id },
      position: api.getPanel('main') ? { referencePanel: 'main', direction: 'right' } : undefined,
    });
  };

  // Thresholds of each view (the slider of its Efficiency interpretation),
  // as in the report; saved in the browser storage for this results folder.
  const [viewThresholds, setViewThresholds] = useState({});
  const storageKey = results ? `ba-thresholds:${(results.run || {}).directory || ''}` : null;
  useEffect(() => {
    if (!storageKey) return;
    try { setViewThresholds(JSON.parse(localStorage.getItem(storageKey) || '{}')); } catch { setViewThresholds({}); }
  }, [storageKey]);
  const thresholdsFor = useCallback((viewId) => (results
    ? viewThresholds[viewId] || thresholdsOf(results) : null), [results, viewThresholds]);
  const setThresholds = useCallback((viewId, value) => {
    setViewThresholds((current) => {
      const next = { ...current };
      if (value) next[viewId] = value; else delete next[viewId];
      try { if (storageKey) localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* not saved */ }
      return next;
    });
  }, [storageKey]);

  // Open Paraver on a trace with a cfg of the results folder (Tauri), or copy
  // the command of the report (browser).
  const runParaver = useCallback(async (trace, cfg) => {
    if (!isTauri() || !resultsDir) {
      const command = paraverCommand(trace, cfg);
      try { await navigator.clipboard.writeText(command); setMessage(`Copied: ${command}`); } catch {
        setMessage(command);
      }
      return;
    }
    try {
      const command = await openParaver(resultsDir, trace, cfg);
      setMessage(`Paraver started: ${command}`);
    } catch (error) {
      setMessage(String(error.message || error));
    }
  }, [resultsDir]);

  const context = useMemo(() => ({
    results, selected, setSelected, activeView, thresholdsFor, setThresholds,
    customThresholds: viewThresholds, runParaver, canRunParaver: isTauri() && !!resultsDir,
  }), [results, selected, activeView, thresholdsFor, setThresholds, viewThresholds, runParaver, resultsDir]);

  return (
    <AnalysisContext.Provider value={context}>
      <div className="app">
        <header className="app-header">
          <div className="brand">BasicAnalysis <span>Analyzer — prototype</span></div>
          <div className="header-right">
            <span className="message">{message}</span>
            <button type="button" className="primary" onClick={open}>
              Open results{isTauri() ? ' folder' : '.json'}
            </button>
            <input ref={fileInput} type="file" accept=".json,application/json" hidden
                   onChange={(e) => e.target.files.length && readFile(e.target.files[0])} />
          </div>
        </header>
        <div className="body">
        {results && <Sidebar views={views} active={activeView} onOpen={openView} onOpenBeside={openViewBeside} />}
        <div className="dock">
          {!results && (
          <section className="welcome">
            <h1>Open the results of a BasicAnalysis run</h1>
            <p>Run BasicAnalysis on the cluster as usual, copy its output folder to this
              computer, and open it. The analyzer shows the performance model, explains
              each metric, and proposes the deeper analysis with the BSC tools when a
              metric shows a loss.</p>
          </section>
          )}
          <DockviewReact
            className="dock-view"
            theme={themeLight}
            components={components}
            onReady={(event) => {
              apiRef.current = event.api;
              if (results) layoutPanels(event.api, results);
            }}
          />
        </div>
        </div>
      </div>
    </AnalysisContext.Provider>
  );
}
