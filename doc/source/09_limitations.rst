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
  sockets, pipes) are counted as File I/O; only the access pattern
  excludes them.
* **I/O not visible in the trace.** Memory-mapped I/O, asynchronous I/O,
  and I/O performed by threads that are not instrumented are not measured.
* **Whole-execution aggregation.** The metrics describe the whole execution;
  applications with distinct I/O phases (for example, a write phase and a
  read phase) should be inspected per phase in Paraver.
* **Critical path.** I/O Load Balance and I/O Critical-Path Efficiency
  assume that the units synchronize after each kind of I/O call, so that the
  others wait for the slowest unit. When the I/O of a unit overlaps the
  computation of the others, they underestimate the efficiency.
* **Request sizes.** The volume and the request-size distribution include
  the read and write calls whose request size is recorded in the trace (see
  the request-size coverage). The MPI-IO size is the requested size (count
  times the datatype size), which may be more than the bytes read at the end
  of a file. The nonblocking MPI-IO calls (``MPI_File_iread``,
  ``MPI_File_iwrite``) are not instrumented by Extrae. Zero-byte requests
  are not counted. When
  a call starts before the previous call of the same thread has ended
  (unclosed or nested calls, rare in Extrae traces), only the later call is
  counted.
* **Files.** Only the POSIX and ANSI C calls are attributed to files: MPI-IO
  records neither the file name nor the file handle. A call is attributed
  through its descriptor to the last ``open`` or ``fopen`` of the process
  that returned it; calls on descriptors opened before the tracing starts
  or with calls that Extrae does not instrument (``openat``, ``creat``,
  ``dup``), and after an ``open`` or ``fopen`` without a file name in the
  trace, are not attributed to a file (see the file-name coverage). Files
  are identified by the name passed to ``open``: the same file opened with
  different paths (relative and absolute, or through links) appears as
  several files. A failed ``open`` counts as an open of the file.
* **Access pattern.** The offset of the reads and writes is rebuilt from
  the ``open`` calls, the seeks, and the request sizes. Extrae records the
  seek offset without its origin (``whence``): every seek is taken as
  absolute (``SEEK_SET``), so a relative seek (``SEEK_CUR``, ``SEEK_END``)
  misplaces the following requests of the descriptor. The seek offset is
  recorded only by recent Extrae versions; with older versions, the
  position is unknown after the first seek. The size is the requested size,
  so a short read advances the position too far. The open flags are not
  recorded: the writes to a file opened with ``O_APPEND`` go to its end,
  whatever the position. The ``pread``/``pwrite`` family, MPI-IO, and
  descriptors without a traced ``open`` (until their first seek) have no
  known offset (see the offset coverage). ``fread``/``fwrite`` show the
  pattern presented to the C library, before its buffering. The pattern is
  given per process: how the regions of several processes fit together in a
  shared file is not analyzed.

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
