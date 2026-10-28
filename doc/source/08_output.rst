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
Host/Device Model (TALP), I/O Analysis, and Scaling views, as applicable to the
analyzed execution.

The available views depend on the programming model and performance data. For
example, the Host/Device Model (TALP) view is available for accelerator
applications, while I/O Analysis reports I/O Efficiency and its Data Access
and File Management factors when POSIX, ANSI C, or MPI-IO calls are detected
in the traces. When multiple execution
configurations are analyzed, the report also provides scaling information and
performance trends.

Metric values in the report are interactive. Selecting a metric opens its
definition, interpretation, and recommended next diagnostic steps.

Efficiency tables can be exported from the report as PNG images. The report
also provides export options for multiple tables and can be printed or saved as
a PDF using the browser.

When the analyzed traces use different programming models, the report
contains a Programming Model Comparison tab and one tab per programming model
with the complete report of its traces.

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
   and I/O Efficiency with its Data Access and File Management factors.

``io_metrics.csv``
   Written when File I/O is detected. Contains I/O Efficiency, its factors,
   and the I/O diagnostics: time fractions, participation, contributions,
   load balance, the time, count, and mean duration of each group of I/O
   calls, the read and write volume, mean request size, and
   request-size coverage, the files accessed, maximum processes per
   file, volume moved by the main process of each file, and file-name
   coverage, and the volume in consecutive requests, volume re-accessed,
   and offset coverage of the reads and writes, and the share of redundant
   seeks.

``io_request_sizes.csv``
   Written when the traces have read or write requests. One row per
   execution, operation, API (POSIX/ANSI C or MPI-IO), and power-of-two
   request-size interval, with the number of requests, time, bytes, and
   their shares of the
   operation.

``io_files.csv``
   Written when the traces have POSIX or ANSI C calls. One row per
   execution and file accessed, in decreasing I/O time, with the processes,
   opens, I/O time, the requests, bytes, time, and processes of the reads
   and writes, the bytes of the main process and their share, the
   shares of the I/O time and of the bytes, and the access pattern of the
   reads and writes of the file (share of the requests and of the bytes of
   each class). The row *(descriptors without a
   traced open)* collects the calls on descriptors without an open in the
   trace.

``io_access_pattern.csv``
   Written when the traces have POSIX or ANSI C reads or writes to regular
   files. One row per execution, operation, and access-pattern class
   (first, consecutive, strided, forward, backward, unknown offset), with
   the number of requests, bytes, time, and their shares of the operation.

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
``talp_metrics.csv``. For *nsys2prv* traces with GPU metrics, BasicAnalysis
also writes ``device_hwc_metrics.csv`` with the GPU hardware counter metrics
(percentages, and the GPC clock in MHz) and adds the integrals of the
counters to ``rawdata.csv``.

For GPU traces, ``talp_metrics.csv`` also contains the Device Work and
Throughput Scalability (and, for *nsys2prv* traces with GPU metrics, the
Device Issue and Frequency Scalability) when two or more traces are analyzed
(see :ref:`device-work-throughput`). ``rawdata.csv`` adds the number of
kernels executed on the devices and the GPU threads launched, and, for
*nsys2prv* traces with GPU metrics, the integral of SM Issue multiplied by
the GPC clock. With two or more GPU traces, BasicAnalysis also writes:

``device_kernels.csv``
   One row per execution other than the reference and kernel (or kernel
   family), in decreasing change of the kernel time, with the work ratio of
   the scaling model, the share of the kernel in the change of the device
   time from the ideal, and the calls, time (us), and GPU threads launched of
   the kernel in the reference and in the execution (see
   :ref:`device-kernel-contributions`). The kernel column has the full name
   recorded in the trace.

When the analyzed traces use different programming models, BasicAnalysis
also writes:

``comparison_metrics.csv``
   Contains the comparison of the efficiency metrics of the traces, with the
   same rows as the comparison table printed on the terminal. Cells of
   metrics that do not apply to a programming model are empty. In this case,
   the reference-based metrics in ``modelfactors.csv`` and
   ``other_metrics.csv``, such as scalability metrics and Efficiency, are
   reported as ``N/A``.

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
variants. For the Host/Device model, ``efficiency_table_talp_matplot``
shows the Host and Device metrics together, and
``efficiency_table_talp_host_matplot`` and
``efficiency_table_talp_device_matplot`` show each execution domain on its
own, for example for presentations that focus on the host or on the device.
For *nsys2prv* traces with GPU metrics,
``efficiency_table_device_hwc_matplot`` shows SM Utilization and its
factors, and ``table_device_hwc_indicators_matplot`` shows the indicators
(GPU Active, Achieved Occupancy, Tensor Core Activity, DRAM Read and Write
Bandwidth and GPC Clock) with a single neutral colour, since they are not
efficiencies.

Each column of the static plots is labelled with its configuration and the
trace identifier used in the interactive report (``[T1]``, ``[T2]``, ...),
so that the same trace can be referenced in a paper or in slides, even when
several traces have the same configuration. Metrics without a value for
any trace (for example IPC, Instruction and Frequency scalability when the
traces have no hardware counters) are not shown in the static efficiency
tables; the CSV files keep all the metrics.

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

When the analyzed traces use different programming models, the static
efficiency tables and the scaling plots are not generated, because they
assume a single programming model. The comparison is available in the
terminal output, in ``comparison_metrics.csv``, and in the interactive report.


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