.. _cha:running-basicanalysis:

Running BasicAnalysis
#####################

This chapter describes how to run the standard BasicAnalysis workflow and
configure the analysis.

For workflows in which trace analysis and metric computation need to be
performed independently, see :doc:`04_staged_workflow`.




Standard workflow
=================

The standard BasicAnalysis workflow is executed with ``modelfactors.py``:

.. code-block:: sh

   modelfactors.py [options] <list-of-traces>

The command accepts one or more Paraver traces in either uncompressed
``.prv`` format or compressed ``.prv.gz`` format.

Trace filenames can be specified explicitly:

.. code-block:: sh

   modelfactors.py trace_1.prv trace_2.prv trace_3.prv

Wildcard expressions can also be used, for example:

.. code-block:: sh

   modelfactors.py *.prv

or for compressed traces:

.. code-block:: sh

   modelfactors.py *.prv.gz

BasicAnalysis automatically filters the input list to retain valid Paraver
traces, including compressed traces, and excludes traces generated internally
by simulation.

By default, traces are ordered according to their parallel configuration
before the metrics are computed. When several execution configurations are
provided, BasicAnalysis uses them to evaluate performance and scalability
trends.


Metric workflow
===============

BasicAnalysis automatically selects the metric workflow according to the
programming models detected in the analyzed traces.

If all traces correspond to simple execution models, BasicAnalysis uses the
simple metric workflow. If at least one trace contains hybrid parallelism,
BasicAnalysis uses the hybrid metric workflow.

Therefore, users normally do not need to select the metric workflow
explicitly.

The metric workflow can be controlled manually with:

.. code-block:: text

   -m, --metrics {simple,hybrid}

The available modes are:

``simple``
   Force the use of the simple metric workflow.

``hybrid``
   Allow BasicAnalysis to use the hybrid metric workflow when required by the
   detected trace modes. If all analyzed traces correspond to simple
   execution models, BasicAnalysis automatically uses the simple metric
   workflow.

The default is ``hybrid``.


Scaling model
=============

The scaling model can be selected with:

.. code-block:: text

   -s, --scaling {weak,strong,auto}

The available modes are:

``strong``
   Use the strong-scaling formulation when computing scalability metrics.

``weak``
   Use the weak-scaling formulation when computing scalability metrics.

``auto``
   Let BasicAnalysis determine the scaling behavior from the analyzed
   executions.

The default is ``auto``.

The scaling model affects the computation and interpretation of scalability
metrics. The detected and selected scaling models are reported in the
**Scaling** section of the performance report.

See :doc:`05_methodology` and :doc:`06_metrics` for the definition and
interpretation of the scalability metrics.


Selecting the MPI+GPU metric model
==================================

For MPI+GPU applications, BasicAnalysis computes both the classic
multiplicative model and the TALP-based model.

The model displayed in the standard output can be selected with:

.. code-block:: text

   -pop-model, --pop_model_to_apply {classic,talp}

The available models are:

``classic``
   Display the classic multiplicative model in the standard output.

``talp``
   Display the TALP-based model in the standard output.

The default is ``talp``.

This option affects the model presented in the standard output. The
interactive Performance Report provides access to both models, allowing
users to inspect the complementary information provided by each one.

The classic and TALP-based models, including the Host and Device
execution-domain analysis associated with the TALP-based model, are
described in :doc:`05_methodology` and :doc:`06_metrics`.


Dimemas simulation
==================

Some communication-efficiency metrics require information obtained from an
idealized execution simulated with Dimemas.

Simulation can be disabled with:

.. code-block:: text

   -skip-simul, --skip-simulation

When this option is used, BasicAnalysis does not run the Dimemas simulation.
Metrics that depend on simulated execution information may consequently be
reported as unavailable.

Additional simulation options are available for traces containing OpenMP or
CUDA activity:

.. code-block:: text

   -somp, --simulation_openmp
   -scuda, --simulation_cuda

``--simulation_openmp``
   Enable simulation of OpenMP events.

``--simulation_cuda``
   Enable simulation of CUDA events.

The role of Dimemas, the idealized execution, and the metrics that depend on
simulation are described in :doc:`06_metrics`.


Trace-mode detection
====================

BasicAnalysis automatically determines the programming and tracing mode of
the analyzed traces.

The source used for trace-mode detection can be selected with:

.. code-block:: text

   -tmd, --trace_mode_detection {pcf,prv}

``pcf``
   Detect the trace mode using the Paraver configuration file. This is the
   default.

``prv``
   Inspect the trace itself to determine the available instrumentation.
   This mode is useful for customized traces, such as filtered or cut traces,
   whose contents may no longer correspond exactly to the original ``.pcf``
   description.

The default is ``pcf``.


Trace ordering
==============

By default, BasicAnalysis orders the analyzed traces according to their
parallel configuration.

This behavior is controlled with:

.. code-block:: text

   -ord, --order_traces {yes,not}

``yes``
   Order the traces before performing the comparative analysis.

``not``
   Preserve the input trace order.

The default is ``yes``.

Trace ordering is particularly relevant when several configurations are
analyzed because the first execution is used as the reference for several
relative performance and scalability metrics.

Preserving the input order is also useful when the analyzed traces are not a
scaling study, for example when comparing executions with the same parallel
resources but different problems, or executions that use different
programming models (see :ref:`sec:comparing-programming-models`). In these
cases, list the trace to be used as reference first and use ``-ord not``.


.. _sec:comparing-programming-models:

Comparing programming models
============================

BasicAnalysis can compare executions that use different programming models,
for example a new MPI+CUDA implementation of an application with its legacy
MPI or MPI+OpenMP version, or the MPI+CUDA and MPI+HIP versions of the same
application.

The comparison is activated automatically when more than one trace is
analyzed and the traces do not all use the same programming model. No
additional option is required:

.. code-block:: sh

   modelfactors.py app_mpi.prv app_mpi_cuda.prv app_mpi_openmp.prv

When all traces use the same programming model, BasicAnalysis performs the
usual analysis and its output is not affected.

In the comparison:

* Each trace is described with the efficiency metrics of its own programming
  model. Metrics that do not apply to a programming model, such as Device
  metrics for an MPI execution, are left empty.
* Scaling detection and the metrics computed relative to a reference
  execution, such as Global Efficiency and Computation Scalability, are not
  computed across programming models.
* Elapsed time and Speedup remain available. Speedup is the runtime ratio
  relative to the first trace.
* The interactive report contains a **Programming Model Comparison** tab and
  one tab per programming model with the complete analysis of its traces.

The first trace is the reference for Speedup. By default, traces are ordered
according to their parallel configuration (see `Trace ordering`_). To use a
specific execution as reference, for example the legacy version of the
application, list it first and preserve the input order:

.. code-block:: sh

   modelfactors.py -ord not app_legacy_mpi.prv app_new_mpi_cuda.prv

The comparison is supported for **Detailed** traces of MPI-based programming
models, such as MPI, MPI+OpenMP, MPI+CUDA, and MPI+HIP. If a trace set with
different programming models contains a Burst trace or a trace without MPI,
BasicAnalysis stops and lists the traces that cannot be compared. These traces
should be analyzed separately.

The comparison always uses the hybrid metric workflow, which covers all
MPI-based programming models, even when ``--metrics simple`` is selected.

The comparison is also available in the staged workflow
(:doc:`04_staged_workflow`). The methodology of the comparison is described in
:ref:`sec:methodology-programming-model-comparison`, and the corresponding
report views in :ref:`sec:report-programming-model-comparison`.


Parallel trace analysis
=======================

Independent traces can be analyzed concurrently to reduce the total analysis
time.

The number of concurrent workers is controlled with:

.. code-block:: text

   --jobs <number|auto>

``1``
   Analyze traces sequentially. This is the default.

``<number>``
   Analyze up to the specified number of traces concurrently.

``auto``
   Let BasicAnalysis determine an appropriate number of concurrent workers
   according to the available resources.

The estimated memory available to each worker can be controlled with:

.. code-block:: text

   --mem-per-worker-gb <value>

This option overrides the automatic memory estimate used when determining
parallel trace-processing capacity.

Parallel processing applies to independent trace analyses; it does not change
the performance metrics computed for each trace.


Maximum trace size
==================

The maximum input trace size accepted by BasicAnalysis can be controlled with:

.. code-block:: text

   -ms, --max_trace_size <MiB>

The default maximum size is 1024 MiB.

Traces larger than the configured limit are excluded from the analysis.
BasicAnalysis reports the traces that have been excluded. If every input trace
exceeds the limit, the analysis terminates without computing metrics.


Debug information
=================

Additional diagnostic information can be enabled with:

.. code-block:: text

   -d, --debug

This option is useful when validating trace detection, metric computation, or
report generation.


Version information
===================

The installed BasicAnalysis version can be displayed with:

.. code-block:: text

   -v, --version


Command-line help
=================

The complete set of options supported by the installed BasicAnalysis version
can always be obtained with:

.. code-block:: sh

   modelfactors.py --help

The command-line help should be considered the authoritative reference for
the options available in a particular BasicAnalysis version.