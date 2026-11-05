Hybrid Model without the Hierarchical Limitation
================================================

:Status: Implemented on this branch, in new rows, not merged into ``devel`` until tested
:Date: 2026-11-05
:Branch: ``feature/non-hierarchical-model``, from ``feature/runtime-model-views``
:Scope: Parallel Runtime Model of the MPI+X traces

The hybrid model of Giménez et al., ISPDC 2020, was designed for hierarchical codes:
MPI is the outer level, and the threads are blocked or idle during MPI. Section III.B
names the other cases: tasks calling MPI from any thread, a parallel do with different
threads calling MPI, and MPI+CUDA with kernels overlapping communication. It gives the
rule, "we have to blame MPI only for the MPI time plus the time other threads are
waiting", and says that the formulation was in progress.

Definition
----------

:math:`M_i` is the union of the MPI calls of the Host threads of process :math:`i`, and
:math:`t_i` its units: threads, and in MPI+GPU the physical devices. :math:`U^M_{i,j}` is
the useful time of unit :math:`j` during :math:`M_i`. A unit is blamed for :math:`M_i`
except while it does useful work:

.. math::

   O'_i = (T - |M_i|) + \frac{1}{t_i} \sum_j U^M_{i,j}

The rows use :math:`O'_i` in place of :math:`O_i`:

.. math::

   MPI\_PE = \frac{\overline{O'}}{T}
   \qquad
   MPI\_LB = \frac{\overline{O'}}{\max_i O'_i}
   \qquad
   MPI\_Comm = \frac{\max_i O'_i}{T}

The inner rows stay Hybrid / MPI, and all the multiplications hold. Hybrid values do not
change. The mean follows the classic model: weighted by threads in CPU-based executions,
and over the MPI ranks in MPI+GPU.

With MPI on the first thread and no useful work during it, :math:`O'_i = O_i`.

Implementation
--------------

``rawdata.non_hierarchical_outside_mpi`` reads the timeline of
``cfgs/mpi_calls_intervals.cfg``, which has every thread, and the useful timelines
already used for Useful Work during MPI. Units are counted from the timeline and not
from the ``.row`` file: ``unbalancedMPI.row`` describes 6 processes and the trace has 5.
``hybridmetrics.non_hierarchical_factors`` gives the rows ``nh_*``. The classic rows do
not change. The new rows are in the CSV and the standard output. The report shows them
below the classic rows only when one differs by 0.05 points or more
(``metrics/non_hierarchical.py``), so a hierarchical code does not repeat them.

Results
-------

Measured with ``-pop-model classic``.

.. list-table::
   :header-rows: 1

   * - Trace
     - Hybrid PE
     - MPI PE classic / new
     - Inner PE classic / new
   * - BT-MZ A
     - 47.12
     - 68.23 / 68.23
     - 69.06 / 69.06
   * - BT-MZ B
     - 54.25
     - 99.08 / 99.08
     - 54.75 / 54.75
   * - SOD2D 1 node, MPI+HIP
     - 22.13
     - 64.24 / 64.24
     - 34.46 / 34.46
   * - CloverLeaf 4p+4d chop1, MPI+CUDA
     - 46.42
     - 98.91 / 98.95
     - 46.93 / 46.91
   * - XSHELLS chop1, MPI+CUDA
     - 32.74
     - 66.60 / 70.69
     - 49.15 / 46.31
   * - Tsunami-HySEA chop, MPI+CUDA
     - 22.33
     - 45.61 / 56.94
     - 48.95 / 39.21

The six traces of the paper, BT-MZ, and SOD2D differ from the classic rows by at most
0.003 points.

MPI from any thread has no real trace: a scan of 214 traces up to 250 MB found no MPI
event on a thread other than the first. A controlled trace with 2 processes of 2 threads
gives the values computed by hand: mean 775, maximum 850, MPI LB 91.18, MPI Comm 85.
The classic code gives MPI LB 86.11 and MPI Comm 90: ``parse_outside_mpi_stats`` takes a
second thread with MPI as if it were another process.

Limits
------

* Inner Load Balance or Communication can still exceed 100%. They compare two maxima, and
  MPI is still blamed first. The controlled trace gives inner Communication 105.88.
* Inner PE cannot exceed 100% with equal units per process. In MPI+GPU with unequal units,
  the mean over the ranks does not guarantee it.
* Idle time during MPI is blamed on MPI. In task-based codes it can have another cause, for
  example no ready tasks.

Open questions
--------------

1. Do the new rows replace the classic ones?
2. Does Useful Work during MPI stay as a diagnostic?
3. Real codes with MPI on several threads to validate the definition.
