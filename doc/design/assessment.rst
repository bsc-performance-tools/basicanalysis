Analyst Assessments in the Interactive Report
=============================================

:Status: Design; clipboard evaluation done, POP template mapped, not implemented
:Date: 2026-11-10
:Branch: ``feature/assessment``
:Scope: Interactive report, all trace sources and programming models.

The interactive report should let a performance analyst write an assessment
inside the report: paste Paraver views, comment on them, link them to the
metrics they explain, organize the sections, and export the result.


Context
-------

The team has set three levels for BasicAnalysis:

.. list-table::
   :header-rows: 1
   :widths: 6 34 30 30

   * - Level
     - Functionality
     - Main requirement
     - Current report
   * - 1
     - Interactive reporting: views, plots, metric explanations, filtering,
       comparisons
     - Browser-based interaction
     - Done
   * - 2
     - Personalized assessments: insert Paraver views, write observations,
       annotate findings, organize sections, export reports
     - Editable and persistent report
     - This document
   * - 3
     - Tool integration: execute Paraver configurations, run Dimemas
       simulations, retrieve results, update analyses
     - Backend that runs external tools
     - Not possible in a static page; see
       ``doc/design/paraver_launcher.rst`` (branch
       ``feature/paraver-launcher``)

Level 2 does not need a backend. This document keeps it inside the
single-file report, and defines the assessment so that a future Level 3
backend reads and writes the same files.

Reference case
~~~~~~~~~~~~~~

The POP assessment ``POP3_AR_074_GROMACS.pdf`` (36 slides) shows how an
analyst works:

* Most slides pair a table or a set of Paraver views with two to four
  bullet comments.
* The efficiency tables (slides 13, 15, 19, 20) are followed by Paraver
  views that explain the low metrics (slides 24 to 31).
* Views are often grouped: three histograms labelled 1N, 2N and 4N side by
  side, with one shared caption ("first 48 threads, 5 to 5000 µs").
* The sections follow a fixed path: background, application structure,
  scalability, efficiency metrics, deeper analysis, experiments, summary.
* 64 of the images are 600 × 132 pixels: Paraver views copied with the
  clipboard.


Requirements
------------

* Paste a Paraver view with Ctrl+V, and drop an image file, into the report.
* Group images with a label each and a shared caption, and write comments.
* Link a comment or an image to a metric, a trace, and a report view.
* Organize the assessment in sections that the analyst names and orders.
* Insert BasicAnalysis tables and plots as live elements, not screenshots.
* Keep the work across sessions, and share it as one file.
* Keep the assessment when the report is regenerated with new traces.
* Export to PDF and to slides.
* No new installation step; the report still works by double-clicking it.
* An assessment received from someone else must not run code in the browser.


Evaluation
----------

Tested on 2026-11-10 on Linux (X11) with wxparaver 4.12.0-devel and a test
page that lists the clipboard content of a paste event.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Test
     - Result
   * - Copy a Paraver timeline, paste in Chrome
     - One ``image/png`` file, 600 × 133 pixels, 6999 bytes
   * - Same in Firefox 158 (snap package)
     - Same result
   * - Test page under ``/tmp``, opened in Firefox (snap)
     - File not found: snap applications have a private ``/tmp``. Reports
       in the home directory or the project folders open normally

The image arrives as a standard PNG, with no conversion. At about 7 KB per
view, an assessment with the 300 images of the GROMACS deck adds a few MB.


Options considered for persistence
----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Option
     - Limitation
     - Decision
   * - ``localStorage``
     - About 5 MB, one browser and machine, can be cleared at any time
     - Rejected; kept only for small view settings, as today
   * - IndexedDB
     - Larger, but still one browser and machine
     - **Chosen for the draft** only, saved automatically
   * - Save a copy of the report with the assessment embedded
     - A new file at each save (browser download)
     - **Chosen**: one file to open, send, and archive
   * - Assessment file (``.json``) exported and imported
     - A second file to manage
     - **Chosen** to move an assessment to a regenerated report
   * - File System Access API, save in place
     - Chromium only
     - Optional later, on top of the download
   * - Server (Jupyter, Dash, custom)
     - Installation, process to keep running
     - Level 3; not needed here


Proposed design
---------------

Assessment view
~~~~~~~~~~~~~~~

A new *Assessment* view in the main navigation, after the analysis views.
It is empty until the analyst starts an assessment, either blank or from a
template. The first template is the POP assessment template (next
section): it creates the sections, shows the guidance of each one, and
fills in what BasicAnalysis knows, so that the analyst starts by
commenting.

The analyst can:

* add, rename, reorder (drag or up/down buttons), and delete sections;
* add blocks to a section: text, image group, or BasicAnalysis element;
* paste (Ctrl+V) or drop images into an image group, or into a section,
  which creates a new group;
* write a label for each image and a caption for the group;
* switch between *Edit* and *Read* mode; Read mode is what is exported.

POP assessment template
~~~~~~~~~~~~~~~~~~~~~~~

Source: ``POP3_Assessment_template_detailed.pptx`` (12 slides, 16:9). Each
content slide has the expected content (*Include*) and its purpose (*Why is
important?*). The assessment keeps that text as guidance: shown in Edit
mode, never exported.

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Template slide
     - Assessment
     - Filled in by BasicAnalysis
   * - 1. Title
     - Fields: report number (``POP3_AR_XXX``), code name, analyst name,
       email, organisation
     - Date
   * - 2. Background
     - Fields: customer and organisation, code and version, input,
       programming language, software environment (compiler, MPI version,
       libraries), hardware platform, EuroHPC system acknowledgment
     - Programming model (detected), processes, threads, and GPUs per trace,
       nodes and tasks per node, trace names and dates. The analyst
       confirms or edits them
   * - 3. Structure
     - Image groups (timeline of the whole execution: Useful Duration or MPI
       calls), checklist from the guidance (initialization, iterative
       phase, all processes equal, granularity, processes or GPUs per node,
       communication and offloading phases), and the *Focus of Analysis*
       field
     - Execution Overview table
   * - 4. Scalability
     - Image groups (timelines of the scaling traces with the same duration
       or one iteration) and comments
     - Scaling plots (speedup and efficiency) when there are several traces
   * - 5. Efficiency metrics
     - Comments on the main issues
     - Runtime model table (Hybrid Model or Parallel Runtime Model) and the
       Heterogeneous Model table when present. A list of the metrics below
       the thresholds of the report, which the analyst confirms as issues
   * - 6. Detailed analysis based on eff. metrics
     - One subsection per confirmed issue, with its evidence (images and
       comments)
     - The subsections, from the confirmed issues and from *Add evidence*.
       The possible causes and next steps of Metric Details as guidance
   * - 7. Conclusions and suggestions
     - Comments: summary of findings, hints to address the main issues
     - Nothing inserted: the conclusions are the analyst's. The list of
       issues and their evidence is shown as a reminder
   * - 8. We need your help
     - No content to write
     - Fixed text with the report number, added at export
   * - 9–11. Internal use only: co-design feedback for tools and for
       resources
     - Sections marked *internal*: not in the customer export, included in
       the internal export
     - Nothing
   * - 12. Closing slide
     - No content to write
     - Fixed slide, added at export

The template is a data file (for example
``assessment_templates/pop3.json``) with the sections, their guidance, the
fields, the elements to insert, and the *internal* flag. Other templates
(outside POP, or a future POP version) are new files, not code changes.

Add evidence from Metric Details
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Metric Details gets an *Add evidence* button. It opens a small panel where
the analyst pastes images and writes a comment. The block is added to the
*Deeper analysis* section (created if missing), linked to the metric and to
the trace of the selected cell. The interpretation and the possible next
steps of the metric are shown in the panel as a guide.

Metric cells that have evidence show a small mark, and Metric Details lists
the evidence blocks with a link to each one. This is the path from a low
metric to its explanation that the GROMACS deck follows by hand.

Assessment format
~~~~~~~~~~~~~~~~~

One JSON document, independent of the report HTML::

    {
      "format": "basicanalysis-assessment",
      "version": 1,
      "title": "Performance assessment of GROMACS",
      "template": "pop3",
      "fields": {"report_number": "POP3_AR_074", "code": "GROMACS",
                 "analyst": "", "email": "", "organisation": "",
                 "focus_of_analysis": "..."},
      "created": "2026-11-10T15:00:00Z",
      "modified": "2026-11-10T16:30:00Z",
      "report": {"basicanalysis_version": "...",
                 "traces": ["GROMACS-1N.prv", "GROMACS-2N.prv"]},
      "sections": [
        {"id": "s1", "title": "Efficiency metrics", "internal": false,
         "blocks": [
          {"id": "b1", "type": "element",
           "view": "parallel-runtime-model", "element": "efficiency-table",
           "snapshot": {"parallel_eff": [68.10, 58.63, 43.32]}},
          {"id": "b2", "type": "text",
           "text": "Parallel efficiency is the most problematic...",
           "links": [{"metric": "parallel_eff", "trace": "GROMACS-4N.prv"}]},
          {"id": "b3", "type": "images",
           "images": [{"image": "i1", "label": "1N"},
                      {"image": "i2", "label": "2N"}],
           "caption": "Useful Duration histogram, first 48 threads",
           "links": [{"metric": "load_balance"}]}
        ]}
      ],
      "images": {"i1": {"type": "image/png", "width": 600, "height": 133,
                        "data": "<base64>"}}
    }

* Images are stored once in ``images`` and referenced by ID, so moving a
  block does not copy them.
* Links use the metric keys of the report (the keys already used by Metric
  Details), the trace file name, and the view ID (``data-guided-view-id``).
  Trace names, not indices, so they survive a regenerated report with a
  different trace order.
* An element block stores a ``snapshot`` of the values shown when it was
  inserted. When the report data differs, the element shows the current
  values and a note that they changed since the assessment was written.
* ``version`` lets later releases read older assessments.

Text
~~~~

Plain text, with lines starting with ``-`` shown as bullets and blank lines
as paragraphs. A rich-text editor is not proposed for the first version:
it brings HTML into the assessment, which is a risk when the file comes
from someone else, and the GROMACS deck uses only bullets.

Saving
~~~~~~

* **Draft**: saved automatically in IndexedDB at each change, keyed by the
  report path (the same key the threshold changes use in
  ``localStorage``). When the report opens
  and a draft is newer than the embedded assessment, the report asks which
  one to use.
* **Save assessment**: downloads a copy of the report with the assessment
  embedded in ``<script type="application/json" id="ba-assessment">``. The
  file name is the report name plus the assessment title and the date. This
  file is the deliverable.
* **Export assessment (.json)** and **Import assessment**: move an
  assessment to a report regenerated with more traces, or merge the work of
  two analysts section by section. References that the new report cannot
  resolve (a trace or a metric missing) are marked, never dropped.
* Leaving the page with unsaved changes shows the browser warning.

``modelfactors.py`` gets ``--assessment FILE.json`` to embed an existing
assessment in the generated report, so that the staged workflow can
regenerate the report without the manual import.

Export
~~~~~~

* **Print / Save as PDF**: the printable report gets the assessment
  sections, in Read mode, before the analysis appendices. ``html_to_pdf.py``
  works unchanged.
* **Slides (PPTX)**: one slide per block group, following the GROMACS
  layout (images on the left, bullets on the right, caption below). Two
  ways were considered:

  a. In the browser with PptxGenJS, loaded from a CDN like Plotly: no
     installation, but the export needs network access, and the slides
     would imitate the template instead of using it.
  b. ``assessment_to_pptx.py`` with ``python-pptx``, reading the saved
     report or the ``.json``, and filling the layouts of the template file
     itself (*Title Slide*, *Title and Content*, *Title Only*, *Section
     Header*, *Blank*). ``python-pptx`` is an optional dependency, like the
     plotting packages.

  **Proposed: (b)**, because the deliverable must be the POP template, and
  any change to the template is picked up without code changes. The
  template file is given with ``--template``. BasicAnalysis tables are
  exported as images; Paraver views are inserted as pasted.
* **Customer and internal exports**: the customer export leaves out the
  sections marked *internal*; the internal export includes them.

Security
~~~~~~~~

An assessment can come from another person, so it is treated as untrusted
data:

* Text is inserted with ``textContent``, never as HTML.
* Images are accepted only as PNG, JPEG, or WebP data, checked by type and
  decoded before use; SVG is rejected because it can contain scripts.
* A size limit per image (5 MB) and a warning above 50 MB in total.
* The embedded JSON is read with ``JSON.parse``, and ``</`` is escaped when
  writing it into the HTML, as the report already does for the scaling
  notes.
* Unknown block types and fields are kept but not rendered.


Relation to Level 3
-------------------

* The Level 3 backend (``doc/design/paraver_launcher.rst``) stores the same
  assessment file in the project folder instead of downloading it.
* An image block can later keep the trace, the cfg, and the time range of
  the Paraver view, so that the image reopens the view in Paraver. With the
  clipboard, only the image is available: the window title in the image
  names the view and the trace, and the analyst can add the rest in the
  caption.
* Several analysts editing at the same time needs a server; it is out of
  scope here.


Scope of each phase
-------------------

1. Assessment format and view: sections, text blocks, image groups with
   paste and drop, Edit and Read modes, draft in IndexedDB, Save assessment,
   export and import of the ``.json``. Tests of the embedding, the escaping,
   and the rejection of invalid images. Manual test following the GROMACS
   deck with one of our traces.
2. *Add evidence* from Metric Details, the links, the marks on metric
   cells, BasicAnalysis elements with snapshots, the POP template (fields,
   guidance, prefilled values, issue list, internal sections), and
   ``--assessment``.
3. Printable report and PDF; PPTX export with the POP template, customer
   and internal versions.
4. User Guide (report and output chapters), release notes, screenshots.


Open questions
--------------

1. Slide export with ``python-pptx`` and the template file (b): agreed?
   Can the POP template be distributed with BasicAnalysis, or must the
   analyst give its path?
2. Is plain text with bullets enough, or do analysts need bold, links, or
   formulas in comments?
3. Which other templates are needed besides POP (for example for internal
   BSC analyses or training)?
4. Should *Save assessment* also offer the ``.json`` by default, so that
   the analyst always has the file needed for a regenerated report?
5. Merging two analysts' assessments: by section, or block by block?
6. Can Paraver add the trace, cfg, and time range to the clipboard, for
   example as text next to the image? This would let Level 3 reopen the
   view. Question for the Paraver team.
7. Should images from other tools (Nsight Systems, Vampir, profilers) be
   labelled with their source?
