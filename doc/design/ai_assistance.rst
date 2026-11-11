AI Assistance for BasicAnalysis
===============================

:Status: Design; not implemented
:Date: 2026-11-12
:Branch: ``feature/ai-assistance``
:Scope: Interactive report, a tool interface for AI assistants (MCP), and
        the Level 3 backend (``doc/design/paraver_launcher.rst``).

Two requests point to the same need. Jesús asked for a way to ask an AI
assistant questions from the report, about the metrics being looked at. The
head of the group asked whether BasicAnalysis can be offered to AI agents as
a tool, through the Model Context Protocol (MCP). This document proposes one
design for both.


Context
-------

The two requests start from opposite sides:

* **From the report to the assistant** (Jesús): the analyst is looking at a
  view or a metric and asks, for example, "Why is Device Orchestration
  Efficiency low here?" or "Which Paraver view should I look at next?".
* **From the assistant to BasicAnalysis** (MCP): the analyst works in an AI
  application (Claude Desktop, Claude Code, or another MCP client) and asks
  it to analyze traces; the assistant runs BasicAnalysis, reads the metrics,
  and explains them.

**MCP** is an open protocol to connect AI assistants to external tools and
data. A program, the *MCP server*, exposes a set of functions (name,
description, typed parameters); any MCP client can call them during a
conversation. The MCP server is not an agent: the agent is the assistant,
and the server gives it access to the tool.

Both requests need the same two things:

#. **The data of the analysis in a structured form**: the metric values per
   trace, the configurations, the scaling model, and the thresholds, rather
   than HTML.
#. **The knowledge of the model**: the definitions, interpretation, possible
   causes, and next steps of ``metrics/definitions.yaml``. Given to the
   assistant with the values, it keeps the answers grounded in the POP model
   instead of in generic explanations.

The report already embeds the second for each metric
(``window.metricInfo_<section>``: title, definition, interpretation,
recommendations, thresholds), and each value cell carries its value and
thresholds (``data-value``, ``data-critical``, ...). The first phase below
uses only this.


Requirements
------------

* Ask an assistant about a metric, a view, or the whole analysis, from the
  report, with the values and definitions included automatically.
* The analyst chooses which assistant receives the data and sees what is
  sent: traces and metrics of customers may not be sent to every service.
* No API key in the report: the report is a file that is shared.
* The single-file report keeps working without any backend.
* One set of functions (analyze, read metrics, explain a metric, list the
  issues, run a Paraver cfg) for the report and for the MCP clients.
* Long analyses (traces of GB, Dimemas simulations) must not block a
  conversation: start, then poll.
* The answers must cite the metrics and definitions they use, so the analyst
  can check them.


Options considered
------------------

.. list-table::
   :header-rows: 1
   :widths: 24 34 18 24

   * - Option
     - How it works
     - Infrastructure
     - Decision
   * - A. *Ask AI* button: copy the question with its context
     - The report builds a text with the question, the values, and the
       definitions; the analyst pastes it into any assistant
     - None
     - **Phase 1**
   * - B. The report calls an AI service from the browser
     - A chat panel sends the data to the service directly
     - API key inside the report
     - **Rejected**: the key leaks with the file and every viewer spends it
   * - C. Chat panel in the report through the local backend
     - The panel talks to the Level 3 helper, which holds the key, calls the
       service, and lets the assistant use BasicAnalysis functions
     - Local backend
     - **Phase 3**
   * - D. MCP server
     - The analyst works in an MCP client, which uses BasicAnalysis
       functions
     - MCP server (Python)
     - **Phase 2**


Phase 1: *Ask AI* in the report
-------------------------------

Where
~~~~~

* **Metric Details**: *Ask AI about this metric*. The context is the metric,
  its value in every trace, its parent and children in the tree, and their
  definitions.
* **Each analysis view** (next to the export menu): *Ask AI about this
  view*. The context is the tables of the view.
* **Execution Overview**: *Ask AI about the analysis*. The context is the
  configurations, the scaling model, and the metrics below the thresholds,
  with their definitions.

What it does
~~~~~~~~~~~~

The button opens a small dialog with:

* a question field, prefilled with a suggested question (for example "Why
  is *Device Orchestration Efficiency* low in the 8 × 1 GPU run, and what
  should I look at next?"), which the analyst can change;
* the full text that will be copied, shown read-only and collapsed, so the
  analyst sees exactly what is shared;
* **Copy** (to the clipboard) and **Download** (``.md`` file).

The analyst pastes it into the assistant of their choice: a hosted service
or a model run at BSC. Nothing leaves the browser by itself.

Content of the text
~~~~~~~~~~~~~~~~~~~

Markdown, in this order, so that any assistant can read it:

#. **Instructions to the assistant**: you are helping a performance analyst
   interpret POP efficiency metrics computed by BasicAnalysis from Paraver
   traces; use the definitions below; cite the metric names and values you
   rely on; say when the data is not enough to conclude; suggest the
   Paraver views or BasicAnalysis views to inspect; values are percentages,
   relative to the first trace for the scalability metrics.
#. **Execution**: programming model, trace mode, configurations
   (``4 × 1 GPU``...), scaling model per level and its ratios, thresholds of
   the view (including custom ones from the slider).
#. **Metrics**: a table of the relevant metrics (name, tree level, value per
   trace, Critical/Attention/Good), with the workload marks.
#. **Definitions**: for each metric in the table, definition, formula,
   interpretation of the observed range, possible causes, and next steps,
   from the embedded Metric Details.
#. **Question** of the analyst.

Trace file names and paths are left out by default; a check box adds them.
The text is kept below a size that fits the common assistants (the whole
analysis with all definitions is about 20–40 KB).

What is not included
~~~~~~~~~~~~~~~~~~~~

Raw trace data, timelines, and Paraver views are not sent. When the
assessment of ``doc/design/assessment.rst`` exists, the analyst's notes
of the current metric could be added on request.


Phase 2: BasicAnalysis functions and the MCP server
---------------------------------------------------

Functions
~~~~~~~~~

One Python module (for example ``basicanalysis_api.py``) with functions
that use the existing pipeline and return data, not HTML. The MCP server
and the backend of Phase 3 are thin layers over it.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Function
     - Purpose
   * - ``analyze(traces, options)``
     - Start an analysis (``modelfactors.py`` options: workload, scaling,
       simulation...) in a project folder; returns a job id
   * - ``status(job)``
     - State of the job (queued, running, done, failed) and the log so far
   * - ``list_runs(folder)``
     - Analyses available in a folder (reports, ``*.rawdata.json``, merged
       files)
   * - ``get_metrics(run, view)``
     - Metric values of a view (Runtime Model, Heterogeneous Model, I/O,
       Scaling) per trace, with thresholds and workload marks
   * - ``list_issues(run, thresholds)``
     - Metrics below the thresholds, ordered by tree level and value: the
       starting point of the diagnosis
   * - ``explain_metric(key, value)``
     - Definition, formula, interpretation for that value, causes, next steps
       (from ``definitions.yaml``)
   * - ``compare_runs(run_a, run_b)``
     - Differences between two analyses of the same application
   * - ``run_paramedir(trace, cfg)``
     - Run a Paraver cfg in batch and return the table (Level 3)
   * - ``simulate(trace, network)``
     - Dimemas simulation with other latency and bandwidth (Level 3)

The results of ``get_metrics`` and ``list_issues`` are the same data model
as the report data model of ``doc/design/assessment.rst`` (and of the Level
3 analysis); this module is where that model is defined.

MCP server
~~~~~~~~~~

* A small program (``basicanalysis_mcp.py``) using the official MCP Python
  SDK, an optional dependency like the plotting packages.
* It exposes the functions above as MCP *tools*, and ``definitions.yaml`` and
  the User Guide chapters as MCP *resources*, so the assistant can read the
  methodology.
* Transports: *stdio* when the client runs on the same machine as the traces
  (Claude Code on a login node, for example), and HTTP with authentication
  when the server runs on a cluster and the client elsewhere.
* Long jobs use ``analyze`` + ``status``; on clusters, ``analyze`` can submit
  the staged workflow as Slurm jobs.

Safety
~~~~~~

* The server runs only BasicAnalysis, paramedir, and Dimemas, with
  validated arguments, never a shell or arbitrary command.
* Paths are limited to the folders configured at start.
* Functions that only read (``get_metrics``, ``explain_metric``, ...) are
  separated from those that run tools, so a client can be allowed only to
  read.
* Each run of a tool is logged (command line, as the run log does today).


Phase 3: chat panel in the report
---------------------------------

When the report is served by the Level 3 backend (``basicanalysis serve``,
growing from ``doc/design/paraver_launcher.rst``), the *Ask AI* dialog
becomes a chat panel:

* the backend holds the API key or the address of the BSC model; the report
  never sees it;
* the assistant receives the same context as in Phase 1, and can call the
  functions of Phase 2 (for example, run the Paraver cfg of a metric and
  read its table);
* answers that cite metrics link to them in the report (open Metric
  Details), and the analyst can add an answer to the assessment as a note.

Without the backend, the report keeps the Phase 1 dialog.


Data and privacy
----------------

* Phase 1 sends nothing by itself: the analyst copies the text and chooses
  the assistant.
* Phases 2 and 3 send metrics and, through the functions, data computed from
  traces to the AI service chosen when the server or backend is configured.
  Which services may receive data of POP customers (hosted, at BSC, both) is
  a decision of the group, and the configuration must make it explicit.
* Trace names and paths are optional in the context; they may contain
  customer or user names.


Evaluation
----------

Before Phase 2, test Phase 1 with the reports we know:

* questions on CloverLeaf MPI+CUDA (low Host and Device Offload), vLLM
  (``--device-workload``), BT-MZ MPI+OpenMP (Inner level), laplace MPI;
* the GROMACS assessment (``POP3_AR_074``) as reference: do the answers
  point to the same issues and Paraver views as the analyst?
* with at least one hosted assistant and one model run at BSC, if
  available;
* record whether the answers use the definitions given, cite values, and
  admit uncertainty; adjust the instructions of the context accordingly.


Scope of each phase
-------------------

1. *Ask AI* dialog in Metric Details, views, and Execution Overview; context
   built in the browser from the embedded data; Copy and Download; tests of
   the context text; evaluation above; User Guide.
2. ``basicanalysis_api.py`` (data model shared with the assessment and
   Level 3), MCP server with stdio, read-only functions first, then
   ``analyze``/``status``; HTTP transport and Slurm submission for clusters.
3. Chat panel in the report served by the Level 3 backend.


Open questions
--------------

1. Which AI services may receive metrics of customer traces: hosted
   services, a model run at BSC, or both? (Phases 2 and 3.)
2. Who holds and pays the API keys: each analyst, or a BSC service?
3. Where does the MCP server run for traces on the clusters: login node,
   a job, Open OnDemand?
4. Should Phase 1 offer the context in English only, or in the language of
   the question?
5. Should *Ask AI* include the analyst's notes of the assessment when they
   exist?
6. Is a public MCP server for BasicAnalysis users outside BSC in scope, or
   only for POP analysts?
