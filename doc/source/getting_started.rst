.. _cha:getting-started:

Getting Started
###############

This chapter describes the basic requirements for running **BasicAnalysis**
and shows how to perform a first analysis from a set of Paraver traces.

For a complete description of the command-line options and execution modes,
see :doc:`running_basicanalysis`.


Requirements
============

BasicAnalysis requires Python 3 and relies on tools from the BSC Performance
Tools ecosystem to extract performance information and, when required,
simulate idealized executions.

The main external requirements are:

* **Paraver / paramedir**, used to extract performance data from Paraver traces.
* **Dimemas**, used when simulation is required to compute communication
  efficiency submetrics such as Serialization Efficiency and Transfer
  Efficiency.

The tools are available from:

* Paraver: https://tools.bsc.es/paraver
* Dimemas: https://tools.bsc.es/dimemas

The corresponding executables must be available through the ``PATH``
environment variable. A typical configuration is:

.. code-block:: sh

   export PATH=<paraver-install-dir>/bin:$PATH
   export PARAVER_HOME=<paraver-install-dir>

   export PATH=<dimemas-install-dir>/bin:$PATH
   export DIMEMAS_HOME=<dimemas-install-dir>


Python dependencies
===================

BasicAnalysis requires Python 3.

Additional Python packages are used for data processing, plotting, and report
generation. The required packages and their installation are described with
the BasicAnalysis distribution.

Some output functionality may depend on optional external tools. In
particular, generation of the printable PDF performance report requires a
supported Chromium-compatible browser.


PDF report export
-----------------

BasicAnalysis generates an interactive HTML performance report as part of the
analysis results.

A printable PDF version of the report can be generated on demand using the
**Export** function available in the interactive report. PDF generation is not
performed automatically during a BasicAnalysis execution.

The PDF export requires a supported Chromium-compatible browser to be
available on the system, such as:

* ``chromium``
* ``chromium-browser``
* ``google-chrome``
* ``google-chrome-stable``

This separation allows BasicAnalysis to run on HPC systems where a compatible
browser may not be installed. The interactive HTML report and the remaining
analysis outputs are generated independently of PDF export.


Installation
============

BasicAnalysis does not require a separate installation procedure.

Clone or copy the BasicAnalysis repository to the desired location. The
directory containing the BasicAnalysis executable scripts can optionally be
added to ``PATH``:

.. code-block:: sh

   export PATH=<basicanalysis-dir>:$PATH


Running a first analysis
========================

The standard BasicAnalysis workflow analyzes one or more Paraver traces.
The tool accepts both uncompressed ``.prv`` traces and compressed ``.prv.gz`` 
traces and computes the corresponding efficiency metrics and other 
performance indicators, tables, plots, and reports.

BasicAnalysis can be executed with:

.. code-block:: sh

   modelfactors.py [options] <list-of-traces>

The trace list can contain explicit trace filenames, multiple traces, or
wildcard expressions. Only valid Paraver traces are retained for analysis.

For example:

.. code-block:: sh

   modelfactors.py application.prv

Compressed trace:

.. code-block:: sh

   modelfactors.py application.prv.gz


Several execution configurations can be analyzed together:

.. code-block:: sh

   modelfactors.py trace_1.prv trace_2.prv trace_3.prv

Wildcards can also be used:

.. code-block:: sh

   modelfactors.py *.prv

When several traces are analyzed, BasicAnalysis can compare their performance
and evaluate how the efficiency factors evolve across the execution
configurations.


Analysis results
================

A standard BasicAnalysis execution can produce:

* raw performance data;
* efficiency and model-factor tables;
* CSV files;
* performance and scalability plots; and
* an interactive HTML performance report.

The performance report organizes the analysis into complementary views such
as Execution Overview, Parallel Runtime Model, Runtime-Specific Analysis, 
Execution Domains when applicable, and Scaling when several configurations 
are available.

A printable PDF version of the performance report can be generated on demand
from the **Export** function of the interactive report.

A detailed description of the generated files is provided in :doc:`output`.


Next steps
==========

After completing a first analysis:

* See :doc:`running_basicanalysis` for the available execution options and
  analysis configuration.
* See :doc:`staged_workflow` when traces should be analyzed independently and
  merged before computing the final metrics.
* See :doc:`methodology` to understand the BasicAnalysis performance-analysis
  methodology.
* See :doc:`performance_report` for guidance on reading the generated
  performance report.
* See :doc:`metrics` for the definitions of the efficiency metrics.