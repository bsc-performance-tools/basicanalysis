.. _cha:staged-workflow:

Staged Analysis Workflow
########################

BasicAnalysis can separate trace processing from metric computation by using
a staged analysis workflow.

Instead of analyzing all traces and computing the final metrics in a single
``modelfactors.py`` execution, the analysis can be divided into three
independent stages:

#. **Trace analysis**: analyze each Paraver trace and generate a raw-data JSON
   file.
#. **Raw-data merge**: combine the per-trace raw-data files into a single
   merged dataset.
#. **Metric computation**: compute the efficiency metrics and other performance 
   indicators, tables, plots, and performance report.

The workflow can be summarized as:

.. graphviz::
   :align: center
   

   digraph BasicAnalysisWorkflow {
       rankdir=TB;

      graph [
         bgcolor="transparent",
         nodesep=0.20,
         ranksep=0.30
      ];

      node [
         fontname="Helvetica",
         fontsize=9,
         margin="0.10,0.06",
         style="filled",
         color="#6B7C8F",
         penwidth=1.0
      ];

      edge [
         color="#526477",
         penwidth=1.0,
         arrowsize=0.6
      ];

       traces [
           label="Paraver traces",
           shape=folder,
           fillcolor="#EAF2F8"
       ];

       analyze [
           label="analyze_traces.py",
           shape=box,
           fillcolor="#E8F5E9"
       ];

      raw1 [
         label="trace_1 rawdata JSON",
         shape=note,
         fillcolor="#F4F6F7"
      ];

      raw2 [
         label="trace_2 rawdata JSON",
         shape=note,
         fillcolor="#F4F6F7"
      ];

      rawn [
         label="trace_N rawdata JSON",
         shape=note,
         fillcolor="#F4F6F7"
      ];

       merge [
           label="merge_rawdata.py",
           shape=box,
           fillcolor="#E8F5E9"
       ];

       merged [
           label="merged_rawdata.json",
           shape=note,
           fillcolor="#F4F6F7"
       ];

       compute [
           label="compute_metrics_from_merged.py",
           shape=box,
           fillcolor="#E8F5E9"
       ];

       output [
           label="Metrics, plots and report",
           shape=folder,
           fillcolor="#FFF3E0"
       ];

       traces -> analyze;

         analyze -> raw1;
         analyze -> raw2;
         analyze -> rawn;

         raw1 -> merge;
         raw2 -> merge;
         rawn -> merge;

       merge -> merged;
       merged -> compute;
       compute -> output;
   }


This workflow is particularly useful when analyzing many or expensive traces.
If the analysis of one trace fails, the successfully generated raw-data files
can be preserved and only the failed trace needs to be analyzed again. The
resulting files can then be merged again without repeating the successful
trace analyses.

The staged workflow also separates the potentially expensive trace-processing
phase from metric computation, allowing the final metrics and reports to be
regenerated from previously extracted raw data.


Trace analysis
==============

The first stage is performed with ``analyze_traces.py``:

.. code-block:: sh

   analyze_traces.py [options] [trace_list ...]

The command accepts Paraver traces in both uncompressed ``.prv`` format and
compressed ``.prv.gz`` format.

For example:

.. code-block:: sh

   analyze_traces.py trace_1.prv trace_2.prv trace_3.prv

Compressed traces can be analyzed directly:

.. code-block:: sh

   analyze_traces.py trace_1.prv.gz trace_2.prv.gz

Wildcard expressions can also be used:

.. code-block:: sh

   analyze_traces.py *.prv

The trace-analysis stage performs the operations required to prepare the raw
performance information for each execution. Depending on the selected
analysis model, this includes:

* validating the input trace;
* detecting the programming model and trace mode;
* extracting performance data from the trace; and
* running the required Dimemas simulations when applicable.

Each successfully analyzed trace produces an independent raw-data JSON file.
These files contain the information required by the later metric-computation
stage, so the original trace does not need to be analyzed again when only the
final metrics or reports need to be regenerated.


Analysis configuration
----------------------

The trace-analysis stage supports the analysis options that affect raw-data
extraction, including the metric workflow, scaling selection, trace-mode
detection, simulation configuration, trace-size limit, and parallel trace
processing.

For example:

.. code-block:: sh

   analyze_traces.py --jobs auto *.prv

can analyze independent traces concurrently.

The main analysis options are described in :doc:`03_running_basicanalysis`.
The complete set of options supported by the installed version can be obtained
with:

.. code-block:: sh

   analyze_traces.py --help


Merging raw data
================

After the required traces have been analyzed, their raw-data JSON files can be
combined with ``merge_rawdata.py``:

.. code-block:: sh

   merge_rawdata.py --output merged_rawdata.json <rawdata-files>

For example:

.. code-block:: sh

   merge_rawdata.py --output merged_rawdata.json *.rawdata.json

The merge operation combines the independent trace-analysis results into a
single dataset that can be used for comparative and scalability analysis.

The merged file preserves the information required for metric computation,
including the analyzed trace set, trace metadata, raw performance data, and
parallel-configuration information.

Raw-data files do not need to have been generated in the same
``analyze_traces.py`` execution. This makes it possible to analyze traces
independently or to replace the raw data corresponding to a trace that needed
to be reanalyzed.

The available command-line options can be displayed with:

.. code-block:: sh

   merge_rawdata.py --help


Computing metrics from merged data
==================================

The final stage computes the performance metrics and generates the analysis
results from the merged raw-data file:

.. code-block:: sh

   compute_metrics_from_merged.py --merged-input merged_rawdata.json [options]

For example:

.. code-block:: sh

   compute_metrics_from_merged.py --merged-input merged_rawdata.json

This stage does not analyze the original Paraver traces. It consumes the
previously extracted raw data and computes the final efficiency metrics,
tables, plots, and interactive performance report.

This separation is useful when the metric configuration or report generation
needs to be repeated without rerunning the more expensive trace-analysis
stage.


Metric configuration
--------------------

Options that affect final metric computation can be specified at this stage.
These include the metric workflow, scaling model, trace ordering, and the
performance model used for MPI+GPU applications.

For example:

.. code-block:: sh

   compute_metrics_from_merged.py \
       --merged-input merged_rawdata.json \
       --scaling strong

or:

.. code-block:: sh

   compute_metrics_from_merged.py \
       --merged-input merged_rawdata.json \
       --pop_model_to_apply talp

The complete set of options can be displayed with:

.. code-block:: sh

   compute_metrics_from_merged.py --help


Reanalyzing failed traces
=========================

One of the main advantages of the staged workflow is that an unsuccessful
trace analysis does not require all traces to be processed again.

For example, suppose three traces are analyzed:

.. code-block:: sh

   analyze_traces.py trace_1.prv trace_2.prv trace_3.prv

and the analysis succeeds for ``trace_1`` and ``trace_3`` but fails for
``trace_2``.

After resolving the problem affecting ``trace_2``, only that trace needs to
be analyzed again:

.. code-block:: sh

   analyze_traces.py trace_2.prv

The available raw-data files can then be merged:

.. code-block:: sh

   merge_rawdata.py --output merged_rawdata.json *.rawdata.json

and the final metrics regenerated:

.. code-block:: sh

   compute_metrics_from_merged.py --merged-input merged_rawdata.json

The successful analyses of ``trace_1`` and ``trace_3`` therefore do not need
to be repeated.


Complete example
================

A complete staged analysis can be performed as follows.

First, analyze the traces:

.. code-block:: sh

   analyze_traces.py trace_1.prv trace_2.prv trace_3.prv

Second, merge the generated raw-data files:

.. code-block:: sh

   merge_rawdata.py --output merged_rawdata.json *.rawdata.json

Finally, compute the performance metrics and generate the reports:

.. code-block:: sh

   compute_metrics_from_merged.py --merged-input merged_rawdata.json

The resulting analysis follows the same performance-analysis methodology as
the standard BasicAnalysis workflow. The difference is that raw-data
extraction and final metric computation are performed as independent stages.


Choosing between the workflows
==============================

The standard workflow with ``modelfactors.py`` is convenient for direct
analysis when all traces can be processed in a single execution.

The staged workflow is preferable when:

* a large number of traces must be analyzed;
* individual trace analyses are expensive;
* traces are processed at different times or on different systems;
* failed traces need to be reanalyzed independently; or
* metrics and reports need to be regenerated without repeating trace
  processing.

Both workflows ultimately use the same BasicAnalysis metric models and
performance-analysis methodology.