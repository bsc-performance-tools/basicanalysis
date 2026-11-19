GPU Assessment Metrics from the vLLM POP Assessment
===================================================

:Status: Proposal, for review by the team
:Date: 2026-11-19
:Branch: ``feature/gpu-assessment-metrics`` (to create from ``devel``)
:Source: Jesús Labarta, *POP3_AR_078 vLLM efficiency study*
         (``Multiverse_assessment.v6``, 74 slides, nsys2prv traces of
         PyTorch and vLLM, three Llama models, batch sizes 1 to 512, one
         H100)
:Related: ``workload_scaling.rst``, ``device_computation_scalability.rst``
          (branch ``feature/device-scalability``)

This document compares the metrics that Jesús used in his assessment of
vLLM with the metrics of BasicAnalysis, and proposes, in order, what to add
so that BasicAnalysis produces his tables and the indicators he used to
explain them.


Context
-------

The assessment explains the throughput, time to first token and time per
output token of the inference with the Device side of the TALP
heterogeneous model. The tables of the assessment (slides 15 to 24 and 48
to 53) were *"manually computed: paraver cfgs → excel"*, for the full step
and for the decode phase. The losses are then explained with timelines and
statistics of kernels (computation) and of the kernel launches
(orchestration).

His table has five blocks:

1. **Model**: Total, Parallel, Load Balance, Communication, Orchestration
   Efficiency and Computation Efficiency scaled by the batch size.
2. **Checks**: Normalized total, Elapsed, Time based efficiency, Kernel
   time, Computation Efficiency not scaled.
3. **Scaled counts**: TC ops, Bytes read, Bytes written, SM issues, relative
   to the reference and scaled by the batch size.
4. **Scaled averages**: TC active, BW read, BW write, SM issue rate, active
   SMs, relative to the reference.
5. **Averages**: the same five quantities in %.


What BasicAnalysis has today
----------------------------

.. list-table::
   :header-rows: 1
   :widths: 35 40 25

   * - Assessment
     - BasicAnalysis
     - Where
   * - Total, Par., LB, Comm., Orch. Eff.
     - Device Global, Parallel, Load Balance, Communication, Orchestration
       Efficiency
     - ``devel``
   * - Comp. Eff. (scaled by bs)
     - Device Computation Scalability with ``--workload``
     - ``devel``
   * - Elapsed
     - Runtime
     - ``devel``
   * - Averages (TC, BW read/write, SM issue, active SMs)
     - Tensor Core Activity, DRAM Read/Write Bandwidth, SM Utilization, SM
       Coverage (weighted by GR Active)
     - ``devel``
   * - Scaled count of SM issues
     - Device Instruction Scalability (with IPC and Frequency)
     - ``feature/device-scalability``
   * - Kernel signatures (slide 27)
     - Table of kernel families ("Which kernels change the device time?")
     - ``feature/device-scalability``
   * - Normalized total, Time based eff., Kernel time, Comp. Eff. not
       scaled, scaled counts of TC and bytes, scaled averages
     - —
     - new (step 1)
   * - Phases (full step, prefill, decode)
     - — (only by cutting the trace)
     - new (step 3)
   * - Kernels in flight, inter-launch time, host time split, CUDA graphs
     - —
     - new (step 4)
   * - Statistics per kernel and per class of kernel
     - —
     - new (step 5)
   * - Paraver views of the assessment (histograms, profiles, sampled
       timelines)
     - only ``useful_duration.cfg`` in ``cfgs-report/``; the GPU cfgs of
       BasicAnalysis compute numbers, they are not views
     - new (see `Paraver views for GPU traces`_)

The averages may not be the same quantity: ours are weighted by GR Active
(average while the GPU is active), and his normalization is the open
question 1.

**Possible error in the assessment.** In the table of slide 15, vLLM Depth
bs=1 has a Time based efficiency of 2.995; from its elapsed time it is
4560116 / 1972937 = 2.311, which agrees with the Normalized total (2.316).


Proposal, in order
------------------

Each step is usable on its own and is validated with the vLLM traces before
the next one.

Step 1: complete the model table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All quantities come from data that BasicAnalysis already computes (kernel
time and counter integrals). With :math:`c` a trace, :math:`r` the
reference, :math:`T` the elapsed time, :math:`G = \sum_i G_i` the kernel
time of all devices, :math:`N` the number of devices and :math:`w` the
workload given with ``--workload`` (1 when not given):

* **Throughput speedup** (his *Time based eff.*):
  :math:`S_c = \frac{T_r}{T_c} \cdot \frac{w_c}{w_r}`.
* **Normalized total**: :math:`DGE_c / DGE_r`. Since
  :math:`DGE_c = \frac{G_r}{N_c\,T_c}\,\frac{w_c}{w_r}`, the Normalized
  total equals :math:`S_c \cdot N_r / N_c`: with the same number of devices
  it is the same number as the throughput speedup. In the assessment both
  rows differ slightly because the values come from different runs. We
  propose to show only the throughput speedup, and to say in the guide why
  the Normalized total is not needed.
* **Kernel time** :math:`G_c` (µs), and the **Device Computation
  Scalability not scaled** :math:`G_r / G_c` next to the scaled one when
  ``--workload`` is given.
* **Scaled counts** of a counter :math:`X` with integral :math:`I_X` (the
  Paraver integral of the counter, as in the GPU Hardware Counters view):
  :math:`C_X = \frac{I_{X,r}}{I_{X,c}} \cdot \frac{w_c}{w_r}`, for Tensor
  Active (TC ops), DRAM Read (bytes read) and DRAM Write (bytes written).
  Above 100 % the case does less of that work per unit of workload than the
  reference. They are indicators next to the Device Computation
  Scalability, not factors of it. SM issues is already the Device
  Instruction Scalability of step 2.
* **Scaled averages** :math:`A_{X,c} / A_{X,r}` of the five averages,
  once open question 1 fixes the normalization.

Where: Heterogeneous Model view (rows of the Device table and a "Checks"
table), ``device_metrics.csv``, ``results.json``. Only for GPU traces, and
the scaled quantities only with two or more traces.

Step 2: bring ``feature/device-scalability`` to ``devel``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The branch splits the Device Computation Scalability as the CPU model:
Device IPC × Instruction × Frequency Scalability with GPU counters (IPC
split into Coverage × Active Issue Rate), Work × Throughput without them,
and adds the table of kernel families. It is his "scaled count of SM
issues" and close to his kernel signatures. It needs the review and
approval of the team, then a merge of ``devel`` into it (the branch is from
2026-11-05) and the validation with the vLLM traces of step 1.

Step 3: analysis per NVTX region
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

His tables are given for the full step and for the decode phase. The
nsys2prv traces have the NVTX ranges of the benchmark (event 9600, values
such as ``rep0_full``, ``rep0_ttft``, ``warmup_0``). Proposal: an option
``--region <NVTX label>`` that restricts all the metrics to the time
intervals of that range (one or several instances), computed as today on
the trace cut to those intervals. Decode would be ``rep0_full`` without
``rep0_ttft`` (open question 2). Today the user has to cut the trace by
hand in Paraver.

Step 4: orchestration indicators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The assessment explains the low Orchestration Efficiency at small batch
sizes with the kernel launches. The nsys2prv traces have what is needed:
the CUDA calls on the host threads (event 63000000, values such as
``cudaLaunchKernel``, ``cudaGraphLaunch``), the kernels on the streams, the
communication lines from each launch to its kernel, and the Correlation ID
(event 9200).

* **Kernels in flight**: number of kernels launched and not finished, as a
  function of time; report its average and the % of the time the queue is
  empty while the host is running (slide 33: "queue builds and drains",
  "unable to fill the queue").
* **Inter-launch time**: time between consecutive kernel launch calls of a
  host thread, with the **kernel duration**; report median and mean of both
  and the **% of kernels (and of kernel time) shorter than the median
  inter-launch time** (slide 37, "twilight zone"). When kernels are shorter
  than the inter-launch time, the device waits for the host and the
  Orchestration Efficiency falls.
* **Host time split**: % of the host time in the framework (outside CUDA
  calls), in launch calls, in synchronization and memory calls, and in
  graph calls (slide 45: 86.95 % framework, 12.05 % launches).
* **CUDA graphs**: number of graph instantiations and launches, and kernels
  per graph launch (slides 44 to 55).

Where: Heterogeneous Model view, below the Device table, as indicators of
the Orchestration Efficiency; a Paraver cfg for the kernels-in-flight
timeline (deeper analysis in the analyzer).

Step 5: statistics per kernel and per class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Per kernel family** (families as in step 2): number of instances, % of
  kernel time, average duration, and the counters averaged over the time
  of the kernel (TC active, DRAM read/write, active SMs). The averages are
  approximate: the counters are sampled (every 100 µs in these traces) and
  not synchronized with the kernels (slide 27). Slide 66: these statistics
  "would be useful for kernel engineering".
* **Per class** (GEMM, attention, data reshuffle, other) by name patterns
  in a configurable file, with the same columns, compared across traces
  (slides 28 and 29).

Where: GPU Hardware Counters view and ``device_kernels.csv``.


Paraver views for GPU traces
----------------------------

A second result of the assessment, as important as the metrics, is the set
of Paraver views used to explain them. On GPUs the granularity is very fine
(kernels of a few µs to a few hundred µs, millions of them in a run), so a
plain timeline shows little: at the zoom of a full step every pixel holds
hundreds of kernels. The assessment uses three kinds of views that solve
this:

* **histograms** (2D analyzer with bins of duration), such as the kernel
  duration and the inter-launch time between 0 and 200 µs;
* **profiles per kernel** (2D analyzer with one row per kernel name and
  statistics as columns), such as the kernel signatures;
* **timelines sampled in windows** (for example the Parallel Efficiency
  every 250 µs), which turn the fine grain into a curve.

These views are hard to build by hand in Paraver (event codes that change
between nsys2prv versions, semantic functions, bins, colours), and they are
also hard to read when the trace is large. BasicAnalysis can provide them
in two ways:

1. **cfgs ready to open** in ``cfgs-report/``, rewritten for each trace
   with its event codes (as ``nsys2prvevents.py`` does today for the metric
   cfgs), opened from the report and from the analyzer (Phase 3 of
   ``desktop_app.rst``), next to the metric they explain;
2. **the histograms and profiles as plots** in the report and the
   analyzer: BasicAnalysis runs the 2D analyzer of the cfg with paramedir
   and plots the result (zoomable in the analyzer, log scale for
   durations), so the analyst sees the distribution without opening the
   trace, and opens Paraver only to go to the time intervals.

Views of the assessment
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 12 34 10 14

   * - View
     - Kind
     - Explains
     - Slides
     - BasicAnalysis
   * - NVTX ranges (structure: iterations, prefill, decode)
     - timeline
     - phases; step 3 (regions)
     - 10–12
     - new
   * - CUDA calls on the host and kernels on the streams, with the
       launch → kernel lines
     - timeline
     - Orchestration: who waits for whom
     - 10, 33–36, 54
     - new (our cfgs give only numbers)
   * - Kernels coloured by name
     - timeline
     - structure, different kernels per case
     - 10–12, 27
     - new
   * - Tensor core active, DRAM read and write BW, active SMs, SM issue
       rate
     - timelines
     - Computation; GPU Hardware Counters view
     - 10, 30, 58
     - new (Jesús has a cfg)
   * - Parallel Efficiency every 250 µs
     - sampled timeline
     - where the Device Parallel Efficiency is lost
     - 10–12, 33–36
     - new
   * - Kernels in flight
     - timeline
     - Orchestration; step 4
     - 33–36, 45–46
     - new
   * - Kernel duration
     - timeline
     - Orchestration (short kernels)
     - 33–36
     - new
   * - **Histogram of kernel duration** (0–200 µs)
     - histogram
     - Orchestration and Computation; step 4
     - 37–38
     - new
   * - **Histogram of inter-launch time** (0–200 µs)
     - histogram
     - Orchestration ("twilight zone"); step 4
     - 37–39
     - new
   * - Histogram of GEMM duration coloured by kernel
     - 3D histogram
     - different GEMM kernels per model and batch size
     - 37
     - new
   * - **Kernel signatures**: instances, average duration, TC active,
       read/write BW, active SMs per kernel
     - profile
     - Computation; step 5
     - 27, 61
     - new (family table on the device-scalability branch)
   * - Kernel classes (GEMM, attention, reshuffle, other)
     - profile + plot
     - Computation; step 5
     - 28–29
     - new
   * - Graph creation/deletion, graph launch, graph ID
     - timelines
     - CUDA graphs; step 4
     - 54
     - new
   * - TALP Device and GPU profiles (useful and data movement per GPU)
     - profile
     - the Device model itself
     - 73
     - computed (Jesús has a cfg)

Proposal
~~~~~~~~

* Each step of the proposal adds the views it relies on: step 3 the NVTX
  ranges; step 4 the calls and kernels, kernels in flight, kernel duration,
  the two histograms, Parallel Efficiency every 250 µs and the graph views;
  step 5 the kernel signatures, the kernel classes and the GEMM histogram;
  the counter timelines go with step 1.
* The **histograms of kernel duration and inter-launch time** and the
  **kernel signatures** are also plotted in the report (GPU views), as they
  are the views that Paraver shows worst at GPU granularity.
* The cfgs are written for nsys2prv and for Extrae CUDA/HIP traces (their
  event codes differ), and are listed in the deeper-analysis actions of the
  metric they explain (``definitions.yaml`` ``next_steps``), so the
  analyzer can open them.
* Start from Jesús's cfgs (``hwc_counters_app_level.cfg``,
  ``aggregated_metric_per_phase.cfg``, ``TALP_model_D_and_G_profiles.cfg``
  and its Extrae version), and ask him for the cfgs of the histograms,
  kernels in flight and kernel signatures.


Open questions (for Jesús)
--------------------------

1. How are the *Averages* normalized: over the elapsed time, the kernel
   time, or GR Active? (This is his email 3, still open.)
2. Decode: is it the full step without the TTFT range, or a range of its
   own?
3. The name patterns of the kernel classes (GEMM, attention, reshuffle).
4. Which statistic of the inter-launch time does he want (median, mean,
   histogram)?
5. Can he share the traces of the 12 cases of slide 15, to validate step 1
   against his numbers? (We have Width bs=1 and bs=256, eager.)
6. Slide 15, vLLM Depth bs=1: Time based efficiency 2.995 or 2.311?
7. Can he share the cfgs of the views of the assessment (histograms of
   kernel duration and inter-launch time, kernels in flight, Parallel
   Efficiency every 250 µs, kernel signatures, graphs)?


Validation
----------

* Step 1: the 12 cases of slide 15 (or the vLLM Width traces we have)
  against his table; the throughput speedup against the tokens per second
  of the benchmark (slide 8).
* Step 3: the decode values against slides 23 and 48.
* Step 4: slide 45 (86.95 % / 12.05 %) and the queue length 8.2 of slide 33.
* Views: each cfg opened in Paraver on the vLLM traces shows the same
  picture as the slide it comes from.
* All steps: also an Extrae CUDA trace (CloverLeaf) for the parts that do
  not depend on nsys2prv, and no change for traces without GPU.
