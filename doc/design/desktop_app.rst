BasicAnalysis Desktop Application (Tauri)
=========================================

:Status: Design, for review by the team
:Date: 2026-11-19
:Branch: ``feature/desktop-app``
:Related: ``assessment.rst`` (branch ``feature/assessment``),
          ``paraver_launcher.rst`` (branch ``feature/paraver-launcher``),
          ``ai_assistance.rst`` (branch ``feature/ai-assistance``)

The team agreed on 2026-11-19 to start a desktop application for
BasicAnalysis with `Tauri <https://tauri.app>`_. This document proposes how
the application fits with the current tool, what it does in each phase, and
the decisions that are still open.


Context
-------

BasicAnalysis has three levels of goals (meeting of 2026-11-10):

1. **Interactive reporting**: views, plots, explanations, filters, and
   comparisons. The current single-file HTML report covers it.
2. **Personalized assessments**: Paraver views, observations, and comments
   organized into an editable report that can be saved and exported (POP
   assessment style). The static report can only do a limited, single-user
   version, with the data in the browser storage.
3. **Tool integration**: run Paraver configurations, Dimemas, and other
   tools from the analysis, retrieve their results, and update the
   analysis. A page in a browser cannot run programs, so this level needs a
   local backend.

Options considered for levels 2 and 3:

* **Python Dash**: discarded (2026-11-16). The other BSC group does not use
  it, and Victor recommended Tauri.
* **A local Python server** (``basicanalysis serve``) with the report as its
  front end: our earlier plan.
* **A Tauri desktop application**: a native window with a web front end and
  a Rust backend that can run other programs (sidecars). MemDive, from
  another BSC group, is built this way (Tauri, Rust, React) and already
  reads and writes Paraver traces, generates Extrae configurations, and
  offers a local MCP server to AI assistants.

**Decision (2026-11-19): Tauri.**


The main constraint: analysis on the cluster, exploration on the laptop
-----------------------------------------------------------------------

This is the main difference with MemDive. BasicAnalysis must analyze large
traces, which only fit, and only finish in reasonable time, on the cluster
where they were recorded. The cluster login and compute nodes have no
graphical environment, and users cannot install software there. Today users
copy the BasicAnalysis Python scripts and run them; nothing is installed.

Therefore:

* **On the cluster nothing changes.** BasicAnalysis stays a set of Python
  scripts with the same requirements (Python 3, NumPy, pandas, matplotlib,
  paramedir). No binary is built or installed there.
* **The desktop application runs only on the laptop.** It is installed once,
  as Paraver or MemDive are, and works on the **results folder** produced on
  the cluster. It does not need to compute the metrics of large traces.
* **The results folder is the contract** between the two sides.

::

    CLUSTER (unchanged)                        LAPTOP (new)
    ------------------                         ------------------------------
    python3 modelfactors.py traces ...         BasicAnalysis Desktop (Tauri)
      + paramedir                                installed once per laptop
            |                                          |
            v                                          v
    results folder  ---- scp / rsync / SSH ---->  open results folder
      CSV files, HTML report,                       L1 interactive views
      results.json (new)                            L2 assessment, notes
                                                    L3 Paraver, Dimemas,
                                                       re-analysis (small traces)

The static HTML report is still produced, so a user without the application
still gets a complete report with nothing to install.


Cluster side: the ``results.json`` export
-----------------------------------------

The only change on the Python side is a new output file, ``results.json``,
written next to the CSV files of every run. It contains everything the
report shows, in one machine-readable file:

* **Run**: BasicAnalysis version and commit, command line, date, host,
  options (scaling mode, workload, thresholds, model), and a
  ``schema_version``.
* **Traces**: trace ID (T1, T2...), file name and path, trace mode,
  processes, ranks, threads, devices, GPU streams, configuration label
  (``8 × 1 GPU``), its meaning (``Processes × GPUs per process``),
  simulation and consistency flags.
* **Metrics**: every metric of every model (Application, Runtime Model,
  Hybrid levels, Host, Device, GPU hardware counters, I/O, OpenMP runtime)
  per trace, with its key, display name, parent (hierarchy), unit, and
  value, or ``Non-Avail``/``NaN`` with its reason.
* **Raw data**: the content of ``rawdata.csv``, keyed the same way.
* **Definitions**: a reference to ``metrics/definitions.yaml`` entries (key
  and version), not a copy, to keep the file small.
* **Paraver context**: the cfgs written to ``cfgs-report/`` and the views
  that each metric links to.

Notes:

* The CSV files and the HTML report do not change; ``results.json`` is added.
* The content already exists in memory: ``reportdata.build_report()`` and the
  report model (``report/model``) hold it before the HTML is rendered.
  ``results.json`` is a serialization of that model plus the metric
  dictionaries.
* The schema is versioned and documented (JSON Schema in ``doc/``), so that
  the application, the MCP server, and user scripts can rely on it. This is
  useful even without the application: today scripts must parse CSV files
  whose labels change (for example the GPU configuration labels of
  2026-11-19).
* The traces are **not** copied into the results folder. The application
  works without them; Level 3 features that need a trace use a local (cut)
  copy or the cluster (see `Traces on the laptop`_).


Laptop side: the application
----------------------------

Components
~~~~~~~~~~

::

    +------------------- BasicAnalysis Desktop -------------------+
    | Front end (system WebView)                                   |
    |   project browser | report views | assessment | tool runs    |
    |            ^  Tauri commands and events (IPC)                |
    |            v                                                 |
    | Rust backend                                                 |
    |   projects: open/save results folders, results.json          |
    |   tools: run sidecars (paramedir, wxparaver, Dimemas,        |
    |          BasicAnalysis Python), stream their output          |
    |   remote (later): SSH to the cluster, run, copy results back |
    |   MCP server (later): local socket, project state as tools   |
    +--------------------------------------------------------------+

* **Front end**: the windows and views, written in HTML/JS and shown in the
  system WebView (WebKitGTK on Linux, WKWebView on macOS, WebView2 on
  Windows). See `Open decision: the front end`_.
* **Rust backend**: everything a browser page cannot do: files of the
  project, running programs, the network (SSH), and the MCP server. The
  front end calls it through Tauri *commands*; long tasks report progress
  through *events*.
* **Sidecars**: external programs started by the backend. paramedir and
  wxparaver are found in the ``PATH`` or configured in the settings; they
  are not bundled. Python is only needed to re-run BasicAnalysis locally
  (see `Python on the laptop`_).

Analysis project
~~~~~~~~~~~~~~~~

The application works on **analysis projects**. A project is a folder that
can be copied, archived, or shared:

::

    my-analysis/
    ├── project.json            name, created, BA version, notes, settings
    ├── results/                one or more BasicAnalysis results folders
    │   └── run-2026-11-19/     results.json, CSV files, report, cfgs-report/
    ├── traces/                 optional local (cut) traces, or references
    ├── assessment/             assessment.json + images (Level 2)
    └── paraver/                Paraver views and images saved from the app

A results folder copied from the cluster can also be opened directly; the
application then offers to create a project around it.

What the application does in each level
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Level 1**: open a results folder or project, show the same views as the
  HTML report (overview, Runtime Model, Heterogeneous Model, scaling,
  metric details), and compare runs of the same project.
* **Level 2**: the assessment editor of ``assessment.rst``, saving to
  ``assessment/`` in the project instead of the browser storage; paste
  images from Paraver; export to PDF and to the POP PowerPoint template.
* **Level 3**: open Paraver on a trace with the cfg behind a metric (the
  Paraver helper of ``paraver_launcher.rst`` becomes a backend command), run
  paramedir cfgs and show their results, run Dimemas, and re-run
  BasicAnalysis on small traces.

Traces on the laptop
~~~~~~~~~~~~~~~~~~~~

Large traces stay on the cluster. Level 3 features that need a trace use:

1. a **cut trace** copied to the laptop (Paraver Cutter around the region of
   interest), which is the usual practice for detailed analysis; or
2. later, the **cluster**: the backend runs paramedir there over SSH and
   copies back the small result files (see Phase 6).

Python on the laptop
~~~~~~~~~~~~~~~~~~~~

Viewing results and writing assessments do not need Python. Re-running
BasicAnalysis locally needs a Python with the BasicAnalysis requirements.
The first versions use the user's Python (configured in the settings); the
BasicAnalysis scripts are included in the application, with the same
version as the application. Bundling a Python runtime is postponed, since
it makes the installer much larger and must be done per OS.


Open decision: the front end
----------------------------

Option A: reuse the current HTML/JS of the report (recommended to start)
   The report views are already HTML, CSS, and JavaScript with Plotly. The
   application loads them from ``results.json`` instead of data embedded
   in the HTML file, and adds a small shell (project browser, menus, tool
   panel) in plain JavaScript. No Node.js build step is needed at the
   beginning, and the views stay identical to the static report.

Option B: a new front end with React (as MemDive)
   Better suited to complex layouts (dockable panels, the assessment
   editor) and closer to MemDive if components are shared later. It needs
   Node.js and a build step, and the report views must be rewritten.

Recommendation: start with option A for Phases 1 and 2, keeping the views
as independent JavaScript modules that read ``results.json``. Decide on
React before Phase 4 (assessment editor), when the needs of the editor are
known. The Rust backend and the project format do not depend on this
choice.

A prerequisite of both options is to separate the report **data** from its
**rendering**: the views read ``results.json`` (or the same JSON embedded
in the static HTML report) instead of values written into the HTML by
``interactiveplots.py``. The static report and the application then share
the same views.


Security
--------

* The backend exposes only the commands the front end needs (Tauri
  capabilities); there is no generic "run any command".
* Sidecars are run with argument lists, never through a shell, and only
  from the configured paths.
* Files are read and written inside the opened project or results folder,
  except the files the user picks explicitly.
* Results folders can come from other users: their content (labels, notes,
  file names) is shown as text, never as HTML.
* SSH (Phase 6) uses the user's own SSH configuration and keys; the
  application stores no passwords.
* The MCP server (Phase 7) listens on a local socket owned by the user.


Packaging and distribution
--------------------------

* Tauri builds a native installer per OS: ``.deb`` and AppImage on Linux,
  ``.dmg`` on macOS, ``.msi`` on Windows. Each must be built on (or for)
  its OS; a CI pipeline builds them.
* Linux first (the team's laptops), then macOS; Windows when requested.
* Installers of macOS and Windows should be signed, or users must allow
  them by hand.
* The application version follows the BasicAnalysis version, and the
  application checks the ``schema_version`` of ``results.json``: a newer
  application opens older results; an older application warns about newer
  results.


Phases
------

Each phase is usable on its own and is reviewed by the team before the
next one.

0. **Design** (this document) and the ``results.json`` schema.
1. **``results.json`` export** in the Python core (cluster side), with
   tests and documentation. Useful without the application.
2. **Application skeleton**: Tauri v2 project in ``desktop/``; open a
   results folder or project; show the overview and the efficiency tables
   from ``results.json``; Linux build.
3. **All report views** in the application, shared with the static report
   (data/rendering separation); comparison of runs in a project.
4. **Assessment editor** (Level 2) saving into the project; PDF and POP
   PPTX export.
5. **Local tools** (Level 3): open Paraver on a trace and cfg, run
   paramedir cfgs and Dimemas, re-run BasicAnalysis on small traces.
6. **Cluster connection**: run BasicAnalysis and paramedir on the cluster
   over SSH and copy the results back into the project.
7. **MCP server** for AI assistants (``ai_assistance.rst``), exposing the
   project, its metrics, and the tool runs.

Repository layout (Phase 2):

::

    basicanalysis/              (branch feature/desktop-app)
    ├── modelfactors.py ...     Python core, unchanged
    ├── doc/design/desktop_app.rst
    └── desktop/
        ├── src-tauri/          Rust: Cargo.toml, src/, tauri.conf.json, icons
        └── ui/                 HTML/JS of the application window

Development requirements (laptop only): Rust (``rustup``), the Tauri system
libraries (on Ubuntu 22.04: ``libwebkit2gtk-4.1-dev``, ``libgtk-3-dev``,
``librsvg2-dev``, ``libayatana-appindicator3-dev``, ``build-essential``,
``libssl-dev``), and Node.js only if option B is chosen.


Risks
-----

* **Rust maintenance**: the team works in Python today. Mitigation: keep the
  backend small (files, processes, SSH, MCP) and all metric logic in Python.
* **Two front ends** (static report and application) diverging. Mitigation:
  shared views reading the same JSON.
* **Per-OS builds and signing** need a CI pipeline and certificates.
* **WebView differences** between OSes (WebKitGTK is behind Chromium in some
  features). Mitigation: test the views on Linux WebKitGTK first.
* **Overlap with MemDive**: both are Tauri applications at BSC with Paraver
  integration and MCP. Opportunity to share components (Paraver file
  readers, MCP conventions, settings); to be discussed with Victor.


Open questions
--------------

1. Front end: option A (reuse our HTML/JS) or option B (React)?
2. Should ``results.json`` be written always, or only with an option
   (``--json``)? Proposal: always, as the CSV files.
3. Which components or conventions to share with MemDive (Paraver file
   handling, MCP tools, look and feel)?
4. Which OS after Linux: macOS or Windows?
5. Cluster connection (Phase 6): which clusters first (MareNostrum 5), and
   are batch jobs (Slurm) needed for large traces, or only interactive
   runs on the login node for small ones?
6. Distribution: GitLab releases with installers, or BSC tools download page
   as Paraver?
