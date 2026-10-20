GPU Metrics: States, Events, and the ``.row`` File
==================================================

:Status: Decision recorded; future work proposed
:Date: 2026-10-20
:Scope: Device and Host metrics of Extrae GPU traces (GPU without MPI and
        MPI+GPU)

This document records why BasicAnalysis computes the GPU metrics of Extrae
traces from the Paraver **states** and the ``.row`` file rather than from the
GPU **events**, the evidence behind the decision, and how events should be
used in future Paraver views of the interactive report.


Context
-------

BasicAnalysis computes the Device metrics with a hybrid method:

#. ``paramedir`` writes the intervals of the *Running* state (1) and of the
   *Memory transfer* state (17) of every thread
   (``useful_streams_state.cfg``, ``memtransfer_streams_state.cfg``), and the
   host useful time and the time outside MPI per thread.
#. Python reads the ``.row`` labels (``GPU-D1.S1``, ``CUDA-D1.S1-<node>``,
   ``GPU_<uuid>``) to tell the GPU stream threads from the host threads and
   to group the streams by physical device (``<node>:D<n>``). For each
   device it takes the union of the intervals of its streams, so that
   kernels running concurrently on several streams are counted once.

A Paraver trace has no device or stream object: only applications, tasks,
and threads. The device structure exists only in the ``.row`` labels.


Why the ``.row`` file is needed
-------------------------------

The ``.row`` file is used for two things:

* **Streams versus host threads.** Both carry the *Running* and *Memory
  transfer* states (host computation; host side of synchronous copies).
* **Grouping by physical device.** Needed for the union of the streams of a
  GPU and for the number of GPUs, in multi-node and multi-GPU executions,
  when a process uses several GPUs, or when several processes share a GPU.

Using events instead of states would remove only part of the first use (only
the streams carry kernel events, but transfer events vary between versions
and state 17 also appears on host threads). The second use remains with
either approach: **the ``.row`` dependency comes from the per-device model,
not from the choice of states.** A cfg without the ``.row`` file can only
assume one GPU per process (as Jesús's ``TALP_model_D_and_G_profiles`` cfg
does).


States versus events
--------------------

.. list-table::
   :header-rows: 1
   :widths: 28 36 36

   * - Aspect
     - States (current)
     - Events
   * - Extrae version
     - Same meaning in every version, CUDA and HIP
     - Codes and labels change: kernels ``63000006`` / ``63000009``
       (``635000xx`` for HIP); labels "CUDA kernel" / "CUDA kernel
       execution"; transfers ``63000000`` values 3/7, ``63000014``,
       ``63000001``
   * - Cut traces
     - A kernel running at the start of the cut is counted (*Running*
       state)
     - A kernel running at the start of the cut has no start event and is
       lost
   * - Stream versus host thread
     - Needs the ``.row`` labels
     - Kernel events only on the streams; transfers still ambiguous
   * - Device grouping
     - Needs the ``.row`` labels
     - Needs the ``.row`` labels
   * - Information for the analyst
     - Only "kernel" or "transfer"
     - Kernel names, transfer types, CUDA/HIP calls on the host


Evidence (2026-10-20)
---------------------

* **Label change.** The Extrae adaptation of Jesús's cfg selects the kernel
  event by the label "CUDA kernel". Paraver resolves the event by its label,
  and Extrae 5.0.6 and 5.1.3 label ``63000006`` "CUDA kernel execution": the
  cfg gives Device useful time 0 on those traces. It worked on the xshells
  traces, whose ``.pcf`` does not declare the kernel event (Paraver then uses
  the code).
* **Meaning of the codes.** In Extrae 5.0.6 and 5.1.3, ``63000009`` is "CUDA
  kernel instantiation" on the host thread (the launch), while in older
  traces it was the kernel execution.
* **Cut trace.** In a cut HIP CloverLeaf trace (8 GPUs), the event-based
  device useful time is about 630 us per GPU lower than the state-based one:
  one stream per GPU is in *Running* from the start of the cut without a
  kernel start event (Device Parallel Efficiency 74.56% versus 74.67%).
* **``.row`` after cuts and filters.** ``paramedir -f`` (filter) and
  ``paramedir -c`` (cutter, by time) write a ``.row`` file identical to the
  original. A cut that keeps only some tasks has not been checked.
* **Simulated traces.** The Device metrics are computed on the original
  trace; Dimemas is used only for the MPI factors (Serialization and
  Transfer), so the ``.row`` of the simulated trace is not needed for them.
* **Missing ``.row``.** BasicAnalysis warns when the ``.row`` file is not
  found and cannot compute the Device metrics; the most likely cause is a
  user copying only the ``.prv`` and ``.pcf`` files.


Decision
--------

Keep the **states** and the ``.row`` file for the GPU metrics: they do not
depend on the Extrae version, they are correct at the boundaries of cut
traces (BasicAnalysis is expected to analyze traces cut to the focus of
analysis), and the ``.row`` file is required anyway by the per-device model
of multi-node and multi-GPU executions.


Future work
-----------

#. **Paraver views in the interactive report.** When the report offers
   Paraver views that show where a metric points to a problem, use the
   **events** there, because they carry what the analyst needs to see
   (kernel names, transfer types, CUDA/HIP calls). Instead of a fixed cfg,
   BasicAnalysis should **generate the cfg for each trace** when it writes
   the report, using:

   * the event codes present in that trace's ``.pcf``, selected by code and
     without labels (no dependency on the Extrae version);
   * the stream and host rows identified from the ``.row`` file.

   Metrics from states, views from events adapted to each trace.

#. **Fallback without ``.row`` (optional).** For Extrae traces without a
   ``.row`` file, compute approximate Device metrics assuming one GPU per
   process, with a clear warning and an entry in the Limitations chapter,
   instead of not computing them.

#. **Check** that a cut keeping only some tasks writes a consistent
   ``.row`` file.


Related material
----------------

Paraver cfgs prepared for a colleague (outside the repository, in
``BasicAnalysis/ToParaver-HostDevice-Extrae/``), validated against
BasicAnalysis on CloverLeaf CUDA (Extrae 5.0.6 and 5.1.3), CloverLeaf HIP, and
xshells:

* ``TALP_model_D_and_G_profiles_extrae_BasicAnalysis.cfg``: Jesús's cfg
  reviewed (kernel events by code, transfers of the streams only, host
  windows added); identical values except at the edges of cut traces.
* ``BasicAnalysis_Host_Device_Extrae.cfg``: state-based cfg; identical
  values; streams identified as all threads but the first of each process.

Both assume one GPU per process, which illustrates the limitation of any
approach without the ``.row`` file.
