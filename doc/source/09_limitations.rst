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


GPU Trace Sources: Extrae and nsys2prv
--------------------------------------

BasicAnalysis computes the Host and Device metrics for GPU traces generated
with Extrae and with *nsys2prv*. Both sources provide the metrics, but they
record different information, so some quantities are obtained under
different assumptions. The definitions are described in :doc:`06_metrics`.

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Quantity
     - Extrae
     - nsys2prv
   * - Useful Device time
     - *Running* state of the GPU streams (kernel execution)
     - Kernel events (``63000006``) of the GPU streams
   * - Device communication
     - *Memory transfer* state of the GPU streams
     - Memory copies and ``memset`` (``63000001``) and NCCL kernels
       (``63000007``)
   * - ``memset`` on the device
     - Not recorded on the GPU streams: not counted as useful time or
       communication; it appears as idle device time
     - Counted as a memory operation (communication)
   * - ``memset`` on the host
     - Time in the call: Device Offload loss
     - Time in the call: Device Offload loss
   * - Useful Host time
     - *Running* state of the host threads
     - Elapsed time minus the time in CUDA calls
   * - Host hardware counters (IPC, instructions, frequency)
     - Available when recorded
     - Not available
   * - GPU hardware counters
     - Not available
     - Available when the report includes GPU metrics (``Metrics GPU<n>``
       threads)
   * - *Dimemas* simulation
     - Available for MPI+CUDA
     - Not available

**Assumptions for nsys2prv traces**

* **Useful Host time.** Without state records, the useful Host time is the
  elapsed time minus the time inside CUDA runtime and driver calls. It
  includes any Host time outside those calls, such as interpreter, waiting,
  or I/O time in Python applications. Device Offload Efficiency is therefore
  an upper bound of the efficiency that would be obtained with state records.
* **Processes without GPU streams.** Only the processes with GPU streams are
  analyzed as Host. Processes that do not offload work to the accelerator are
  reported in the standard output and are not included in the metrics.
* **Memory operations.** Following the TALP device model, ``memset`` and all
  memory copies count as communication. *nsys2prv* does not distinguish
  Device-to-Device copies within a GPU from copies between GPUs, so both are
  counted as communication.
* **Region of interest.** The metrics are computed over the whole trace,
  which BasicAnalysis assumes is the region of interest, as for Extrae
  traces. When the trace includes initialization (for example, loading model
  weights), that phase is part of the metrics, and it can dominate them: in
  a vLLM benchmark, the inference phases started at 38.6 s of a 53.7 s
  trace. The trace should therefore be cut to the region of interest with
  the Paraver Cutter before the analysis; the NVTX ranges recorded by
  *nsys2prv* (event ``9600``) show where the application phases start and
  end. BasicAnalysis reports one set of metrics for the analyzed trace and
  does not break them down per NVTX range: comparing phases is part of the
  detailed analysis in Paraver.
* **Programming models and validation.** Only CUDA is supported; the
  configurations use the CUDA event types of *nsys2prv*. The metrics have
  been validated with single-GPU traces and with a multi-node trace of 32
  GPUs (one GPU per process, NCCL collectives); several GPUs per process and
  shared GPUs are covered by the implementation but have not yet been
  validated with real traces.
* **Nodes.** *nsys2prv* does not record the node of each process: traces
  merged from several nodes place every process on the same node, and the
  device numbers repeat on each node. When the trace has more
  ``Metrics GPU<n>`` threads than GPUs identified by node and device number,
  BasicAnalysis assumes that each process uses its own GPUs (processes do not
  share a GPU). Without GPU metrics threads this cannot be checked: processes
  with the same device number are then analyzed as sharing the GPU, and
  BasicAnalysis prints a warning.
* **Trace metadata.** The ``.row`` file is required to identify the GPU
  streams, the GPU metrics threads, and the host threads.
* **GPU hardware counters.** The GPU metrics are sampled for the whole GPU
  (every 100 µs by default), so they cannot be attributed reliably to
  individual kernels, which are often shorter than the sampling period or
  run concurrently on several streams. BasicAnalysis reports them as
  averages over the whole execution weighted by the GPU activity (GR
  Active), which do not need that attribution; they are not valid per
  kernel. Additional assumptions:

  * The sampled values are integers, so low percentages (for example, SM
    Issue) lose precision.
  * An idle GPU reports GR Active = 1%, never 0%, with SMs Active and SM
    Issue = 0. *nsys2prv* copies the values of the Nsight Systems report
    unchanged, so this floor comes from Nsight Systems; no official Nsight
    documentation of it has been found. These samples are included in the
    GR Active integral, so GPU Active is slightly overestimated and the
    metrics divided by GR Active (SM Coverage, SM Utilization, Tensor Core
    Activity, DRAM bandwidth, and GPC Clock) are slightly underestimated. The
    effect grows with the idle time: in the vLLM traces analyzed, the idle
    samples are 5.1% of the GR Active integral for a mostly idle GPU (SM
    Coverage 46.43% instead of 48.92%) and 0.8% for a busy GPU (94.42%
    instead of 95.18%). SM Issue Efficiency and Achieved Occupancy are not
    affected.
  * The GPC clock is recorded in Hz although its label says MHz;
    BasicAnalysis converts averages above 10\ :sup:`5` to MHz.
  * The control window of the configurations assumes that the GPC clock is
    sampled during the whole execution.
  * The integrals cover the whole trace as loaded by Paraver, including the
    samples written after the end declared in the header, and the last
    sample of each GPU is extended until the end of the trace. GPU Active is
    computed over that same period. When the sampling of the GPUs ends at
    different times, GPU Active is overestimated (in a 32-GPU trace, 97.06%
    instead of 93.36% for the measured samples only).
  * With several GPUs, the counters of all ``Metrics GPU<n>`` threads are
    added.
  * The *Avg* variants of the warp counters are not used: values that
    underflow (for example, 4294967293) have been observed.

**Limitations for Extrae traces**

* The device-side execution of ``cudaMemset`` and ``cudaMemsetAsync`` is not
  recorded on the GPU streams; only the host-side call is recorded. Its
  device time therefore lowers Device Orchestration Efficiency instead of
  Device Communication Efficiency.
* Extrae does not record the direction of memory copies, so Device-to-Device
  copies within a GPU are counted as communication, as in *nsys2prv* traces.

The differences between the two sources are small in the traces analyzed so
far, but they should be considered when comparing Extrae and *nsys2prv*
traces of the same application.


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
