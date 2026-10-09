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
* **Region of interest.** The metrics are computed over the whole trace. When
  the trace includes initialization (for example, loading model weights),
  that phase is part of the metrics; the trace should be cut to the region of
  interest, as with Extrae traces. Metrics per NVTX phase are not yet
  available.
* **Programming models and validation.** Only CUDA is supported; the
  configurations use the CUDA event types of *nsys2prv*. The metrics have
  been validated with single-GPU traces; several GPUs per process, shared
  GPUs, and NCCL collectives are covered by the implementation but have not
  yet been validated with real traces.
* **Trace metadata.** The ``.row`` file is required to identify the GPU
  streams, the GPU metrics threads, and the host threads.

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
