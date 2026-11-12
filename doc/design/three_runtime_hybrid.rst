Hybrid Applications with Three Parallel Runtimes
================================================

:Status: Design; not implemented
:Date: 2026-11-13
:Branch: ``feature/three-runtime-hybrid``
:Scope: MPI applications that combine a CPU runtime (OpenMP, OpenACC, Pthreads)
        with an accelerator runtime (CUDA, HIP), Extrae traces.

BasicAnalysis has a performance model for MPI+X with one second runtime
(MPI+OpenMP, MPI+CUDA, MPI+HIP). Since 2026-11-11, traces that combine a GPU
runtime with a CPU threading runtime stop before computing the metrics, because
no model was defined for them. This document proposes the model for the two
kinds of applications found in practice.


Context
-------

* **TLAB (POP user ticket, November 2026).** MPI + OpenMP target offloading +
  HIP on AMD MI300A, 4 MPI processes with one CPU thread each and one GPU per
  process. The trace contains OpenMP target events, and all the GPU work comes
  from OpenMP target regions; the HIP calls (``hipLaunch``,
  ``hipStreamSynchronize``) are made by the OpenMP runtime inside those
  regions. BasicAnalysis detects it as MPI+HIP, and the Host and Device metrics
  are correct, but the role of the OpenMP target constructs is not visible.
  The metrics sent to the user are in `Case 1: worked example (TLAB)`_.
* **SPH-EXA, iPIC3D.** MPI + OpenMP (or Pthreads) with several threads per
  process, and CUDA. Detected as MPI+OpenMP+CUDA or MPI+Pthreads+CUDA; they
  stop today.


The two cases
-------------

.. list-table::
   :header-rows: 1
   :widths: 18 41 41

   * -
     - **Case 1: CPU runtime used only to offload**
     - **Case 2: CPU runtime with offloading and computing threads**
   * - Programming
     - OpenMP target or OpenACC directives; one CPU thread per MPI process
       (no host parallel regions with more than one thread)
     - OpenMP (or Pthreads) parallel regions with several threads per process;
       one or more threads offload to the GPU
   * - CPU inner level
     - Time in the offloading constructs and accelerator calls of the single
       thread: an inner level in **time**, not in threads
     - Threads computing, idle threads, and offloading time: an inner level in
       **threads**, plus offloading
   * - Example
     - TLAB
     - SPH-EXA, iPIC3D
   * - Model
     - The Host model of BasicAnalysis, with the offloading time taken from the
       directives and the calls; adds the decomposition of the offloading
       contribution
     - New: MPI × CPU threading × Offloading on the Host
   * - Device side
     - Unchanged
     - Unchanged


Detection
---------

Event types written by Extrae (5.1.10 source and traces):

.. list-table::
   :header-rows: 1
   :widths: 28 32 40

   * - Runtime
     - Event types
     - Notes
   * - OpenMP (classic)
     - ``60000xxx``
     - What BasicAnalysis recognizes as OpenMP today
   * - OpenMP (OMPT)
     - 70003 Parallel, 70007 Implicit Task, 70023 Sync, 72000 function
     - Written by Extrae 5.1 in the TLAB trace. **Not recognized as OpenMP by
       BasicAnalysis.**
   * - OpenMP target (OMPT)
     - 70008 Target (Offloading, Data Enter, Data Exit), 70009 Target Data
       Operation (instant: Associate, Disassociate), 70010 Kernel Submit
     - TLAB trace
   * - OpenACC
     - 66000000, 66000001 (data), 66000002 (launch)
     - Values ``acc_ev_compute_construct``, ``acc_ev_enter_data``,
       ``acc_ev_wait``…; no trace available yet
   * - CUDA / HIP calls
     - 63000000 / 63500000
     - CPU threads
   * - GPU streams
     - ``.row`` labels (``GPU-D<n>.S<m>``, ``CUDA-D<n>…``, ``GPU_<uuid>``)
     - See `GPU identity`_

Rules, per trace, from the ``.pcf`` and the ``.prv``:

* **Accelerator**: GPU streams in the ``.row`` and CUDA or HIP calls.
* **Offloading directives**: OpenMP target (70008) or OpenACC (66000000)
  events on the CPU threads.
* **CPU threading**: more than one CPU thread with useful computation in some
  process, inside OpenMP (60000xxx or 70003/70007) or Pthreads regions.

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - Accelerator + directives + threading
     - Case
     - Trace mode shown (proposal)
   * - Accelerator, no directives, no threading
     - Current MPI+GPU model
     - MPI+HIP
   * - Accelerator + directives, no threading
     - **Case 1**
     - MPI+HIP (OpenMP target) / MPI+CUDA (OpenACC)
   * - Accelerator + threading (with or without directives)
     - **Case 2**
     - MPI+OpenMP+HIP

**Prerequisite (OMPT OpenMP).** BasicAnalysis must recognize the OMPT OpenMP
events (70003, 70007) as OpenMP. Otherwise an MPI+OpenMP trace written with
OMPT events is analyzed as pure MPI, without a warning. This needs an
MPI+OpenMP trace (several threads per process) from Extrae 5.1 to confirm
which event types it writes, and is independent of the rest of this document.


Notation
--------

For MPI rank :math:`i` (:math:`i = 1 \ldots P`) and its CPU thread :math:`j`
(:math:`j = 1 \ldots t_i`), with :math:`T` the elapsed time and
:math:`H = \sum_i t_i` the number of CPU threads:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Symbol
     - Meaning
   * - :math:`MPI_i`
     - Time in MPI calls of the thread of rank :math:`i` that calls MPI
   * - :math:`OutsideMPI_i`
     - :math:`T - MPI_i`
   * - :math:`Offload_{ij}`
     - Time of thread :math:`j` of rank :math:`i` in the offloading: the union
       of the directive constructs (OpenMP target regions and data
       operations, OpenACC constructs) and the accelerator calls (CUDA, HIP),
       outside MPI
   * - :math:`Useful_{ij}`
     - Useful computation of the thread: outside MPI, outside the offloading,
       and outside the CPU runtime (OpenMP synchronization, idle)
   * - :math:`Active_{ij}`
     - :math:`Useful_{ij} + Offload_{ij}`: time in which the thread computes or
       offloads

The **union** of constructs and calls covers both applications that use only
directives (the constructs also include the work of the OpenMP or OpenACC
runtime around the calls) and applications that also call CUDA or HIP
directly (calls outside the constructs). When all the calls are inside the
constructs, the union equals the time of the constructs.


Case 1: CPU runtime used only to offload
-----------------------------------------

One CPU thread per rank (:math:`t_i = 1`, :math:`H = P`), so the index
:math:`j` is dropped.

MPI level (as today):

.. math::

   MPI\_PE = \frac{\sum_i OutsideMPI_i}{P \cdot T}, \quad
   MPI\_LB = \frac{\frac{1}{P}\sum_i OutsideMPI_i}{\max_i OutsideMPI_i}, \quad
   MPI\_CommE = \frac{\max_i OutsideMPI_i}{T}

Host level, with :math:`Useful_i = T - |MPI_i \cup Offload_i|`:

.. math::

   Host\_PE = \frac{\sum_i Useful_i}{P \cdot T}, \quad
   Host\_LB = \frac{\frac{1}{P}\sum_i Useful_i}{\max_i Useful_i}, \quad
   Host\_CommE = \frac{\max_i Useful_i}{T}

Offloading level, the inner level of the Host:

.. math::

   Offloading\_Eff = \frac{Host\_PE}{MPI\_PE}
                   = \frac{\sum_i Useful_i}{\sum_i OutsideMPI_i}

and its contributions to Load Balance and Communication:

.. math::

   Offloading\_LB = \frac{Host\_LB}{MPI\_LB}, \quad
   Offloading\_CommE = \frac{Host\_CommE}{MPI\_CommE}

with :math:`Offloading\_Eff = Offloading\_LB \times Offloading\_CommE` and

.. math::

   Host\_PE = MPI\_PE \times Offloading\_Eff

This is the current Host model of BasicAnalysis (Host Parallel Efficiency =
MPI Parallel Efficiency × Offloading Efficiency). The two changes are the
offloading time (constructs and calls, not only the calls) and the
decomposition of Offloading Efficiency into its Load Balance and Communication
contributions:

* :math:`Offloading\_LB` above 100% means that the offloading time compensates
  the MPI imbalance (the ranks with more time outside MPI spend more of it
  offloading); below 100%, that it adds imbalance.
* :math:`Offloading\_CommE` measures the waiting for the device: low values
  mean that the CPU thread waits in the offloading (synchronous offloading)
  instead of computing.

Diagnostics of the offloading time (Host view, not multiplicative): data
mapping (OpenMP Data Enter/Exit, OpenACC enter/exit data, uploads and
downloads), launch (``hipLaunch``, ``cudaLaunchKernel``, Kernel Submit), wait
(``hipStreamSynchronize``, ``cudaDeviceSynchronize``, ``acc_ev_wait``), and
other runtime time. Instant events (Associate, Disassociate) are counted, not
timed.

Case 1: worked example (TLAB)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Trace ``tlab.4mpi_5iter_4th_substep_4th_repetition``: :math:`P = 4`,
:math:`T = 89.04` s. The offloading time is that of the OpenMP target
constructs (70008), which contain all the HIP calls.

.. list-table::
   :header-rows: 1
   :widths: 16 21 21 21 21

   * - Rank
     - :math:`MPI_i` (s)
     - :math:`OutsideMPI_i` (s)
     - :math:`Offload_i` (s)
     - :math:`Useful_i` (s)
   * - 1
     - 3.39
     - 85.65
     - 77.63
     - 8.01
   * - 2
     - 5.96
     - 83.08
     - 75.18
     - 7.90
   * - 3
     - 2.51
     - 86.53
     - 78.53
     - 7.99
   * - 4
     - 5.46
     - 83.58
     - 75.56
     - 8.02

.. list-table::
   :header-rows: 1
   :widths: 34 22 22 22

   * - Level
     - PE
     - LB
     - CommE
   * - Host (useful)
     - 8.96%
     - 99.54%
     - 9.00%
   * - MPI
     - 95.14%
     - 97.90%
     - 97.18%
   * - Offloading (OpenMP target)
     - 9.42%
     - 101.68%
     - 9.27%

Checks: :math:`95.14\% \times 9.42\% = 8.96\%`;
:math:`97.90\% \times 101.68\% = 99.54\%`;
:math:`97.18\% \times 9.27\% = 9.01\%` (9.00% without rounding the factors).

BasicAnalysis reports Offloading Efficiency 9.41% for this trace. The values
above were computed from the events (useful time = elapsed time minus the MPI
and target-construct time), while BasicAnalysis takes the useful Host time from
the Running state of the CPU threads; the 0.01-point difference comes from
that. An implementation must use one definition of useful time for both the
Host and the offloading levels.

Diagnostics (paramedir, per rank): Target Offloading 75.2–78.5 s, of which
``hipStreamSynchronize`` is practically all; Target Data Enter about 7 ms and
Data Exit about 5 ms; ``hipLaunch`` about 8 ms; about 2,300 Associate and
2,300 Disassociate operations.


Case 2: CPU runtime with offloading and computing threads
----------------------------------------------------------

Units: all the CPU threads (:math:`H`). The Host Parallel Efficiency is
decomposed in three levels, with an exact product:

.. math::

   Host\_PE = \frac{\sum_{i,j} Useful_{ij}}{H \cdot T}
            = MPI\_PE \times Thread\_PE \times Offloading\_Eff

where

.. math::

   MPI\_PE = \frac{\sum_i t_i \cdot OutsideMPI_i}{H \cdot T}

(the current MPI Parallel Efficiency, weighted by the threads of each rank),

.. math::

   Thread\_PE = \frac{\sum_{i,j} Active_{ij}}{\sum_i t_i \cdot OutsideMPI_i}

(the fraction of the thread time outside MPI in which the threads compute or
offload: losses from idle threads, serial regions, and the CPU runtime
synchronization and scheduling), and

.. math::

   Offloading\_Eff = \frac{\sum_{i,j} Useful_{ij}}{\sum_{i,j} Active_{ij}}

(the fraction of the active thread time that is useful computation, not
offloading). The product telescopes: each denominator is the previous
numerator.

Load Balance and Communication contributions, with the same ratios as the
Hybrid model of BasicAnalysis:

.. math::

   LB_X = \frac{\frac{1}{H}\sum_{i,j} X_{ij}}{\max_{i,j} X_{ij}}, \quad
   CommE_X = \frac{\max_{i,j} X_{ij}}{T}

for :math:`X = Active` and :math:`X = Useful`, and

.. math::

   Thread\_LB = \frac{LB_{Active}}{MPI\_LB}, \quad
   Offloading\_LB = \frac{LB_{Useful}}{LB_{Active}}

(and the same for CommE), so that each level's PE is the product of its LB
and CommE contributions.

Reading:

* low :math:`Thread\_PE`: the CPU threads are idle outside MPI (serial
  regions, imbalance between threads, OpenMP overhead);
* low :math:`Offloading\_Eff`: the threads spend their active time offloading
  or waiting for the GPU instead of computing; in GPU-centric codes this is
  expected;
* the isolated OpenMP metrics (Serial, Region Load Balance, Scheduling) stay
  available as a complementary view of the CPU threading.

Points to define:

* **Thread that offloads.** Offloading can be done by one thread (the master,
  outside parallel regions) or by several threads at once (inside parallel
  regions). :math:`Offload_{ij}` is per thread, so both are covered, but the
  reading of :math:`Thread\_PE` differs: in the first case the other threads
  are idle while the master offloads.
* **Overlap.** With asynchronous offloading (``nowait``, ``async``), a thread
  can compute while the GPU works; only the time in the constructs and calls
  counts as offloading, so this overlap appears as useful time, as it should.
  Threads active while the MPI thread is inside MPI can make
  :math:`Thread\_PE` exceed 100% (the "Other" effect studied in the runtime
  model views).
* **Runtime Model view.** For three runtimes, the Hybrid (MPI+X) table of the
  report would be Hybrid (MPI+OpenMP) over the CPU threads, with the GPU in the
  Heterogeneous Model, as today for MPI+CUDA.
* **Dimemas.** Serialization and Transfer are not available (no simulation of
  the GPU runtime), as for MPI+HIP today.


GPU identity
------------

Both cases need the physical GPU of each stream for the Device metrics.
Traces from Extrae 5.1 with one GPU per process label all the streams
``D1``; see the limitation in the User Guide (``09_limitations.rst``) and the
request to the Extrae team (GPU UUID in the labels).


Validation plan
---------------

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Trace
     - Case
     - Check
   * - TLAB (MI300A, OpenMP target)
     - 1
     - Reproduce the worked example; Offloading Efficiency 9.42%
   * - OpenACC trace (to obtain)
     - 1
     - Detection of 66000000; constructs and waits
   * - SPH-EXA MPI+OpenMP+CUDA (8 local traces)
     - 2
     - Product of the three levels; compare Thread_PE with the isolated OpenMP
       metrics
   * - iPIC3D MPI+Pthreads+CUDA
     - 2
     - Pthreads as CPU runtime
   * - MPI+OpenMP from Extrae 5.1 (OMPT events, to obtain)
     - Prerequisite
     - Recognition of 70003/70007 as OpenMP


Phases
------

1. Prerequisite: recognize the OMPT OpenMP events as OpenMP (with the trace of
   the validation plan).
2. Case 1: detection of offloading directives, offloading time as union of
   constructs and calls, decomposition of Offloading Efficiency (LB, CommE),
   diagnostics; validated with TLAB.
3. Case 2: three-level Host decomposition; remove the stop for these traces;
   validated with SPH-EXA and iPIC3D.
4. User Guide (methodology, metrics, limitations), release notes, report.


Open questions
--------------

1. Should Case 1 show the offloading decomposition (Offloading LB and CommE)
   in the Host table, or only in Metric Details?
2. Names of the new metrics: *Thread Parallel Efficiency* (or *OpenMP Parallel
   Efficiency* when the runtime is OpenMP)?
3. In Case 2, when only the master thread offloads, should the idle time of
   the other threads during the offloading go to :math:`Thread\_PE` (as
   proposed) or to the offloading?
4. Do we need an OpenACC trace before releasing Case 1, or can it be released
   for OpenMP target first?
