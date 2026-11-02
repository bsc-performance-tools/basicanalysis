Opening Paraver Views from the Interactive Report
=================================================

:Status: Design; evaluation done, not implemented
:Date: 2026-11-02
:Branch: ``feature/paraver-launcher``
:Scope: Interactive report, all trace sources. The set of Paraver
        configurations (cfgs) for each metric is a separate work item.

The metric details of the interactive report should let the user open the
Paraver view where a performance issue can be observed, with one click and
without adding installation steps.


Context
-------

The report is one HTML file with embedded plots. It can be emailed, printed,
and opened on any machine. A page in a browser cannot run a local program,
and there is no permission that it can request to do so, so one-click launching
needs something outside the page.

The report has a *Copy Paraver command* button for the Useful Duration view
(``interactiveplots._build_resources_table_html``). Colleagues did not like
having to paste a command in a terminal, so it is not the solution.


Requirements
------------

* One click from the metric details to the Paraver view.
* No new dependencies or installation steps: Python, already required by
  BasicAnalysis, and ``wxparaver``.
* The report stays a single file that also works without the helper.
* A web page must not be able to run anything else through the helper.


Options considered
------------------

.. list-table::
   :header-rows: 1
   :widths: 34 26 40

   * - Option
     - Installation
     - Decision
   * - Local helper, Python standard library
     - None
     - **Chosen**
   * - Copy the command
     - None
     - Rejected by colleagues; not one click
   * - ``paraver://`` link
     - Handler registered on each machine and OS
     - Rejected: installation step, browser prompt
   * - Browser extension
     - One per browser
     - Rejected: installation step
   * - Desktop application (Qt, Electron, pywebview)
     - Heavy, especially on clusters
     - Rejected: loses the single-file report
   * - Dash, Streamlit, Jupyter
     - New dependencies
     - Rejected: also a local server, with more to install


Evaluation
----------

Tested on 2026-11-02 with wxparaver 4.12.0-devel on Linux, trace
``bt-mz_A-8px4th.prv``, and ``single_instance`` set to 1 in
``~/.paraver/paraver.xml``.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Test
     - Result
   * - ``wxparaver trace.prv view.cfg``, no Paraver open
     - Opens Paraver with the view
   * - Same command with Paraver open
     - Adds the view to the open Paraver; the command exits with 0 and one
       process remains
   * - Zoom with ``window_begin_time_relative`` and
       ``window_end_time_relative`` in the cfg
     - Works: the legend of the zoomed view lacks the calls outside the range
   * - ``~/paraload.sig`` and ``SIGUSR1``, no image line
     - Loads the view; the zoom was not checked. Linux only
   * - ``~/paraload.sig`` and ``SIGUSR1``, with an image line
     - A wxWidgets assertion dialog (``invalid bitmap``) blocks Paraver until
       someone clicks (2 of 2 runs)
   * - ``wxparaver -i trace.prv view.cfg``
     - Saved only the legend strip, not the timeline
   * - ``wxparaver`` without ``DISPLAY``
     - Exits with 255: ``Unable to initialize GTK+``
   * - Prototype helper (39 lines) driven with ``curl``
     - Opened two views in one Paraver; rejected a missing token, a foreign
       ``Origin``, and an unknown view

The conclusion is to launch with the plain command and to put the zoom in the
generated cfg. The signal interface is not needed.


Proposed design
---------------

BasicAnalysis writes a small script next to the report, for example
``open_report.py``, using only the Python standard library. The user runs it
once; it opens the report in the browser from ``http://127.0.0.1``.

Every *Open in Paraver* button in the metric details then requests one view.
When the report is opened as a plain file, the buttons cannot launch Paraver
and tell the user to start the helper. All the other content works as today.

View list
~~~~~~~~~

The helper reads a list written by BasicAnalysis, with paths relative to the
report folder::

    {"views": {"<view id>": {"trace": "<path>.prv", "cfg": "<path>.cfg"}}}

The report holds only view IDs, so it has no local paths.

Requests
~~~~~~~~

``POST /open`` with ``{"view": "<view id>"}`` runs::

    subprocess.Popen(["wxparaver", trace, cfg])

Security
~~~~~~~~

* Listens only on ``127.0.0.1``, on a free port chosen by the system.
* Requires a random token created at each start.
* Rejects a request whose ``Origin`` is not the helper itself.
* Accepts only IDs from the view list, never a path or a command.
* Runs ``wxparaver`` without a shell.
* Serves only the report and its files, not the whole folder.

Errors shown in the report
~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``wxparaver`` not in the ``PATH``.
* The trace or the cfg is not there, for example after moving the report.
* No display available, including over SSH without X forwarding.


Scope of each phase
-------------------

1. The helper, the view list, and the button with the existing Useful Duration
   view. Tests of the security checks and of the errors.
2. The set of cfgs for each metric, with the rules to select them. The trace
   and the metric decide the view, and the zoom points to the region of the
   issue. This is the larger part of the work.
3. User Guide (report and output chapters), release notes, screenshots.


Requirements for the cfg set
----------------------------

* A mapping from each metric to its view, per programming model. The current
  ``cfgs-report`` folder has 8 cfgs, which are not enough for every metric.
* Each cfg must work on any trace of its model, with its events present.
* Cfgs are generated per trace when they need a zoom, using the relative
  begin and end times.
* How BasicAnalysis finds the region of an issue is still to be defined.


Open questions
--------------

1. Does a real browser click behave like the ``curl`` tests?
2. Windows and macOS: is launching the same? The signal interface is Linux
   only, but it is not used here.
3. With ``single_instance`` set to 0, or if that is the default for new users,
   does each click open a new Paraver? Should the helper handle this?
4. X forwarding: is it usable with a remote helper, or should the guide
   recommend a remote desktop for traces on a cluster?
5. Reports moved to another machine: where should the helper look for the
   traces, and should it ask for the folder?
6. Should ``modelfactors.py`` have an option to open the report at the end?
7. For the Paraver team: should ``-i`` save the timeline as well as the legend,
   and is the ``invalid bitmap`` assertion known?
