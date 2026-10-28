Device Computation Scalability: Work and Throughput
===================================================

:Status: Implemented on ``feature/device-scalability`` (2026-10-28); the
         definitions are in the User Guide (chapter 6, *Device Work and
         Throughput Scalability* and *Kernel contributions*).
:Date: 2026-10-28
:Branch: ``feature/device-scalability`` (from ``devel`` 08fc95b)
:Scope: The Device side of the Host/Device (TALP) model, for Extrae
        (MPI+CUDA, MPI+HIP, GPU without MPI) and nsys2prv traces

This document proposes two additions that explain *why* the Device
Computation Scalability is lower or higher than 100 %:

1. two submetrics, **Device Work Scalability** and **Device Throughput
   Scalability**, whose product is the Device Computation Scalability, so
   the multiplicative Host/Device model is kept;
2. a **per-kernel contribution table**, a diagnostic that names the kernels
   that cause the change of the device time.


Context
-------

On the Host, Computation Scalability is split into Instruction, IPC, and
Frequency Scalability, from the hardware counters. On the Device there is
no such split today: the Device Computation Scalability compares only the
aggregate useful device time :math:`U` (the kernel time of all devices)
with the reference execution :math:`0`:

.. math::

   DevCompScal(n) = \frac{U(0) \cdot r(n)}{U(n)}

where :math:`r(n)` is the work ratio of the scaling model: 1 in strong
scaling, the device ratio in weak scaling, and the device workload ratio in
the user-defined workload mode (see ``workload_scaling.rst``). The Device
Global Efficiency is:

.. math::

   DevGlobalEff = DevParallelEff \times DevCompScal

A low Device Computation Scalability can mean that the devices do more
work (more or larger kernels) or that they do the same work more slowly
(smaller kernels, launch latency, lower occupancy, lower clock). The
analyst cannot tell the two apart from the time alone.

**Decisions of 2026-10-28:**

* Both additions: the Work × Throughput submetrics and the per-kernel
  table.
* The work measure depends on the trace source (see `Work measure`_).
* The submetrics go in the Host/Device model, because they keep it
  multiplicative.

**Decisions of 2026-10-28 (on the open questions):**

* The third level (Issue × Frequency Scalability) is included for nsys2prv
  traces with GPU metrics.
* Kernel families: remove the tile suffix, for the moment (not
  configurable).
* The Tensor indicator is left for later.


What the traces contain
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 46 27 27

   * - Information
     - Extrae (CUDA)
     - nsys2prv
   * - Kernel name and duration on each GPU stream
     - yes (``63000006``)
     - yes (``63000006``)
   * - Grid and block size of each kernel
     - blocks per grid ``63000011``, threads per block ``63000012``
     - ``9101``–``9103`` (grid X, Y, Z), ``9104``–``9106`` (block X, Y, Z)
   * - Registers per thread, shared and local memory
     - no
     - ``9107``–``9110``
   * - GPU hardware metrics (SM Issue, Tensor Active, clock, DRAM, ...)
     - no (PAPI counters are on the Host only)
     - sampled on the ``Metrics GPU<n>`` row, ``9400``–``9429``

In Extrae 5.1.3 (``cuda_wrapper_cupti.c``), the blocks per grid are
``gridDim.x × gridDim.y × gridDim.z`` and the threads per block
``blockDim.x × blockDim.y × blockDim.z``, taken at the launch.

A kernel is the interval between a non-zero value of ``63000006`` on a
stream row and the next zero on the same row. The grid and block events are
written with the start of the kernel. In nsys2prv traces, event ``63000007``
is an NCCL kernel; in Extrae traces it is the source line of the kernel.


Proposed decomposition
----------------------

With a work measure :math:`W` of the Device (the total over all devices),
the Device Computation Scalability is split exactly:

.. math::

   DevCompScal(n) =
   \underbrace{\frac{W(0) \cdot r(n)}{W(n)}}_{DevWorkScal}
   \times
   \underbrace{\frac{W(n) / U(n)}{W(0) / U(0)}}_{DevThroughputScal}

* **Device Work Scalability**: the work of the reference execution, scaled by
  the work ratio of the scaling model, divided by the work of execution
  :math:`n`. It is 100 % when the devices do the work expected by the
  scaling model; below 100 % they do more work (replicated or redundant
  work, halo exchanges, more kernels).
* **Device Throughput Scalability**: the work done per second of kernel
  time, relative to the reference. Below 100 %, the same work runs more
  slowly.

The work ratio :math:`r(n)` goes to Work Scalability only, as the
instruction ratio does on the Host. :math:`U` stays the useful device time
that BasicAnalysis computes today; only :math:`W` is new. Throughput
Scalability is computed as :math:`DevCompScal / DevWorkScal`, so the
product is exact also when :math:`U` excludes overlapping kernels.

For nsys2prv traces with GPU metrics, the throughput is split once more
(see `Third level (nsys2prv with GPU metrics)`_):

.. code-block:: text

   DEVICE Global efficiency
   -- Device Parallel efficiency
      == Device Load balance
      == Device Communication efficiency
      == Device Orchestration efficiency
   -- Device Computation scalability
      == Device Work scalability
      == Device Throughput scalability
         -- Device Issue scalability       (nsys2prv with GPU metrics)
         -- Device Frequency scalability   (nsys2prv with GPU metrics)


Work measure
------------

Three measures were tested on the traces:

.. list-table:: Change from the reference trace
   :header-rows: 1
   :widths: 40 30 30

   * - Measure
     - CloverLeaf 4 → 32 GPUs (strong)
     - vLLM b1 → b256 (same GPU)
   * - Kernel time :math:`U`
     - × 1.33
     - × 8.41
   * - Number of kernels
     - × 9.76
     - × 1.11
   * - GPU threads launched, :math:`\sum blocks \times threads`
     - × 1.004
     - × 14.81
   * - Issued instructions, :math:`\int SM\,Issue \cdot clock\,dt`
     - —
     - × 26.86

**The number of kernels is not a work measure.** In strong scaling every
GPU runs the same kernels on a smaller subdomain, so the number of kernels
grows with the number of GPUs (× 9.76 with 8 times the GPUs) while the work
is the same.

**Proposal: the measure depends on the trace source**, and the same measure
is used for all the traces of an analysis:

``Issued instructions`` (nsys2prv traces with the GPU metrics)
   .. math::

      W = \sum_{devices} \int SM\,Issue(t) \cdot f_{GPC}(t)\, dt

   SM Issue is the percentage of cycles in which the SMs issue an
   instruction, averaged over the SMs, and :math:`f_{GPC}` the GPC clock. The
   product is proportional to the instructions issued: the constant (number
   of SMs, issue width) cancels in the ratio when the GPU model is the same.
   SM Issue is 0 outside the kernels.

``GPU threads launched`` (all other traces)
   .. math::

      W = \sum_{kernels} blocks \times threads\ per\ block

   It measures the work when each GPU thread processes a fixed amount of
   data, as in most hand-written kernels. See `Limitations`_.

If one trace of the analysis has no GPU metrics, all traces use GPU threads
launched, and BasicAnalysis prints a note.

The integral must be clock-weighted. Without the clock, the work of vLLM
grows × 30.27 instead of × 26.86 (11 % error), because the clock while
issuing drops from 1934 to 1717 MHz at b256.


Third level (nsys2prv with GPU metrics)
---------------------------------------

With the issued-instruction measure, the throughput :math:`W/U` is the
product of the mean SM Issue during the kernels and the mean clock while
issuing:

.. math::

   \frac{W}{U} =
   \underbrace{\frac{\int SM\,Issue\,dt}{U}}_{\overline{Issue}}
   \times
   \underbrace{\frac{\int SM\,Issue \cdot f_{GPC}\,dt}{\int SM\,Issue\,dt}}_{\overline{f}}

so that

.. math::

   DevThroughputScal = \underbrace{\frac{\overline{Issue}(n)}
   {\overline{Issue}(0)}}_{DevIssueScal}
   \times
   \underbrace{\frac{\overline{f}(n)}{\overline{f}(0)}}_{DevFreqScal}

This is the Device analogue of IPC × Frequency Scalability. Without the GPU
metrics, the two rows are *Non-Avail*.


Per-kernel contribution table
-----------------------------

For each trace :math:`n` other than the reference, the kernels are matched
by name with the reference trace, and the table lists the kernels with the
largest share of the change of the device time:

.. math::

   Share_k(n) = \frac{U_k(n) - U_k(0) \cdot r(n)}{U(n) - U(0) \cdot r(n)}

The time of the reference is scaled by :math:`r(n)`, so the table explains
the gap from the ideal of the scaling model. The shares add up to 100 %.

Proposed columns: kernel (or family), share, calls (reference → trace),
time (reference → trace), threads launched ratio, time per thread ratio.
Top 10 kernels in the report and on the standard output, plus an "Other
kernels" row. All kernels in a CSV (``device_kernels.csv``).

**Kernel families.** Libraries such as cuBLAS choose a different kernel for
each problem size: between b1 and b256, vLLM runs 53 kernel families but
the ``nvjet_sm90_tst_*`` matrix-multiply kernels change names (for example
``..._256x8_64x6_4x1_v_bz_TNT`` at b1, ``..._192x192_64x4_2x1_v_bz_coopB_TNN``
at b256). Matched by full name, they appear as kernels that disappear and
kernels that are new. The proposal is to group the names by removing the
tile suffix (the part from the first ``_<n>x<m>``), which gives one
``nvjet_sm90_tst`` row. Kernels whose name has no tile suffix are not
changed.


Validation with the prototype
-----------------------------

The prototype reads the kernels of the stream rows and the GPU metrics of
the ``Metrics GPU<n>`` row (each sample held until the next one, as the
Paraver cfgs do).

* The sum of the kernel durations equals the BasicAnalysis useful device
  time for CloverLeaf (10.686 s and 11.154 s on 4 and 8 GPUs). For vLLM it
  is 0.5 % higher (6.768 s against 6.736 s), because kernels on different
  streams overlap.
* The integrals of SM Issue and of clock × GR Active equal those of
  BasicAnalysis (``rawdata.csv``).

CloverLeaf (Extrae, MPI+CUDA, strong scaling, reference 4 GPUs)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Work measure: GPU threads launched (:math:`3.311 \cdot 10^{11}` at 4 GPUs).

.. list-table::
   :header-rows: 1

   * - GPUs
     - Device Computation Scal.
     - Device Work Scal.
     - Device Throughput Scal.
   * - 8
     - 95.80 %
     - 99.93 %
     - 95.87 %
   * - 16
     - 87.51 %
     - 99.74 %
     - 87.73 %
   * - 32
     - 75.25 %
     - 99.59 %
     - 75.56 %

The devices do the same work; the loss is throughput. The per-kernel table
(4 → 32 GPUs) shows where: about 80 % of the extra 3.5 s of kernel time
comes from 8 ``par_ranged1d_kernel`` kernels (1-D kernels, probably the
halo updates), called 12–14 times more often and 1.9–3.9 times slower per
thread. The main ``par_ranged2d_kernel`` kernels have the same threads and
take 7–11 % more time.

vLLM (nsys2prv, one GPU, batch size 1 → 256)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Work measure: issued instructions (× 26.86).

.. list-table::
   :header-rows: 1

   * - Work ratio
     - Device Computation Scal.
     - Device Work Scal.
     - Device Throughput Scal.
     - Issue Scal.
     - Frequency Scal.
   * - strong (:math:`r = 1`)
     - 11.85 %
     - 3.72 %
     - 318.27 %
     - 358.66 %
     - 88.74 %
   * - ``--workload 1,256``
     - 3033.25 %
     - 953.05 %
     - 318.27 %
     - 358.66 %
     - 88.74 %

The mean SM Issue during the kernels grows from 3.08 % to 11.03 %, and the
clock while issuing drops from 1934 to 1717 MHz. With 256 times the
requests the GPU issues 26.86 times the instructions, so the work per
request is about 9.5 times smaller at b256 (Work Scalability 953 %).

With GPU threads launched instead, the work grows × 14.81 (Work 1728 %,
Throughput 176 % with ``--workload 1,256``): the threads launched
underestimate the matrix multiplications (see `Limitations`_).

Per-kernel table (families): ``device_kernel`` explains 53.7 % of the
change (0.45 → 27.38 s), ``nvjet_sm90_tst`` 36.3 % (5.70 → 23.88 s),
``act_and_mul_kernel`` 3.9 %, ``fused_add_rms_norm_kernel`` 3.4 %.

Tensor Active × clock grows × 91.37: it could be shown as an indicator
(relative Tensor work), not as a factor, because it depends on the
precision used.


Placement
---------

* **Standard output and** ``talp_metrics.csv``: the new rows below Device
  Computation Scalability in the Device table; only with two or more traces.
* **Report**: the same rows in the Host/Device model view (table and
  plots), with a tooltip that names the work measure used. The per-kernel
  table as the card *Which kernels change the device time?* in the Scaling
  view, below the Device Computation Scalability plot, with a selector for
  the execution (the largest one by default); the printable version shows
  every execution. (A first version put it in the secondary Device view,
  which the main navigation does not show.)
* **CSV**: ``device_kernels.csv`` with all kernels (families) and traces.
* **Raw data**: the work measure per trace in ``rawdata.csv``
  (``device_work``, ``device_work_measure``), and for nsys2prv the
  integrals :math:`\int SM\,Issue \cdot f_{GPC}\,dt` and
  :math:`\int SM\,Issue\,dt`.
* **User Guide**: chapter 6 (definitions), chapter 7 (report view),
  chapter 8 (outputs), chapter 9 (limitations).

The data comes from one new pass over the trace (kernels with their grid
and name) and, for nsys2prv, one new cfg for :math:`\int SM\,Issue \cdot
f_{GPC}\,dt` like the existing ``hwc_gpc_clock.cfg``.


Limitations
-----------

* **Fixed grids.** Kernels launched with a fixed grid (grid-stride loops,
  reductions) launch the same threads whatever the data size, so the threads
  launched do not follow the work. In CloverLeaf, ``par_reduce_kernel``
  launches one fixed grid per GPU; its share of the threads is negligible.
* **Library kernels.** Libraries (cuBLAS, cuDNN, attention kernels) change
  the tile size and the work per thread with the problem size. In vLLM the
  threads launched grow × 14.81 when the issued instructions grow × 26.86.
* **Same GPU model.** Both measures compare executions on the same GPU
  model; issued instructions and threads are not comparable across
  architectures.
* **SM Issue is a sampled average.** The instructions are estimated from
  samples (every 100 µs in the vLLM traces); kernels shorter than the
  sampling period are averaged with their neighbours.
* **Overlapping kernels.** Kernels on different streams that run at the
  same time count once in :math:`U` and fully in :math:`W`; this is part of
  the throughput.


Implementation
--------------

* ``devicework.py``: kernel scan of the GPU stream rows (CUDA ``63000006``
  and HIP ``63500006``, with the blocks and threads at ``+5`` and ``+6``;
  nsys2prv grid and block ``9101``–``9106``), kernel families and short
  names for the tables, the submetrics, and the kernel contributions.
* ``cfgs/nsys2prv/hwc_sm_issue_clock.cfg``: integral of SM Issue × GPC clock.
* The prototype and the implementation give the same values: CloverLeaf
  4 → 8 GPUs 95.80 % = 99.93 % × 95.87 %; vLLM ``--workload 1,256``
  3033.25 % = 953.05 % × 318.27 %, with 318.27 % = 358.66 % × 88.74 %.
  The staged workflow gives the same results.
* In the table of the report and on the standard output, the kernels of
  Extrae traces are named without the signature; kernels with the same name
  (lambda kernels) get the function that defines the lambda
  (``clover::par_ranged1d_kernel (clover_pack_message_left)``) or a number.

Open questions
--------------

1. **Tensor indicator.** Left for later (decision of 2026-10-28).
2. **HIP.** Extrae 5.1.3 records the same blocks and threads for HIP
   (``hip_wrapper_roctracer.c``: ``hipLaunchKernel``,
   ``hipModuleLaunchKernel``, ``hipLaunchCooperativeKernel``); the event
   codes in a HIP trace must still be checked with a real trace.
