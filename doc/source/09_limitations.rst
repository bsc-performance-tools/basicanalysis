Limitations
===========

This section summarizes the main limitations of the current BasicAnalysis
methodology and implementation. Metric-specific availability conditions are
described in :doc:`06_metrics`.


Simulation-Derived Metrics
--------------------------

Serialization Efficiency and Transfer Efficiency rely on an ideal execution
simulated with *Dimemas*. These metrics are therefore available only for
programming models and runtime events supported by the current BasicAnalysis
and *Dimemas* simulation workflow.

**BasicAnalysis** currently uses *Dimemas* simulation for MPI, MPI+OpenMP, and
MPI+CUDA applications.

For MPI+HIP applications, MPI Communication Efficiency can be computed from
the measured execution, but Serialization Efficiency and Transfer Efficiency
are reported as ``Non-Avail``. The current BasicAnalysis-*Dimemas* workflow
has not been validated for HIP accelerator events, and BasicAnalysis therefore
does not use simulation-derived communication submetrics for these
executions.

Simulation-derived metrics are also unavailable when *Dimemas* is not
installed, when the required simulation cannot be completed, or when
simulation is explicitly disabled with the ``--skip-simulation`` option.


Number of Parallel Runtimes
---------------------------

The Parallel Runtime Model has been validated for applications with up to two
parallel runtime levels, such as MPI+OpenMP and MPI+GPU.

Applications containing more than two parallel runtimes may be detected in the
trace, but their decomposition into runtime-specific efficiency contributions
has not been validated.

For example, an application combining MPI, a CPU threading runtime, and a GPU
runtime introduces three parallel runtime levels. The current Parallel Runtime
Model does not provide an independently validated efficiency decomposition for
all three runtime contributions.

The application-level metrics may still provide useful performance
information, but the runtime-specific decomposition should not be interpreted
as a complete attribution of the efficiency loss across all active runtimes.


Hierarchical Execution Model
----------------------------

The Parallel Runtime Model assumes a hierarchical organization of the parallel
runtimes. For hybrid applications, MPI is considered the outer parallel level
and the second runtime, such as OpenMP, CUDA, or HIP, the inner parallel level.

The multiplicative runtime decomposition therefore assumes that the execution
of the inner parallel runtime is compatible with this hierarchical
organization.

For example, in an MPI+OpenMP application, when the master thread executes MPI
calls outside an OpenMP parallel region, the remaining OpenMP worker threads
are considered inactive. The corresponding unused thread capacity can then be
attributed to the OpenMP serial component.

Applications whose runtime behavior substantially violates the assumed
hierarchical organization, for example through concurrent useful activity
across runtime levels that the model treats as mutually exclusive, may not be
fully represented by the runtime decomposition.


GPU Execution-Domain Analysis
-----------------------------

The Host/Device execution-domain analysis for MPI+CUDA and MPI+HIP applications
depends on the accelerator activity represented in the Paraver trace.

GPU traces can contain multiple execution streams associated with the same
physical device. BasicAnalysis maps these streams to physical devices and
flattens overlapping useful-computation and memory-transfer intervals before
constructing the Device metrics.

Consequently, the correctness of the Device metrics depends on BasicAnalysis
being able to identify the GPU streams and map them to their corresponding
physical devices from the trace information.

Device activity that is not represented in the trace, or accelerator
configurations for which the stream-to-device mapping cannot be established
correctly, cannot be fully characterized by the Device execution-domain
metrics.


I/O Analysis
------------

The I/O metrics characterize the time contribution and distribution of the
File I/O activity captured in the trace.

BasicAnalysis currently distinguishes MPI-I/O and POSIX/ANSI C File I/O
activity and reports the corresponding efficiency and load-balance metrics
when that activity is detected.

These metrics do not directly characterize transferred data volume, achieved
I/O bandwidth, storage-system utilization, filesystem contention, or the
performance of individual I/O operations. They therefore identify whether
File I/O activity has a significant execution-time contribution or an
imbalanced distribution, but they do not by themselves determine the
underlying storage-system cause.

When I/O activity represents a significant performance factor, detailed trace
analysis or specialized I/O performance-analysis tools may be required for
further diagnosis.