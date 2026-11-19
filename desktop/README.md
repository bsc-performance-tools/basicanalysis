# BasicAnalysis Desktop (prototype)

Design: [`doc/design/desktop_app.rst`](../doc/design/desktop_app.rst).

BasicAnalysis runs on the cluster as always (the Python scripts, nothing to
install). Since this branch, every run also writes `results.json` next to the
CSV files. The desktop application opens that file on the laptop.

## Try the prototype now (no installation)

1. Run BasicAnalysis on some traces, on the cluster or locally:
   `python3 modelfactors.py traces/*.prv`
2. Copy the output folder to your laptop (it contains `results.json`).
3. Open `desktop/ui/index.html` in a browser (Firefox or Chrome) and open the
   `results.json` file with **Open results.json**, or drop it on the page.

To try it without running BasicAnalysis, open one of the examples in
`desktop/examples/` (Laplace MPI with 4, 8 and 16 ranks; Laplace MPI+OpenMP
with 14x4 and 28x4).

The page shows the run, the traces with their configuration labels, Speedup
and Efficiency, and one table per model (General, Application, Hybrid, Host,
Device, OpenMP runtime, GPU hardware counters), with the efficiency colours of
the report. Nothing is uploaded: the file is read in the browser.

## Next: the Tauri application (Phase 2)

The same page (`desktop/ui/`) becomes the window of the Tauri application,
which adds what a browser cannot do: open project folders, run paramedir,
Paraver and BasicAnalysis, and connect to the cluster. Building it needs Rust
and the Tauri system libraries on the laptop (see the design note).

## Layout

```
desktop/
|-- README.md
|-- ui/            front end: index.html, app.js, style.css
`-- src-tauri/     (Phase 2) Rust backend of the Tauri application
```
