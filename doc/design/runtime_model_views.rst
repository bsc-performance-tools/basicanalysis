Views of the Hybrid Parallel Runtime Model
==========================================

:Status: Implemented on this branch (option A); open questions below
:Date: 2026-11-02 (updated 2026-11-03)
:Branch: ``feature/runtime-model-views``
:Scope: Parallel Runtime Model of the interactive report for MPI+X traces

The report should present the hybrid multiplicative model from four
perspectives: Application, Outer level, Inner level, and Other. Other isolates
the useful work that runs during MPI, and the report explains why the inner
level can exceed 100%.


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


Decision: option A
------------------

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * -
     - A: keep MPI, add Other (**chosen**)
     - B: change what MPI is blamed for
   * - Idea
     - MPI PE as in the paper; overlap has its own factor
     - Overlapped useful time is not blamed on MPI
   * - MPI PE values
     - Unchanged
     - Change for codes with overlap
   * - Product
     - Application = Outer x Inner x Other
     - Application = Outer x Inner
   * - Published results
     - Comparable
     - Not comparable for codes with overlap

Option A is exact and measurable, and shows the amount of overlap. Option B needs
a formulation for the time other threads wait for MPI, and could be a later step.


Definition of the views
-----------------------

Let :math:`U^{M}_{i,j}` be the useful time of thread :math:`j` of process
:math:`i` while the first thread of the process is in MPI, and
:math:`U^{O}_{i,j} = U_{i,j} - U^{M}_{i,j}`.

.. math::

   \text{Inner PE (outside MPI)} =
       \frac{\sum_{i,j} U^{O}_{i,j}}{\sum_i O_i t_i} \le 100\%

   \text{Other} =
       \frac{\sum_{i,j} U_{i,j}}{\sum_{i,j} U^{O}_{i,j}} \ge 100\%

   \text{Hybrid PE} = \text{MPI PE}
       \times \text{Inner PE (outside MPI)} \times \text{Other}

.. list-table::
   :header-rows: 1
   :widths: 18 52 30

   * - View
     - Shows
     - Above 100%
   * - Application
     - Hybrid Parallel Efficiency, Load Balance, Communication
     - No
   * - Outer
     - MPI Parallel Efficiency and its factors
     - No
   * - Inner
     - Inner PE (outside MPI), and the Load Balance and Communication ratios
     - PE no; Load Balance can
   * - Other
     - Useful work during MPI
     - Always 100% or more

In MPI+GPU, a unit is a Host thread or a physical device, and
:math:`U^{M}` of a device is its flattened useful time during the MPI calls of
the first thread of its process. Other does not depend on the number of units.
The limit of 100% for Inner PE (outside MPI) assumes the same number of units in
every process, because the MPI metrics are computed over the ranks.

Other applies to Parallel Efficiency only. The Inner Load Balance and
Communication ratios keep their current definition, so with overlap their product
is Inner PE (outside MPI) x Other, not Inner PE (outside MPI). The view must
say so.

The table with the nine metrics stays, because the paper recommends both paths.
Reading the signals together:

.. list-table::
   :header-rows: 1

   * - Inner LB
     - Inner Comm
     - Other
     - Meaning
   * - Above 100%
     - Below 100%
     - 100%
     - Compensation: non-useful time inside some processes causes MPI imbalance
   * - Above 100%
     - About 100%
     - Above 100%
     - Useful work continues during MPI


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
    runs while the first thread is in MPI, see the Other view.


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
     - Inner today
     - Inner (outside MPI)
     - Other
     - Useful during MPI
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

Application, Outer, and Inner today match BasicAnalysis for BT-MZ, XSHELLS,
Tsunami-HySEA, SOD2D, and the CloverLeaf runs with 4 and 8 processes, and the useful
times match the raw data. In all the traces, the overlap comes from the devices:
Host threads have no useful time during MPI.

In a scan of 45 hybrid traces, measured per stream before the fix in ``ed5d01f``,
overlap above 1% appeared in only 3, and no trace had Inner PE above 100%. The highest Inner LB was 100.12%
(``lmp_mpi_omp-mn4``). So the mechanism is measured, but no real trace has been
seen where overlap takes Inner PE above 100%.

The isolated OpenMP metrics are not suitable for the Inner view: on BT-MZ A they
give 27.30% against 69.06%, which would leave a residual of 253%.


Implementation
--------------

1. **Raw data.** Obtain :math:`U^{M}`, preferably with a paramedir
   configuration. Otherwise, from a filtered trace, as the I/O requests already
   do. To be evaluated: the control window is at task level (``Thread i``) and
   the data at thread level, and MPI+GPU needs the flattened intervals.
2. **Metrics.** Inner PE (outside MPI) and Other in ``hybridmetrics.py``,
   ``definitions.yaml``, the CSV files, and tests. Non-Avail outside MPI+X.
3. **Report.** The four views in the Runtime Analysis section
   (``report/sections/runtime_analysis.py``), keeping the nine metrics.
4. **Documentation.** User Guide chapters 5, 6, and 7, and the new text.


Open questions
--------------

1. **Was the formulation of Section III.B of the paper finished?** If so, read it
   before fixing the definition of Other.
2. **MPI called from other threads.** The definition uses the first thread, like
   the current model. Task-based codes may call MPI from any thread.
3. **Labels.** How are the views labelled for each runtime?
4. **Name of the view.** "Other" is general. Should the report use a descriptive
   label such as "Useful work during MPI"?
