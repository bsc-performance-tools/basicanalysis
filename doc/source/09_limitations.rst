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

The I/O metrics characterize the time of the File I/O captured in the
trace: the POSIX, ANSI C, and MPI-IO calls recorded by Extrae, classified into
Data Access and File Management.

The following assumptions and limitations apply:

* **Nested calls.** Extrae does not trace, by default, the POSIX calls
  performed inside MPI-IO calls. BasicAnalysis assumes this default; if the
  internal POSIX calls were traced, their time would be counted twice.
* **I/O library computation.** The CPU work of I/O libraries (for example
  HDF5 compression or metadata handling) is not distinguished from the
  application computation and counts as useful time. A library that spends
  more CPU time therefore increases I/O Efficiency.
* **Descriptor types.** Calls on non-file descriptors (standard output,
  sockets, pipes) are counted as File I/O.
* **I/O not visible in the trace.** Memory-mapped I/O, asynchronous I/O,
  and I/O performed by threads that are not instrumented are not measured.
* **Whole-execution aggregation.** The metrics describe the whole execution;
  applications with distinct I/O phases (for example, a write phase and a
  read phase) should be inspected per phase in Paraver.
* **Critical path.** I/O Load Balance and I/O Critical-Path Efficiency
  assume that the units synchronize after each kind of I/O call, so that the
  others wait for the slowest unit. When the I/O of a unit overlaps the
  computation of the others, they underestimate the efficiency.
* **Useful time in GPU applications.** In MPI+GPU traces, the useful time
  used by the I/O efficiencies also includes the useful time of the GPU
  streams, while File I/O is performed by the Host. The I/O efficiencies are
  therefore slightly overestimated when the GPU streams have significant
  useful time.

These metrics do not characterize achieved I/O bandwidth, storage-system
utilization, or filesystem contention. They identify whether File I/O has a
significant execution-time contribution, which component (Data Access or
File Management) is responsible, and how it is distributed, but they do not
by themselves determine the underlying storage-system cause.

When I/O activity represents a significant performance factor, detailed trace
analysis or specialized I/O performance-analysis tools may be required for
further diagnosis.


Comparison of Programming Models
--------------------------------

The comparison of executions that use different programming models is
supported for Detailed traces of MPI-based programming models, such as MPI,
MPI+OpenMP, MPI+CUDA, and MPI+HIP. Burst traces and traces without MPI cannot
be included in such a comparison and must be analyzed separately.

Scalability metrics, Global Efficiency, Efficiency, and the detection of the
scaling model are not computed across programming models, because they would
compare computation performed on different kinds of resources. Speedup is
computed relative to the first trace and should be interpreted as a comparison
of elapsed times. When the compared executions solve different problems or
problem sizes, Speedup does not represent a performance improvement of the
same computation.

The comparison relates metrics that represent the same performance factor in
each programming model, but these metrics may be computed from different
quantities. For example, the MPI metrics of an MPI execution are based on
useful computation, while those of a hybrid execution are based on the time
spent outside MPI. Small differences between executions should therefore be
interpreted with care.

The interactive report embeds the complete report of each programming model.
When many programming models are compared, the report file is therefore
larger than the report of a single analysis.
