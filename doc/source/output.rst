Output
======

BasicAnalysis generates several complementary outputs from the analyzed
Paraver traces. These include numerical results, static visualizations, an
interactive performance report, and intermediate data produced during the
analysis.

The exact files generated depend on the programming model, the available
performance data, the number of analyzed traces, and the selected analysis
options.


Performance Report
------------------

The main output of BasicAnalysis is the interactive performance report:

.. code-block:: text

   basicanalysis_interactive_report.html

The report provides a guided view of the performance analysis, including the
execution configuration, general performance metrics, hierarchical efficiency
analysis, runtime-specific analysis, and execution-domain analysis for
accelerator applications. When multiple execution configurations are analyzed,
the report also includes scaling information and performance trends.

Efficiency tables can be exported from the report as PNG images. The report
also provides export options for multiple tables and can be printed or saved as
a PDF using the browser.

See :doc:`performance_report` for a detailed description of the report,
its analytical views, and its export capabilities.


Numerical Output
----------------

BasicAnalysis writes the numerical results of the analysis to CSV files in the
output directory.

The main files include:

``rawdata.csv``
   Contains the aggregated performance measurements extracted from the input
   traces and used to compute the performance metrics.

``other_metrics.csv``
   Contains general performance quantities such as elapsed time, Speedup,
   Efficiency, IPC, frequency, and I/O-related metrics when available.

``modelfactors.csv``
   Contains the hierarchical efficiency and scalability factors computed by
   BasicAnalysis.

``efficiency_table*.csv``
   Contains the efficiency metrics arranged in the format used to generate the
   static efficiency tables. The exact filename depends on the performance
   model being analyzed.

Additional model-specific CSV files may also be generated. For example,
OpenMP analyses can generate ``omp_talp_metrics.csv``, while accelerator
analyses using the Host/Device performance model can generate
``talp_metrics.csv``.

The availability of individual metrics depends on the programming model,
the information contained in the traces, and the selected analysis options.


Static Visualizations
---------------------

BasicAnalysis generates static visualizations of the performance metrics when
the required Python plotting dependencies are available.

Efficiency tables are generated as both PNG and PDF files. Depending on the
performance model, the output includes files such as:

.. code-block:: text

   efficiency_table-matplot.png
   efficiency_table-matplot.pdf

or the corresponding global, hybrid, or Host/Device variants.

When multiple execution configurations are analyzed, BasicAnalysis also
generates plots showing the evolution of the performance metrics across the
configurations. These include Speedup and Efficiency plots and, depending on
the performance model, plots for global efficiency, parallel efficiency,
communication efficiency, runtime-specific factors, and computation
scalability.

Some multi-configuration analyses also generate Gnuplot ``.gp`` files
containing plotting instructions and the corresponding metric data.


Intermediate Analysis Files
---------------------------

BasicAnalysis stores the intermediate data produced while analyzing each trace
under:

.. code-block:: text

   scratch_out_basicanalysis/

A separate subdirectory is created for each analyzed trace. These directories
contain the Paraver/paramedir statistics used to derive timing, hardware-counter,
I/O, runtime-specific, and accelerator measurements.

For accelerator traces, the intermediate data can also include Host, GPU-stream,
and memory-transfer statistics. OpenMP analyses include additional timing data
used to characterize serial execution, parallel-region load balance, and
scheduling and fork/join overhead.

When Dimemas simulation is applicable, Dimemas is available, and simulation
has not been disabled, the corresponding trace directory also contains the
simulation input, configuration, simulated trace, and paramedir statistics
obtained from the simulated execution.

These files are intermediate analysis data; the summarized measurements and
computed metrics are provided separately by the CSV files in the main output
directory.