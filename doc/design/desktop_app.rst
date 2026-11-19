BasicAnalysis Desktop Application (Tauri)
=========================================

:Status: Phase 1 (``results.json``) implemented; Phase 2 prototype with
         the views of the HTML report; Phase 3 started (Open in Paraver
         with the Useful Duration cfg); first prototype sent to Germán
         for design feedback (2026-11-19). See "Current state and next
         steps".
:Date: 2026-11-19
:Branch: ``feature/desktop-app``
:Related: ``assessment.rst`` (branch ``feature/assessment``),
          ``paraver_launcher.rst`` (branch ``feature/paraver-launcher``),
          ``ai_assistance.rst`` (branch ``feature/ai-assistance``)

The team agreed on 2026-11-19 to start a desktop application for
BasicAnalysis with `Tauri <https://tauri.app>`_. This document proposes how
the application fits with the current tool, what it does in each phase, and
the decisions that are still open.

**Objective.** BasicAnalysis is a performance analysis tool: it provides
performance models, guides the analyst to understand the metrics, and helps
to write an assessment following the POP methodology. The application is
the **BasicAnalysis analyzer**: when the model detects a performance loss,
it leads the analyst to the deeper analysis with the right BSC tool and
configuration (Paraver with a cfg, Dimemas with network configurations, the
Clustering tools on IPC and instructions...), brings the results back, and
adds them to the assessment. This orchestration of tools is why a desktop
framework with a backend is needed. From MemDive we take the framework
(Tauri, React, dockable panels) and its flexibility, not its features:
BasicAnalysis is not a twin of MemDive. A view of parts of the trace inside
the application may come later, but it is not a priority: Paraver remains
the tool for the detailed view.


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

**Decision (2026-11-19): Tauri**, with a React front end of dockable panels
(see `The front end: React with dockable panels`_).


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
    | Front end: React, dockable panels (system WebView)           |
    |   tables | plots | metric guidance | POP assessment | runs  |
    |            ^  Tauri commands and events (IPC)                |
    |            v                                                 |
    | Rust backend                                                 |
    |   projects: open/save results folders, results.json          |
    |   tools: run sidecars (paramedir, wxparaver, Dimemas,        |
    |          BasicAnalysis Python), stream their output          |
    |   remote (later): SSH to the cluster, run, copy results back |
    |   MCP server (later): local socket, project state as tools   |
    +--------------------------------------------------------------+

* **Front end**: React components arranged in dockable panels, shown in
  the system WebView (WebKitGTK on Linux, WKWebView on macOS, WebView2 on
  Windows). See `The front end: React with dockable panels`_.
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
    |-- project.json            name, created, BA version, notes, settings
    |-- results/                one or more BasicAnalysis results folders
    |   `-- run-2026-11-19/     results.json, CSV files, report, cfgs-report/
    |-- traces/                 optional local (cut) traces, or references
    |-- assessment/             assessment.json + images (Level 2)
    `-- paraver/                Paraver views and images saved from the app

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
   copies back the small result files (see Phase 7).

Python on the laptop
~~~~~~~~~~~~~~~~~~~~

Viewing results and writing assessments do not need Python. Re-running
BasicAnalysis locally needs a Python with the BasicAnalysis requirements.
The first versions use the user's Python (configured in the settings); the
BasicAnalysis scripts are included in the application, with the same
version as the application. Bundling a Python runtime is postponed, since
it makes the installer much larger and must be done per OS.


The front end: React with dockable panels
-----------------------------------------

The team saw MemDive and wants the same flexibility: several views at the
same time, arranged by the user, and zoomable plots of the efficiency
metrics. That flexibility comes from how the window is built, not from
Tauri, and the current HTML report cannot give it: it is one long page
generated as text by ``interactiveplots.py``.

**Decision (2026-11-19)**: a new front end built with **React**, where every
view is a component in a **dockable panel** (panels can be opened, closed,
docked side by side, stacked as tabs, or detached; the layout is saved with
the project). The panels follow the analysis workflow of BasicAnalysis, in
order of priority:

1. **Performance model and guidance** (Level 1): the efficiency tables of
   each model (Application, Runtime Model, Hybrid levels, Host, Device, GPU
   hardware counters, I/O), zoomable scaling plots, and the **metric
   details** that guide the analyst: definition, formula, interpretation
   of the value, typical causes, and next steps (``metrics/definitions.yaml``,
   as in the Metric Details of the report).
2. **Guided deeper analysis** (Level 3): from a metric with a loss, the
   actions that analyze it with the BSC tools (see `Guided deeper analysis:
   from a loss to the right tool`_), and their results as panels.
3. **POP assessment editor** (Level 2): an editable panel where the analyst
   writes the assessment following the POP template (sections of
   ``assessment.rst``), adds evidence from the other panels (a table, a
   plot, a metric with its interpretation, a Paraver image, a Dimemas
   prediction, a clustering result) with comments, and exports it to PDF
   and to the POP PowerPoint template.

**MCP** lives in the Rust backend, which knows the open project, the panels,
and the current selection. It does not depend on the front-end technology.

Consequences:

* The data/rendering separation is done through ``results.json`` (Phase 1,
  implemented): React reads it directly.
* The static HTML report stays as it is, for users without the
  application; its views are not rewritten. Whether the static report
  reuses the React components later is decided after Phase 3.
* The plain HTML/JS viewer in ``desktop/ui/`` (prototype of Phase 1) is
  replaced by the React front end; it shows what each panel needs from
  ``results.json``.

**From MemDive**: ask Victor which framework pieces can be shared: the
docking layout and chart libraries, the conventions of the MCP server,
settings, and packaging. Not its features (trace views, memory analysis).


Guided deeper analysis: from a loss to the right tool
-----------------------------------------------------

The model tells *where* the performance is lost; the BSC tools tell *why*.
For each metric with a loss (below the Critical or Attention threshold, or
on demand), the application offers **actions**: run a tool with a
configuration prepared by BasicAnalysis, show its result in a panel, and
offer it as evidence for the assessment. Examples:

.. list-table::
   :header-rows: 1
   :widths: 26 26 48

   * - Loss detected
     - Tool and configuration
     - Result
   * - Load Balance, Communication, Serialization, Transfer, Offload,
       Orchestration, I/O, Frequency...
     - **Paraver** with the cfg of the metric (the cfgs of BasicAnalysis,
       ``cfgs/`` and ``cfgs-report/``)
     - The view that shows the loss (useful duration per process, MPI
       calls, CUDA kernels and transfers, I/O calls...), to analyze in
       Paraver; its image saved as evidence.
   * - Communication Efficiency (Serialization vs Transfer)
     - **Dimemas** with network configurations (ideal network, bandwidth and
       latency sweeps)
     - Predicted execution time and efficiencies for each network: how much
       of the loss is due to the network and how much to dependencies.
   * - Computation Scalability, IPC Scalability, Instruction Scalability,
       Load Balance of computation
     - **Clustering tools** on the computation bursts (IPC × Instructions)
     - Clusters (code regions with the same behaviour), and the metrics of
       each cluster (IPC, instructions, time, scalability per cluster):
       which region loses performance and why.
   * - Others (to be defined)
     - paramedir cfgs, Folding, tools of other groups
     - New result panels.

Design:

* **Actions are declared, not hard-coded**: a file (for example
  ``actions.yaml``, next to ``definitions.yaml``) maps metrics and
  conditions to actions: tool, configuration files, parameters, and how to
  read the result. Adding an analysis is adding an entry; the ``next_steps``
  of each metric in ``definitions.yaml`` can link to its actions.
* **Tool adapters in the Rust backend**: one adapter per tool (Paraver,
  paramedir, Dimemas, Clustering tools...) knows how to prepare its inputs,
  run it as a sidecar, follow its progress, and collect its outputs into
  the project (``project/analyses/<action>-<date>/``). The tools are not
  bundled; their paths are configured.
* **Where the tools run**: on the laptop for cut traces; for large traces,
  Dimemas and the Clustering tools need the cluster (Phase 7, SSH). The
  action is the same; only the place of execution changes.
* **Results as data**: each adapter turns the tool output into JSON
  (predicted times, clusters and their metrics), so that the panels, the
  assessment, and MCP use it as any other result.

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
* SSH (Phase 7) uses the user's own SSH configuration and keys; the
  application stores no passwords.
* The MCP server (Phase 8) listens on a local socket owned by the user.


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
   *Implemented, with a plain HTML/JS viewer as prototype.*
2. **Application skeleton**: Tauri v2 + React project in ``desktop/``; open
   a results folder; dockable panels with the traces, the efficiency tables,
   zoomable scaling plots, and the metric details (guidance) from
   ``results.json`` and ``definitions.yaml``; Linux build.
   *Prototype on the branch: left menu with the views of the HTML report,
   efficiency tables in the report format, per-view threshold slider,
   scaling plots with the ideal, metric details with the formulas in
   LaTeX (KaTeX) and the proposed deeper analysis; Linux AppImage and
   deb.*
3. **Guided deeper analysis I: Paraver**: actions file and tool adapters;
   from a metric with a loss, open Paraver on a (cut) trace with the cfg of
   the metric, and save the image of the view into the project as evidence.
   *Started: Open in Paraver with* ``useful_duration.cfg`` *(Extrae
   traces verified).*
4. **POP assessment editor** (Level 2): editable panel with the POP
   sections, evidence from the panels and from the tools, comments; saved
   in the project; PDF and POP PPTX export.
5. **Guided deeper analysis II: Dimemas and Clustering**: network what-if
   for communication losses; clustering of IPC × Instructions with the
   metrics of each cluster for computation losses; their result panels.
6. **More views**: I/O and GPU hardware counter panels, comparison of runs
   in a project, re-run BasicAnalysis on small traces.
7. **Cluster connection**: run BasicAnalysis, paramedir, Dimemas, and the
   Clustering tools on the cluster over SSH and copy the results back into
   the project.
8. **MCP server** for AI assistants (``ai_assistance.rst``), exposing the
   project, its metrics, the actions, and their results.
9. *Later, not a priority*: a view of parts of the trace inside the
   application.

Repository layout (Phase 2):

::

    basicanalysis/              (branch feature/desktop-app)
    |-- modelfactors.py ...     Python core, unchanged
    |-- doc/design/desktop_app.rst
    `-- desktop/                React front end (Vite project: package.json, src/)
        `-- src-tauri/          Rust: Cargo.toml, src/, tauri.conf.json, icons

Development requirements (laptop only, not for users of the installed
application): Rust (``rustup``), Node.js (``nvm``, LTS), and the Tauri
system libraries (on Ubuntu 22.04: ``libwebkit2gtk-4.1-dev``,
``build-essential``, ``curl``, ``wget``, ``file``, ``libxdo-dev``,
``libssl-dev``, ``libayatana-appindicator3-dev``, ``librsvg2-dev``).


Current state and next steps
----------------------------

State on 2026-11-19 (branch ``feature/desktop-app``, ``fd5546a``, pushed):

* the views of the HTML report in a left menu, with the same performance
  model in each view, the tables in the report format, the threshold
  slider, "How to read this view", and the scaling plots with the ideal;
* metric details with the formulas from ``definitions.yaml`` in LaTeX;
* Open in Paraver from "Validate in Paraver" and from the metric details,
  with ``cfgs-report/useful_duration.cfg``; the trace is found from
  ``results.json``, by name next to the results, or chosen by the user;
* a first package (AppImage, deb, examples with their traces) sent to
  Germán for feedback on the design.

Open items, in order (the rule: parity with the HTML report before new
functionality):

1. **Metric details parity**: check that the metric panel shows the same
   content as the metric details of the HTML report (description,
   interpretation, formula, thresholds, related metrics, notes such as the
   workload assumptions) and add what is missing.
2. **All report cfgs in** ``cfgs-report/``: BasicAnalysis writes only
   ``useful_duration.cfg`` there today. It should copy every cfg that the
   report and ``definitions.yaml`` refer to (Python side), so that the
   other Paraver actions of the metric details can be run, not only shown.
3. **Useful Duration cfg for nsys2prv traces**: the current
   ``useful_duration.cfg`` is based on the Running state, which nsys2prv
   traces do not have, so Paraver shows an empty view. An events-based cfg
   is needed, rewritten per trace with the event codes resolved from its
   ``.pcf`` (as ``nsys2prvevents.py`` does for the metric cfgs).
4. **Feedback from Germán** on the design of the prototype.

After these: save the Paraver view image as evidence (end of Phase 3), and
then the POP assessment editor (Phase 4).


Risks
-----

* **Rust maintenance**: the team works in Python today. Mitigation: keep the
  backend small (files, processes, SSH, MCP) and all metric logic in Python.
* **Two front ends** (static report and application) diverging. Mitigation:
  both read the same metrics (``results.json`` and the same definitions);
  decide after Phase 3 whether the static report reuses the components.
* **Scope creep towards MemDive**: adding features because MemDive has
  them. Mitigation: every panel must serve the performance model, the
  guidance, the deeper analysis with the BSC tools, or the POP assessment.
* **Tool versions and outputs**: Dimemas and the Clustering tools change
  their inputs and outputs between versions. Mitigation: one adapter per
  tool with tests on real outputs, and versions recorded in each result.
* **Per-OS builds and signing** need a CI pipeline and certificates.
* **WebView differences** between OSes (WebKitGTK is behind Chromium in some
  features). Mitigation: test the views on Linux WebKitGTK first.
* **Overlap with MemDive**: both are Tauri applications at BSC with MCP.
  Opportunity to share framework pieces (docking, charts, MCP conventions,
  packaging); to be discussed with Victor.


Open questions
--------------

1. Should ``results.json`` be written always, or only with an option
   (``--json``)? Implemented: always, as the CSV files.
2. Which framework pieces to share with MemDive (docking layout, charts,
   MCP conventions, packaging, look and feel)?
3. Paraver on the laptop needs a (cut) trace: is it enough, or should the
   application also open Paraver on the cluster (remote display) in
   Phase 7?
4. Which OS after Linux: macOS or Windows?
5. Cluster connection (Phase 7): which clusters first (MareNostrum 5), and
   are batch jobs (Slurm) needed for large traces, or only interactive
   runs on the login node for small ones?
6. Distribution: GitLab releases with installers, or BSC tools download page
   as Paraver?
7. Which Dimemas network configurations and which Clustering tools
   parameters (and versions) should the first actions use?
