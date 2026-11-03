Child Metrics of the Hybrid Parallel Runtime Model
==================================================

:Status: Implemented on this branch, not merged into ``devel`` until tested
:Date: 2026-11-02 (updated 2026-11-03)
:Branch: ``feature/runtime-model-views``
:Scope: Parallel Runtime Model of the interactive report for MPI+X traces

The model is simple: every performance issue is Load Balance or Communication.
Users find it unclear that it blames MPI first, and the inner level can exceed 100%.
The nine metrics keep their names, values, and multiplications, and the new metrics
are children of existing metrics, like the decomposition of Device Computation
Scalability.


Current model
-------------

The model is defined in Giménez, Mercadal, Llort, and Mendez, *Analyzing the
Efficiency of Hybrid Codes*, ISPDC 2020 (``definitions.yaml``:
``ispdc2020_hybrid``). :math:`T` is the runtime, :math:`t_i` the threads of
process :math:`i`, :math:`U_{i,j}` the useful time of thread :math:`j`, and
:math:`O_i` the time that the first thread of process :math:`i` is outside MPI.

.. math::

   \text{Hybrid PE} = \frac{\sum_{i,j} U_{i,j}}{T \sum_i t_i}
   \qquad
   \text{MPI PE} = \frac{\sum_i O_i t_i}{T \sum_i t_i}
   \qquad
   \text{Inner PE} = \frac{\text{Hybrid PE}}{\text{MPI PE}}
   = \frac{\sum_{i,j} U_{i,j}}{\sum_i O_i t_i}

Inner Load Balance and Inner Communication Efficiency are also ratios of the
hybrid factor and the MPI factor (equations 11 to 13 of the paper).

In MPI+CUDA and MPI+HIP, the units of the application level are the Host threads
and the physical devices, with the streams of each device flattened, and the MPI
metrics are computed over the MPI ranks (User Guide, *MPI+GPU Application-Level
Metrics*; code fixed in ``devel`` ``ed5d01f``).

What the paper establishes:

* **MPI is blamed first** (Section III.A): when a rank is delayed, the wait is
  MPI inefficiency, although the source of the delay may be in the inner level.
* **The model is for hierarchical codes.** Overlap is future work (Section
  III.B), including MPI+CUDA with kernels running during communication: "we have
  to blame MPI only for the MPI time plus the time other threads are waiting".
* **Both paths matter** (Section III): by factor and by programming model, so
  the paper recommends reading all nine metrics.

The paper does not discuss values above 100%.


Why the inner level can exceed 100%
-----------------------------------

There are two different effects.

Useful work during MPI
~~~~~~~~~~~~~~~~~~~~~~

:math:`O_i` is measured only on the first thread. Other threads or GPU streams
can do useful work while it is in MPI, which increases the numerator of Inner PE
but not its denominator. This is the only way for Inner PE to exceed 100%.

Compensation between Load Balance and Communication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Inner Load Balance can exceed 100% without overlap, when useful time is more
evenly distributed than the time outside MPI. Example with 2 processes of 2
threads and :math:`T = 100`:

.. list-table::
   :header-rows: 1

   * - Process
     - :math:`O_i`
     - Useful per thread
   * - 1
     - 100
     - 50, 50
   * - 2
     - 50
     - 50, 50

Hybrid LB is 100% and MPI LB is 75%, so Inner LB is 133%. Inner Communication
Efficiency is 50%, and Inner PE is 66.7%. Process 1 spends 50 on non-useful
time (serial code, runtime overhead, or I/O). This creates the MPI imbalance, and
the loss appears in Inner Communication Efficiency. Nothing is mitigated. The
preempted run of the paper (Fig. 7) shows the same pattern: MPI LB 45.54,
OpenMP LB 93.28, OpenMP Communication 50.69.

Assigning more threads to a heavier process does not produce this signal. With
8 threads and work 800 against 2 threads and work 100, Hybrid LB and MPI LB are
both 90%, so Inner LB is 100%.

Without overlap, :math:`U_{i,j} \le O_i`, so Inner PE and Inner Communication
Efficiency cannot exceed 100%. An Inner LB above 100% then requires Inner
Communication Efficiency below 100%.


Decision
--------

An earlier version added Outer and Inner Parallel Efficiency, Process and Thread Load
Balance, and an Other table (commits ``adba48d`` and ``01f6eac``). They were removed
on 2026-11-03: Jesús does not want new names in the main tree, and the model must
stay simple. Separate classic models for CPU and GPU hybrids were also considered and
rejected, because one model keeps the comparison between programming models.

.. code-block:: text

   Global efficiency                      47.12    (BT-MZ A)
   -- Parallel efficiency                 47.12
      -- Load balance                     48.52
         -- between processes             60.53    new
         -- inside processes              80.17    new
      -- Communication efficiency         97.10

   MPI Parallel efficiency                68.23
      -- MPI Load balance                 69.37
      -- MPI Communication efficiency     98.36

   OpenMP Parallel efficiency             69.06
      -- OpenMP Load balance              69.95
      -- OpenMP Communication efficiency  98.72
      -- of which, useful work during MPI 100.00   new, neutral color


Definitions
-----------

All the multiplications of the model stay: Hybrid PE = MPI PE x Inner PE, Hybrid LB
= MPI LB x Inner LB, Hybrid Comm = MPI Comm x Inner Comm, and each PE = LB x Comm.
The new metrics are a second split of the same parents, and they do not pair with
the first.

Let :math:`\overline{U_i}` be the mean useful time of the threads of process
:math:`i`, with the threads that have useful time.

.. math::

   LB_{between} = \frac{\overline{U}}{\max_i \overline{U_i}}
   \qquad
   LB_{inside} = \frac{\max_i \overline{U_i}}{\max_{i,j} U_{i,j}}

Neither exceeds 100%, and :math:`LB_{between} \cdot LB_{inside}` is Hybrid LB, so

.. math::

   \text{Hybrid PE} = LB_{between} \cdot LB_{inside} \cdot
   MPI\_Comm \cdot Inner\_Comm

These are computed for CPU-based hybrid executions only: *inside processes* has no
clear meaning for Host threads and devices.

Let :math:`U^{M}` be the useful time of a unit while the first thread of its process
is in MPI. In MPI+GPU, a unit is a Host thread or a physical device with its streams
flattened.

.. math::

   \text{Useful work during MPI} = \frac{\sum U}{\sum (U - U^{M})} \ge 100\%

It does not multiply with the inner LB and Comm. Dividing the inner PE by it gives the
efficiency outside MPI, in the metric details and not as a row of the tree: as a
sibling of LB and Comm, a reader could multiply all four.

Results of the Load Balance split on the traces of the paper:

.. list-table::
   :header-rows: 1

   * - Trace
     - MPI LB / OpenMP LB
     - between / inside
   * - serialOMP
     - 98.9 / 52.7
     - 98.20 / 53.04
   * - unbalancedOMP
     - 99.9 / 81.7
     - 98.68 / 82.75
   * - unbalancedMPI
     - 61.3 / 96.0
     - 60.39 / 97.38
   * - unbalancedMPI_serialOMP
     - 70.1 / 69.1
     - 65.60 / 73.86
   * - hybrid_UM_BO
     - 99.5 / 39.5
     - 89.17 / 44.11
   * - hybrid_weird (preempted)
     - 45.5 / 93.3
     - 53.28 / 79.72
   * - BT-MZ A
     - 69.4 / 70.0
     - 60.53 / 80.16

The clear cases point to the same place. BT-MZ A shows that work between processes is
the larger issue, and hybrid_UM_BO shows an imbalance that MPI LB hides. Preemption
is not moved to the threads, because a preempted thread appears as running.


Text for values above 100%
--------------------------

Replaces ``above_100_template`` of ``runtime_load_balance`` in
``metrics/definitions.yaml``, which says that the runtime "partially compensates"
the imbalance:

    Values above 100% mean that Hybrid Load Balance is higher than MPI Load
    Balance. The model blames MPI first: a delay inside a process counts as MPI
    imbalance, even when its source is {runtime} or serial code. So useful time
    can be better balanced than the time outside MPI. This does not by itself
    mean that {runtime} improves load balance. The same loss usually appears in
    {runtime} Communication Efficiency, so read the two together. If useful work
    runs while the first thread is in MPI, see Useful Work during MPI.


Validation so far
-----------------

A script read the ``.prv`` directly: useful time is state 1, and the MPI intervals
are the events 50000001 to 50000005 of the first thread of each task. The streams
of each device were flattened using the labels of the ``.row`` file, and each
unit was intersected with the MPI intervals of its task.

.. list-table::
   :header-rows: 1

   * - Trace
     - Application
     - Outer
     - Inner
     - Inner outside MPI
     - Useful during MPI (%)
     - Share of useful time
   * - BT-MZ A, MPI+OpenMP
     - 47.12
     - 68.23
     - 69.06
     - 69.06
     - 100.00
     - 0.00%
   * - XSHELLS chop1, MPI+CUDA
     - 32.74
     - 66.60
     - 49.15
     - 43.01
     - 114.27
     - 12.49%
   * - Tsunami-HySEA chop, MPI+CUDA
     - 22.33
     - 45.61
     - 48.95
     - 24.11
     - 203.01
     - 50.74%
   * - CloverLeaf 4p+4d, MPI+CUDA
     - 41.21
     - 91.46
     - 45.05
     - 44.99
     - 100.15
     - 0.15%
   * - CloverLeaf 8p+8d, MPI+CUDA
     - 37.98
     - 89.01
     - 42.67
     - 42.58
     - 100.22
     - 0.22%
   * - CloverLeaf 16p+16d, MPI+CUDA
     - 32.23
     - 83.10
     - 38.78
     - 38.68
     - 100.26
     - 0.26%
   * - SOD2D 1 node, MPI+HIP
     - 22.13
     - 64.24
     - 34.46
     - 34.46
     - 100.00
     - 0.00%
   * - SOD2D 4 nodes, MPI+HIP
     - 27.04
     - 70.81
     - 38.19
     - 38.19
     - 100.00
     - 0.00%
   * - SOD2D 8 nodes, MPI+HIP
     - 28.46
     - 74.37
     - 38.27
     - 38.27
     - 100.00
     - 0.00%

Application, Outer, and Inner match BasicAnalysis for BT-MZ, XSHELLS,
Tsunami-HySEA, SOD2D, and the CloverLeaf runs with 4 and 8 processes, and the useful
times match the raw data. In all the traces, the overlap comes from the devices:
Host threads have no useful time during MPI.

In a scan of 45 hybrid traces, measured per stream before the fix in ``ed5d01f``,
overlap above 1% appeared in only 3, and no trace had Inner PE above 100%. The highest Inner LB was 100.12%
(``lmp_mpi_omp-mn4``). So the mechanism is measured, but no real trace has been
seen where overlap takes Inner PE above 100%.

The isolated OpenMP metrics measure something else: on BT-MZ A they give 27.30%
against 69.06%, so they are not a split of the inner PE.


Open questions
--------------

1. **Was the formulation of Section III.B of the paper finished?** If so, read it
   before fixing the definition of Useful Work during MPI.
2. **MPI called from other threads.** The definition uses the first thread, like
   the current model. Task-based codes may call MPI from any thread.
3. **What was hybrid_UM_BO designed to show?** Its name suggests unbalanced MPI.
4. **MPI+GPU.** Is there a useful equivalent of the Load Balance split?
