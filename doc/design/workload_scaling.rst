Scaling Models: Strong, Weak, and User-Defined Workload
=======================================================

:Status: Under discussion. A first implementation exists (commit
         ``30c7cf9``); the formulas may change after this discussion.
:Date: 2026-10-24
:Branch: ``feature/workload-scaling`` (from ``devel``)
:Scope: Every metric that depends on the scaling model, for all trace
        sources (Extrae and nsys2prv)

This document lists the metrics whose formula depends on the scaling model,
gives their formula for strong scaling, weak scaling, and the user-defined
workload mode, and records the first validation case (vLLM, batch sizes 1
and 256 on the same GPU) and the discussion it opened.


Context
-------

Jesús asked for a scaling mode in which the user gives the change of the
workload instead of letting BasicAnalysis detect weak or strong scaling. His
case is a vLLM inference on one GPU with different batch sizes: the
resources do not change, only the workload. In his spreadsheet
(``Model_template.xlsx``) the computation efficiency of case :math:`c` is
scaled by the batch size:

.. math::

   CompEff_{scaled}(c) = \frac{K_1 \cdot bs_c / bs_1}{K_c}

where :math:`K` is the kernel time and :math:`bs` the batch size.

Today BasicAnalysis offers only strong and weak scaling. In both, the
number of processes is the same for the two vLLM traces (5), so strong and
weak scaling give the same numbers and neither takes the batch size into
account.

**Decisions of 2026-10-23** (implemented in ``30c7cf9``):

* Two options: ``--workload W1,W2,...`` (workload sizes; the ratio is
  :math:`W(n)/W_{ref}`) and ``--ratios-workload R1,R2,...`` (ratios given
  directly). Either option selects the workload mode; they cannot be
  combined with each other or with ``--scaling weak|strong``.
* The values are matched, in order, with the ``.prv`` traces as given on the
  command line, before filtering and sorting.
* **One ratio for all metrics**: the workload ratio :math:`w` replaces every
  resource ratio of the weak-scaling formulas.


General formulation
-------------------

Strong and weak scaling are two particular cases of one efficiency, the work
done per resource and per unit of time, relative to the reference
execution :math:`0`:

.. math::

   E(n) = \frac{W(n)}{W(0)} \cdot \frac{P(0)}{P(n)} \cdot \frac{T(0)}{T(n)}

.. list-table::
   :header-rows: 1
   :widths: 30 36 34

   * - Experiment
     - Assumption
     - Efficiency
   * - Strong scaling
     - :math:`W(n) = W(0)`
     - :math:`T(0)/T(n) \cdot P(0)/P(n)`
   * - Weak scaling
     - :math:`W(n)/W(0) = P(n)/P(0)`
     - :math:`T(0)/T(n)`
   * - Workload grows, resources fixed
     - :math:`P(n) = P(0)`, :math:`w = W(n)/W(0)`
     - :math:`w \cdot T(0)/T(n)`
   * - General (workload mode)
     - :math:`w` given by the user
     - :math:`w \cdot T(0)/T(n) \cdot P(0)/P(n)`

The resource ratio of the weak-scaling formulas is not there because the
resources grow, but because the work grows: weak scaling assumes that the
work grows like the resources. When the resources are fixed, the factor that
remains is the workload ratio.

The scalability metrics use **totals** of useful time or instructions,
already summed over all execution units, so :math:`P` does not appear in
them: the ideal is a total that grows like the work, and 100 % means that
the cost per unit of work does not change.


Metrics that depend on the scaling model
----------------------------------------

The subscript :math:`0` denotes the reference trace (the first one after
sorting) and :math:`n` the trace being evaluated. Every scalability metric
has the same form:

.. math::

   Scalability(n) = \frac{X_0}{X_n} \cdot r(n)

where :math:`X` is a total (useful time or useful instructions, summed over
all processes, threads, or devices) and :math:`r(n)` is the ratio of the
scaling model:

* **strong scaling**: :math:`r = 1`;
* **weak scaling**: :math:`r` = a resource ratio, trace :math:`n` divided by
  the reference, **different for each metric** (table below);
* **workload mode** (``30c7cf9``): :math:`r = w`, the user workload ratio,
  the same for all metrics.

.. list-table::
   :header-rows: 1
   :widths: 40 32 28

   * - Metric
     - Total :math:`X`
     - Weak-scaling ratio :math:`r`
   * - Computation Scalability (classic model)
     - useful time (``useful_tot``, or ``burst_useful_tot`` in Burst mode)
     - processes
   * - Computation Scalability + serial I/O (experimental)
     - useful + I/O + flushing time
     - processes
   * - Instruction Scalability (also Host Instruction Scalability)
     - useful instructions
     - processes with instructions (``procs_ins``)
   * - Instruction Scalability + serial I/O (experimental)
     - useful + I/O + flushing instructions
     - processes with instructions
   * - Host Computation Scalability (Host/Device model)
     - host useful time :math:`U^H`
     - host threads
   * - Device Computation Scalability (Host/Device model)
     - device useful time :math:`U^D` (kernels)
     - devices
   * - Application Computation Scalability (Host/Device model)
     - :math:`U^H + U^D`
     - host threads + devices

Speedup and Scaling Efficiency use the elapsed time :math:`T` and the ratio
of processes :math:`p(n) = P(n)/P(0)`:

.. list-table::
   :header-rows: 1
   :widths: 22 22 22 34

   * - Metric
     - Strong
     - Weak
     - Workload (``30c7cf9``)
   * - Speedup
     - :math:`T_0/T_n`
     - :math:`T_0/T_n \cdot p`
     - :math:`T_0/T_n \cdot w`
   * - Scaling Efficiency
     - :math:`T_0/T_n \cdot 1/p`
     - :math:`T_0/T_n`
     - :math:`T_0/T_n \cdot w/p`

Derived metrics that depend on the scaling model through the factors above:

* **Global Efficiency** = Parallel Efficiency × Computation Scalability
  (classic model); **Host** and **Device Global Efficiency** = the
  corresponding Parallel Efficiency × Computation Scalability (Host/Device
  model).

Metrics that **do not** depend on the scaling model: Parallel Efficiency,
Load Balance, Communication Efficiency and their factors (Serialization,
Transfer, Device Offload, Orchestration, ...), IPC Scalability and Frequency
Scalability (ratios of averages), all the absolute values (elapsed time,
average IPC, frequency), and the GPU hardware-counter metrics of nsys2prv
traces.

With :math:`w = 1` for all traces the workload mode gives the strong-scaling
values, and with :math:`w` equal to the resource ratio of each metric it
gives the weak-scaling values. Both identities were verified with real
traces (Laplace MPI 8/12/16 processes; fall3d MPI+CUDA 2/4/8 GPUs): the
CSV files and the metric values of the HTML report are identical.

Note that in weak scaling **each metric has its own resource ratio**
(processes, processes with instructions, host threads, devices, or host
threads plus devices), while the current workload mode uses **one** ratio
for all of them.


First case: vLLM, batch sizes 1 and 256
---------------------------------------

Traces: ``vLLM_Llama-3.1-Minitron-4B-Width-Base_b{1,256}_eager.juntar.prv``
(nsys2prv), from Jesús. Run on ``feature/nsys2prv`` with
``feature/workload-scaling`` merged (trial merge, 2026-10-24), with
``-skip-simul``.

Raw data
~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 46 27 27

   * - Quantity
     - b1
     - b256
   * - Processes / host threads / devices / GPU streams
     - 5 / 1 / 1 / 4
     - 5 / 1 / 1 / 4
   * - Elapsed time :math:`T`
     - 53.66 s
     - 104.20 s (× 1.94)
   * - Host useful time :math:`U^H`
     - 43.82 s
     - 55.09 s (× 1.26)
   * - Device useful time :math:`U^D` (kernels)
     - 6.74 s
     - 56.85 s (× 8.44)
   * - Kernels executed (events ``63000006``)
     - 423,745
     - 470,238 (× 1.11)
   * - Average kernel duration
     - 15.9 µs
     - 120.9 µs (× 7.6)

Both runs execute almost the same number of kernels, so they have about the
same number of steps; each step of b256 processes 256 sequences instead of
one, and its kernels last 7.6 times longer. This supports a **device**
workload ratio of 256, if both runs generate the same number of tokens per
sequence (to be confirmed with Jesús). The host work, instead, follows the
number of steps and kernel launches, which hardly changes.

Results
~~~~~~~

Value of the second trace relative to the reference. Strong and weak scaling
give the same values because the resources are the same (ratios of 1). The
last column takes b256 as the reference (``--workload 256,1 b256 b1``), so
it is the value of **b1** relative to b256.

.. list-table::
   :header-rows: 1
   :widths: 34 22 22 22

   * - Metric
     - Strong = weak (ref. b1)
     - ``--workload 1,256`` (ref. b1)
     - ``--workload 256,1`` (ref. b256, value of b1)
   * - Device Computation Scalability
     - 11.85 %
     - 3033 %
     - 3.30 %
   * - Host Computation Scalability
     - 79.55 %
     - 20364 %
     - 0.49 %
   * - Application Computation Scalability
     - 45.17 %
     - 11562 %
     - 0.86 %
   * - Device Global Efficiency
     - 6.46 %
     - 1655 %
     - 0.41 %
   * - Host Global Efficiency
     - 42.06 %
     - 10766 %
     - 0.40 %
   * - Global Efficiency
     - 9.70 %
     - 2484 %
     - 0.16 %
   * - Speedup = Scaling Efficiency
     - 0.515
     - 131.8
     - 0.0076
   * - Parallel Efficiency, Load Balance, Communication, GPU
       hardware-counter metrics, raw data
     - unchanged
     - unchanged
     - unchanged

Checks:

* Device Computation Scalability with ``--workload 1,256`` is
  :math:`6.74 \cdot 256 / 56.85 = 30.33`, which is Jesús's formula
  :math:`K_1 \cdot bs_c / K_c`.
* Taking b256 as the reference gives the inverse value
  (:math:`1/30.33 = 3.30\,\%`): changing the reference does not change the
  formula, only the direction in which it is read.
* The automatic detector reports *Weak* with b1 as the reference and
  *Strong* with b256 as the reference, so it is not meaningful for this
  experiment (it assumes that the resources change).


Second case: Laplace MPI, two grid sizes
----------------------------------------

The workload mode is not specific to GPUs: a CPU application with the same
resources and a larger problem is the same kind of experiment. Traces
``laplace-mpi8p-4096x4096_1000Iter.prv`` and
``laplace-mpi-8p-16384x16384_1k_Iter.prv`` (Extrae, MPI, 8 processes, 1000
iterations): the grid has 16 times more cells, so ``--workload 1,16``. Run on
``feature/workload-scaling`` (``30c7cf9``).

.. list-table::
   :header-rows: 1
   :widths: 46 27 27

   * - Quantity
     - 4096²
     - 16384²
   * - Elapsed time :math:`T`
     - 9.88 s
     - 127.05 s (× 12.86)
   * - Useful time :math:`U` (total)
     - 75.53 s
     - 973.02 s (× 12.88)
   * - Useful instructions :math:`I` (total)
     - 3.34·10¹¹
     - 5.12·10¹² (× 15.35)

.. list-table::
   :header-rows: 1
   :widths: 46 27 27

   * - Metric (16384² relative to 4096²)
     - Strong = weak
     - ``--workload 1,16``
   * - Computation Scalability
     - 7.76 %
     - 124.19 %
   * - IPC Scalability
     - 109.98 %
     - 109.98 %
   * - Instruction Scalability
     - 6.52 %
     - 104.26 %
   * - Frequency Scalability
     - 108.31 %
     - 108.31 %
   * - Global Efficiency
     - 7.43 %
     - 118.89 %
   * - Speedup = Scaling Efficiency
     - 0.078
     - 1.245
   * - Parallel Efficiency (95.73 %), Load Balance, Communication
     - unchanged
     - unchanged

Here one ratio gives values that can be read directly: the larger grid needs
4 % fewer instructions per cell (Instruction Scalability 104 %) and runs
them with a 10 % higher IPC, so each cell costs 24 % less useful time; the
product Computation Scalability = IPC × Instruction × Frequency Scalability
still holds (:math:`1.0998 \cdot 1.0426 \cdot 1.0831 = 1.2419`). Strong
scaling gives 7.76 %, which only says that the larger problem takes longer.
With the larger grid as the reference (option A below) the value of the
smaller grid would be :math:`1/1.2419 = 80.5\,\%`.

The automatic detector reports *Weak*, although the resources do not
change.


Discussion
----------

Discussion of 2026-10-23/24 after the first results.

**The formula is consistent with the general formulation.** With fixed
resources the only factor left is :math:`w`, and the Device Computation
Scalability reproduces Jesús's spreadsheet. In the CPU case (Laplace) one
ratio gives meaningful values. In the vLLM case the values are very large
because of the experiment:

#. **b1 is a very poor reference.** If b256 does 256 times the work of b1,
   the GPU does it in only 8.4 times the kernel time: per unit of work, b256
   is 30 times cheaper. 3033 % is the real effect of batching; b1 leaves the
   GPU almost idle. Strong and weak scaling assume the opposite situation, in
   which the reference is the most efficient execution and the values fall
   as the scale grows.
#. **The host work does not grow with the batch.** The host does roughly the
   same work per step whatever the batch size (same number of kernel
   launches), so its useful time hardly changes, and multiplying it by 256
   gives 20364 %. For the host, the workload is the number of steps, not the
   number of sequences. This is where **one ratio for all metrics** stops
   being right: in weak scaling each metric already had its own ratio
   (processes, host threads, devices, ...).
#. **Values far above 100 % make the multiplicative model hard to read.**
   Values somewhat above 100 % are normal (superlinear behaviour, Laplace
   124 %, as in strong scaling), but Global Efficiency = Parallel Efficiency
   × Computation Scalability = 2484 % cannot be read as an efficiency.

The problem is therefore not the formula but **which work each ratio
describes**: in a CPU application all the useful computation is the work of
the problem, while in a Host/Device application the host and the device can
do work that grows differently.


Applicability to all execution models
-------------------------------------

The solution must work for every execution model, not only for Host/Device
applications. The models differ in the number of **execution domains**,
that is, of parts of the system whose useful work is measured separately:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Execution model
     - Domains
     - Metrics that use the workload ratio
   * - MPI, MPI+OpenMP (and other MPI+X CPU models), OpenMP or pthreads
       only, Burst mode
     - one (application)
     - Computation Scalability (+ serial I/O), Instruction Scalability
       (+ serial I/O), Speedup, Scaling Efficiency; Global Efficiency
       through Computation Scalability
   * - Host/Device model: MPI+GPU (Extrae), GPU without MPI (Extrae),
       nsys2prv traces
     - two (Host, Device) + application
     - Host Computation Scalability, Host Instruction Scalability, Device
       Computation Scalability, Application Computation Scalability,
       Speedup, Scaling Efficiency; Host, Device and application Global
       Efficiencies through them

A rule that works for both is **one workload ratio per execution domain,
with the same default for all domains**:

* :math:`w` (``--workload`` / ``--ratios-workload``) is the workload ratio of
  the **application**. It is used for Speedup and Scaling Efficiency and, in
  the models with one domain, for all the metrics, as today. For CPU
  applications nothing changes with respect to ``30c7cf9``.
* In the Host/Device model, the host and the device have their own ratios,
  :math:`w_H` and :math:`w_D`, which **default to** :math:`w` and can be
  given separately (for example ``--host-workload`` and
  ``--device-workload``; names to be decided):

  .. math::

     HostCompScale = \frac{U^H_0}{U^H_n} \cdot w_H \qquad
     HostInsScale = \frac{I_0}{I_n} \cdot w_H \qquad
     DevCompScale = \frac{U^D_0}{U^D_n} \cdot w_D

* The **Application Computation Scalability** compares the useful time
  with the ideal useful time, which is the sum of the ideal time of each
  domain:

  .. math::

     AppCompScale =
     \frac{U^H_0 \cdot w_H + U^D_0 \cdot w_D}{U^H_n + U^D_n}

  With :math:`w_H = w_D = w` this is the current formula
  :math:`(U^H+U^D)_0/(U^H+U^D)_n \cdot w`; with ratios of 1 it is the
  strong-scaling formula.

For the vLLM case, with :math:`w = w_D = 256` and :math:`w_H = 1.11`
(kernel-launch ratio): Host Computation Scalability 88.3 %, Device
Computation Scalability 3033 % (or 3.30 % for b1 with b256 as the
reference), Application Computation Scalability
:math:`(43.82 \cdot 1.11 + 6.74 \cdot 256)/(55.09 + 56.85) = 1773/111.94 =
1584\,\%`. The device term dominates, as expected for an inference run.

The rule is independent of the trace source (Extrae or nsys2prv) and of the
programming model: only the number of domains changes. The resource ratios
of weak scaling follow the same pattern today (processes for the
application, host threads for the host, devices for the device).



Options
-------

**A. Largest workload as the reference.** Values stay at or below about
100 % and read as "compared with the best execution" (vLLM b1: Device
Computation Scalability 3.30 %, that is, b1 uses the GPU 3.3 % as well per
unit of work as b256; Laplace 4096²: 80.5 %). The formula does not change;
today this is possible by giving the largest workload first. It applies
equally to all execution models. It could become the default of the
workload mode, or stay a choice of the user.

**B. One workload ratio per execution domain** (section above). The
models with one domain keep the current behaviour; in the Host/Device model
the host and device ratios default to the application ratio and can be
given separately. This revises the decision of 2026-10-23 ("one ratio for
all metrics") only for the Host/Device model.

**C. Keep the workload view out of the multiplicative model.** Report the
values normalized by the workload in a separate table ("cost per unit of
work relative to the reference") and do not multiply them into the Global
Efficiencies, which would keep the strong-scaling factors. Applies equally
to all models. The Laplace case suggests it is not needed when the values
are moderate.

Proposed (not decided): **B**, with **A** as an option of the user (or as
the default; to be decided).


Open questions
--------------

#. How were the vLLM runs set up: does each run process one batch of
   :math:`bs` sequences with the same output length (device workload ratio
   = batch size), or the same set of prompts (strong scaling)? Would the
   number of generated tokens be a better workload measure?
#. Which workload applies to the host in GPU applications: number of steps,
   kernel launches, sequences, or none? Should the default of :math:`w_H`
   be :math:`w` (same rule as the CPU models) or 1?
#. Command line for the per-domain ratios: option names, and whether each
   one has a size form and a ratio form like ``--workload`` /
   ``--ratios-workload``. They would be an error (or ignored with a warning)
   for models with one domain.
#. Should the reference be the largest workload by default in the workload
   mode, or always the first trace as in strong and weak scaling?
#. Should the workload-normalized metrics enter the Global Efficiencies
   (option C)?
#. What does Jesús's spreadsheet do with the host and the global
   efficiencies, apart from the scaled computation efficiency?
#. Should the automatic detector be skipped in workload mode? It reports
   *Weak* for both cases, although the resources do not change.
