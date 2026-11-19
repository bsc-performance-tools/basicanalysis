# BasicAnalysis Analyzer (desktop application, prototype)

Design: [`doc/design/desktop_app.rst`](../doc/design/desktop_app.rst).

BasicAnalysis runs on the cluster as always (the Python scripts, nothing to
install). Every run writes `results.json` next to the CSV files. The analyzer
opens that results folder on the laptop: it shows the performance model,
explains each metric, and proposes the deeper analysis with the BSC tools
(Paraver with a cfg, Dimemas, Clustering tools) when a metric shows a loss.

Phase 2 prototype: a left menu with the views of the HTML report (Execution
Overview, Runtime Model, Heterogeneous Model, I/O Metrics, GPU Hardware
Counters, Scaling, and the Outer/Inner levels and runtimes), each view in a
dockable panel (⧉ opens a view beside the others), with the efficiency tables
(▼ critical, ▽ attention) and the zoomable scaling plot; on the right, the
details of the selected metric with the proposed deeper analysis. The deeper-analysis actions are shown but not run
yet (Paraver: Phase 3; Dimemas and Clustering: Phase 5).

## Run it (developers)

Requirements, on the laptop only: Rust, Node.js, and the Tauri system
libraries (see the design note). Then, in this folder:

```
npm install            # once: JavaScript dependencies
npm run tauri dev      # opens the application window (first build: several minutes)
npm run tauri build    # .deb and AppImage in src-tauri/target/release/bundle/
```

In the window, **Open results folder** and pick a BasicAnalysis output folder
(the one with `results.json`), or one of `examples/`.

Without Tauri, the same front end runs in a browser:

```
npm run dev            # then open http://localhost:5173/
```

and **Open results.json** reads the file in the browser.

## Layout

```
desktop/
|-- README.md
|-- package.json        JavaScript dependencies and scripts
|-- index.html, vite.config.js
|-- src/                React front end
|   |-- App.jsx         window, dockable layout (dockview), shared state
|   |-- Sidebar.jsx     left menu with the views of the report
|   |-- data.js         results.json, guidance (metrics/definitions.yaml),
|   |                   efficiency colours, deeper-analysis actions
|   |-- backend.js      calls to the Rust backend
|   `-- panels/         View (page of the report), Model tables, Metric details,
|                       Traces, Scaling (Plotly)
|-- src-tauri/          Rust backend (Tauri v2): open_results command
|-- examples/           results.json of Laplace MPI and MPI+OpenMP runs
`-- html-viewer/        first plain HTML/JS viewer of results.json (Phase 1)
```
