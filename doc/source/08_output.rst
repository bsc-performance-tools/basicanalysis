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

The report provides a guided view of the performance analysis through the
Execution Overview, Parallel Runtime Model, Runtime-Specific Analysis,
Execution Domains, I/O Analysis, and Scaling views, as applicable to the
analyzed execution.

The available views depend on the programming model and performance data. For
example, Execution Domains are available for accelerator applications, while
I/O Analysis reports the File I/O metrics derived from MPI-I/O and POSIX/ANSI C
File I/O activity detected in the traces. When multiple execution
configurations are analyzed, the report also provides scaling information and
performance trends.

Metric values in the report are interactive. Selecting a metric opens its
definition, interpretation, and recommended next diagnostic steps.

Efficiency tables can be exported from the report as PNG images. The report
also provides export options for multiple tables and can be printed or saved as
a PDF using the browser.

See :doc:`07_performance_report` for a detailed description of the report,
its analytical views, and its export capabilities.


Numerical Output
----------------

BasicAnalysis writes the numerical results of the analysis to CSV files in the
output directory.

The main files include:

``rawdata.csv``
   Contains the aggregated performance measurements extracted or constructed
   from the input traces and used to compute the performance metrics. These
   include timing and hardware-counter measurements and, when applicable,
   runtime-specific, I/O, and accelerator-related quantities.

``other_metrics.csv``
   Contains complementary performance quantities such as elapsed time,
   Speedup, Efficiency, IPC, processor frequency, tracer flushing information,
   and I/O-related metrics when available.

``modelfactors.csv``
   Contains the application-level hierarchical efficiency and scalability
   factors computed by BasicAnalysis.

``efficiency_table*.csv``
   Contains efficiency metrics arranged in the format used to generate the
   corresponding static efficiency tables. The exact filename depends on the
   performance model being analyzed.

Additional model-specific CSV files may also be generated. For example,
OpenMP analyses can generate ``omp_talp_metrics.csv``, while MPI+GPU analyses
using the Host/Device execution-domain model can generate
``talp_metrics.csv``.

The availability of individual files and metrics depends on the programming
model, the information contained in the traces, the number of analyzed
execution configurations, and the selected analysis options.


Static Visualizations
---------------------

BasicAnalysis generates static visualizations of the performance metrics when
the required Python plotting dependencies are available.

Efficiency tables are generated as both PNG and PDF files. Depending on the
performance model, the output includes files such as:

.. code-block:: text

   efficiency_table-matplot.png
   efficiency_table-matplot.pdf

or the corresponding global, hybrid, runtime-specific, or Host/Device
variants.

When multiple execution configurations are analyzed, BasicAnalysis also
generates plots showing the evolution of performance metrics across the
configurations. These include Speedup and Efficiency plots and, depending on
the programming model and available data, plots for:

* Global Efficiency and Parallel Efficiency;
* Load Balance and Communication Efficiency;
* Computation Scalability and its available factors;
* runtime-specific efficiency factors; and
* Host and Device execution-domain metrics.

Some multi-configuration analyses also generate Gnuplot ``.gp`` files
containing plotting instructions and the corresponding metric data.

I/O metric plots are provided within the interactive report and are not
generated as separate static visualization files.


Intermediate Analysis Files
---------------------------

BasicAnalysis stores the intermediate data produced while analyzing each trace
under:

.. code-block:: text

   scratch_out_basicanalysis/

A separate subdirectory is created for each analyzed trace. These directories
contain the Paraver/paramedir statistics used to derive timing,
hardware-counter, I/O, runtime-specific, and accelerator measurements.

For accelerator traces, the intermediate data can also include Host,
GPU-stream, and memory-transfer statistics. GPU stream activity is subsequently
mapped and flattened to physical devices when constructing the Device
measurements used by the performance metrics.

OpenMP analyses include additional timing data used to characterize serial
execution, parallel-region load balance, and scheduling and fork/join
overhead.

When Dimemas simulation is applicable, Dimemas is available, and simulation
has not been disabled, the corresponding trace directory also contains the
simulation input, configuration, simulated trace, and paramedir statistics
obtained from the simulated execution.

These files represent intermediate analysis data. The summarized measurements
and computed metrics intended for direct inspection are provided separately by
the CSV files in the main output directory.