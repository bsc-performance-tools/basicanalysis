I/O Performance Model and Diagnostic Metrics
============================================

Purpose and Scope
-----------------

This document captures the current design of the BasicAnalysis I/O performance
model before implementation. The objective is to define a small set of
time-based performance factors that identify whether POSIX I/O contributes
significantly to execution cost, and then provide diagnostic metrics and
characteristics that guide a deeper I/O analysis.

The central design principle is:

* Performance factors are based on **time**, because BasicAnalysis observes the
  cost paid by the application on a specific I/O system.
* Quantities expressed in other units, such as bytes, operation counts, request
  sizes, files, and offsets, are primarily **diagnostic characteristics** used
  to explain the observed I/O time.
* A low I/O efficiency indicates that I/O deserves investigation. It does not
  automatically imply that the application's I/O implementation is poor. An
  application may legitimately spend substantial time moving a large amount of
  required data.

The intended analysis workflow is therefore::

    Detect significant I/O cost
              |
              v
    Identify the I/O component responsible
              |
              v
    Locate where the I/O time is spent
              |
              v
    Characterize the I/O workload/pattern
              |
              v
    Guide deeper analysis with Paraver when required

Conceptual View of I/O
----------------------

For the purposes of this model, POSIX I/O is divided into two components:

``Data Access``
    Operations that transfer application data between the application and the
    I/O system. Initially, these are ``read`` and ``write``.

``File Management``
    Additional operations required to establish and manage data access.
    Initially, these are ``open``, ``close``, and ``lseek``.

The physical motivation for this ordering is that an application performs I/O
because it needs to read data required by its computation or save data produced
by its computation. File-management activity is additional overhead associated
with managing those accesses.

This is a conceptual decomposition of I/O cost. It does **not** imply that all
data-access operations occur temporally before all file-management operations.

Classification of the traced calls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Decision (2026-10-18):* a call that moves or commits application data is
**Data Access**; a call that only manages the file (metadata, positioning,
control) is **File Management**. The rule is the same for every API, so the
components include POSIX, ANSI C, and MPI-IO calls.

Extrae 5.1.3 records the POSIX and ANSI C calls with the event ``40000004``
(``I/O calls``, values 1--17) and the MPI-IO calls with the event
``50000005`` (``MPI I/O``):

+-----------------+--------------------------------+--------------------------+
| API             | Data Access                    | File Management          |
+=================+================================+==========================+
| POSIX           | ``read``, ``write``, ``pread``,| ``open``, ``close``,     |
|                 | ``pwrite``, ``readv``,         | ``lseek``, ``ioctl``     |
|                 | ``writev``, ``preadv``,        |                          |
|                 | ``pwritev``                    |                          |
+-----------------+--------------------------------+--------------------------+
| ANSI C          | ``fread``, ``fwrite``          | ``fopen``, ``fclose``,   |
|                 |                                | ``fseek``                |
+-----------------+--------------------------------+--------------------------+
| MPI-IO          | ``MPI_File_read*``,            | ``MPI_File_open``,       |
|                 | ``MPI_File_write*`` (all       | ``MPI_File_close``       |
|                 | variants, including the        |                          |
|                 | split-collective begin/end)    |                          |
+-----------------+--------------------------------+--------------------------+

Extrae does not instrument ``fsync``, ``stat``, ``MPI_File_seek``,
``MPI_File_set_view``, or ``MPI_File_sync``. If a future Extrae version
records a call that the classification does not know, it is counted as
File Management and BasicAnalysis prints a warning naming it, so that the
classification table can be extended. With every call classified, no
``Other I/O`` category is needed (it was considered in the review and
discarded).

Within Data Access, the **read** family contains ``read``, ``fread``,
``pread``, ``readv``, ``preadv``, and ``MPI_File_read*``, and the **write**
family the corresponding write calls.

*Decision (2026-10-18), structure with MPI-IO (option A):* the decomposition
is by type of operation across the APIs:

.. math::

   IOEff = DAEff \times FMEff

with :math:`DA` and :math:`FM` including the POSIX, ANSI C, and MPI-IO calls.
The split by API (MPI-IO versus POSIX/ANSI C) is a diagnostic contribution,
like the read/write contribution. The alternative (B), decomposing by API
first and then by operation, was discarded: it doubles the number of
factors and adds another order-dependent factor.

*MPI-IO and nested POSIX calls:* by default, Extrae does not trace the POSIX
calls performed inside MPI-IO calls, because of the overhead. The MPI-IO and
POSIX times are therefore not counted twice. This is an assumption of the
model and must be documented.

The model covers **POSIX, ANSI C, and MPI-IO** File I/O. The names of the
existing metrics that say "POSIX" refer to POSIX and ANSI C calls.

.. note::

   The current implementation (``IO_OPERATIONS`` in ``rawdata.py``) keeps
   only ``read``, ``write``, ``open``, ``close``, and ``lseek`` in the
   per-operation data, while the total POSIX I/O time (``io_tot``) includes
   all the calls. In traces with ``fread``/``fwrite`` or ``fopen``/``fclose``,
   these calls are silently missing from the per-operation data.

Descriptor type
~~~~~~~~~~~~~~~

Extrae also records the ``I/O descriptor type`` (event ``40000013``: regular
file, socket, FIFO/pipe, terminal). A ``write`` to the standard output or to a
socket is currently counted as File I/O. The model should state whether it
covers regular files only, and the time of the other descriptor types should
be measured before deciding.

Example (cfdem, 4 processes): 40,086 ``fwrite`` calls to the terminal and
19,738 ``write`` calls to a descriptor opened before tracing starts are
94.9% of the write calls but 2.9% of the write time (see `Access
Pattern`_).

Terminology note
~~~~~~~~~~~~~~~~

``File Management`` is preferred over ``Metadata Management`` for the current
model. ``open`` and ``close`` may involve filesystem metadata, but ``lseek`` is
not necessarily metadata activity. Conversely, higher-level library metadata
may itself generate POSIX ``read`` and ``write`` calls. The current trace
information therefore does not permit all filesystem or library metadata
activity to be isolated as a separate category.

Formal Time Quantities
----------------------

For ``P`` parallel execution units, define:

.. math::

   U_i = \text{useful computation time of execution unit } i

.. math::

   R_i = \text{time spent in POSIX read operations}

.. math::

   W_i = \text{time spent in POSIX write operations}

.. math::

   O_i = \text{time spent in POSIX open operations}

.. math::

   C_i = \text{time spent in POSIX close operations}

.. math::

   S_i = \text{time spent in POSIX lseek operations}

Data Access time is:

.. math::

   DA_i = R_i + W_i

File Management time is:

.. math::

   FM_i = O_i + C_i + S_i

With the classification of the traced calls, :math:`R_i` and :math:`W_i`
include all the calls of the read and write families of every API (for
example, :math:`W_i` includes ``write``, ``fwrite``, ``pwrite``,
``writev``, and ``MPI_File_write*``), and :math:`FM_i` includes all the File
Management calls (``open``, ``fopen``, ``MPI_File_open``, ``close``,
``fclose``, ``MPI_File_close``, ``lseek``, ``fseek``, ``ioctl``). The terms
:math:`O_i`, :math:`C_i`, and :math:`S_i` are the main File Management
operations; the File Management contributions are reported per call.

Total modeled I/O time is:

.. math::

   IO_i = DA_i + FM_i

so that :math:`IO_i` equals the total POSIX, ANSI C, and MPI-IO time
measured for execution unit :math:`i`, and I/O Efficiency equals the
current BasicAnalysis I/O Efficiency.

The execution units are the Host execution units of the current
BasicAnalysis I/O metrics: threads in MPI+OpenMP executions, not only MPI
ranks.

For any per-execution-unit quantity ``X``:

.. math::

   X_{avg} = \frac{1}{P}\sum_{i=1}^{P} X_i

I/O Performance Model
---------------------

I/O Efficiency
~~~~~~~~~~~~~~

.. math::

   IOEff =
   \frac{U_{avg}}
        {U_{avg} + DA_{avg} + FM_{avg}}

Equivalently:

.. math::

   IOEff =
   \frac{U_{avg}}
        {U_{avg} + IO_{avg}}

**Interpretation.** I/O Efficiency measures the useful-computation contribution
relative to useful computation plus the measured POSIX I/O cost. A value close
to 100% means that POSIX I/O contributes little time relative to useful
computation. A decreasing value indicates that POSIX I/O represents an
increasing fraction of the useful-computation-plus-I/O domain.

A low value is a trigger for deeper I/O analysis, not by itself proof of
inefficient I/O behavior.

Working diagnostic threshold
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For the BasicAnalysis report, an I/O Efficiency below approximately 85% is a
candidate trigger for investigation. In practical I/O analysis, an I/O
contribution above roughly 10% of execution time can already be significant.
These values are analysis policy and should not be treated as universal
properties of all HPC applications or I/O systems.

*Decision (2026-10-19):* the I/O efficiencies (I/O, Data Access, and File
Management Efficiency) use stricter thresholds than the other efficiencies:
**Critical below 90%** (I/O takes 10% or more of the useful plus I/O time),
**Attention 90--95%**, **Good from 95%**. The report colors follow the
thresholds of each metric (the I/O thresholds are mapped to the positions of
the default ones on the color scale).

The two criteria do not measure the same quantity. I/O Efficiency compares
I/O time with **useful** time, not with the execution time:

.. math::

   IOEff = 0.85 \Leftrightarrow IO_{avg} = 0.176\,U_{avg}

which corresponds to 16% of the execution time when
:math:`U_{avg} = 0.9\,T`, but only 9% when :math:`U_{avg} = 0.5\,T`. The
"10% of execution time" criterion should therefore be evaluated with the
I/O time fractions defined below, and the 85% threshold presented only as a
policy on I/O Efficiency.

I/O time fractions
~~~~~~~~~~~~~~~~~~

Two time-domain diagnostics complement I/O Efficiency:

.. math::

   IOFraction_{avg} = \frac{IO_{avg}}{T}

.. math::

   IOFraction_{max} = \frac{\max_i IO_i}{T}

where :math:`T` is the execution time. :math:`IOFraction_{avg}` is the
fraction of the execution time spent in I/O on average (it is
:math:`1 - POSIX\_IO\_Eff` of the current implementation).
:math:`IOFraction_{max}` is the I/O fraction of the execution unit with the
most I/O time.

Averages hide I/O that is concentrated in a few execution units. For
example, with 128 ranks where rank 0 writes during 50% of the execution while
the others wait:

* :math:`IO_{avg} \approx 0.004\,T`, so :math:`IOEff \approx 99\%`;
* the participant-aware Data Access Load Balance has a single participant
  and equals 100%;
* participation is 1/128, which may be an intentional delegation strategy.

No factor flags the problem, although the I/O is on the critical path (its
cost appears as MPI waiting in the main model). :math:`IOFraction_{max} =
50\%` does. A large difference between :math:`IOFraction_{max}` and
:math:`IOFraction_{avg}`, together with Participation, identifies delegated
or serialized I/O.

These fractions are diagnostics, not efficiencies, and do not receive
efficiency colouring.

Data Access Efficiency
~~~~~~~~~~~~~~~~~~~~~~

.. math::

   DAEff =
   \frac{U_{avg}}
        {U_{avg} + DA_{avg}}

where:

.. math::

   DA_{avg} = R_{avg} + W_{avg}

Data Access Efficiency measures the efficiency retained after accounting for
the cost of accessing application data through POSIX ``read`` and ``write``
operations. A low value means that read/write activity consumes substantial
time relative to useful computation.

It does **not** identify why data access takes time. Possible explanations
include a legitimately large amount of data, imbalance in data-access time, a
large number of requests, small request granularity, access patterns that
interact poorly with the I/O system, misalignment, contention/system effects,
or transformations introduced by intermediate I/O libraries.

File Management Efficiency
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

   FMEff =
   \frac{U_{avg} + DA_{avg}}
        {U_{avg} + DA_{avg} + FM_{avg}}

File Management Efficiency measures the additional efficiency retained after
accounting for the file-management overhead required to manage data access. A
low value indicates that operations such as ``open``, ``close``, and ``lseek``
add substantial cost after the data-access cost has already been accounted for.

Because :math:`DA_{avg}` appears in its denominator, File Management
Efficiency depends on the data-access time: with the same file-management
cost, FMEff increases when :math:`DA_{avg}` increases. The ordering (Data
Access first) is a modelling choice; applying File Management first would
give different factor values with the same product. This property is shared
with other multiplicative models (e.g. TALP), but it must be documented,
because a comparison between executions can show FMEff improving although
the file-management cost has not changed. The additive shares

.. math::

   \frac{DA_{avg}}{U_{avg} + IO_{avg}}, \quad
   \frac{FM_{avg}}{U_{avg} + IO_{avg}}

are order-independent and can be shown as diagnostics next to the factors.

Multiplicative Relationship
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first level of the model is multiplicative:

.. math::

   IOEff = DAEff \times FMEff

because:

.. math::

   \frac{U_{avg}}{U_{avg} + DA_{avg}}
   \times
   \frac{U_{avg} + DA_{avg}}{U_{avg} + DA_{avg} + FM_{avg}}
   =
   \frac{U_{avg}}{U_{avg} + DA_{avg} + FM_{avg}}

Conceptually::

    Useful Computation
            |
            |  Data-access cost
            v
    Useful + Data Access
            |
            |  File-management overhead
            v
    Useful + Data Access + File Management

Performance Factors versus Diagnostic Metrics
---------------------------------------------

``Performance factors``
    Quantify the contribution of I/O cost to application performance:
    I/O Efficiency, Data Access Efficiency, and File Management Efficiency.

``Time-domain diagnostic metrics``
    Identify where the measured I/O time is spent or whether it is balanced.
    Examples include read/write time contribution and Data Access Load Balance.

``I/O characteristics``
    Describe the workload presented to the I/O system and help explain the
    observed time. Examples include bytes, operation counts, request sizes,
    files, offsets, and access patterns.

The diagnostic reasoning is::

    Efficiency -> Time source -> Workload/pattern explanation

Data Access Diagnostic Model
----------------------------

A low Data Access Efficiency raises the question:

    Why is read/write data-access time significant?

The current diagnostic dimensions are:

* Data Access time composition;
* mean duration per operation;
* Data Access Load Balance (per operation);
* Data volume;
* request granularity;
* access pattern;
* alignment;
* file sharing/access behavior;
* I/O participation.

These dimensions are not necessarily independent. For example, small requests
may be more problematic when combined with an irregular access pattern than
when neighboring requests can be aggregated by the I/O stack.

Read and Write Time Contribution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

   ReadContribution = \frac{R_{avg}}{R_{avg} + W_{avg}}

.. math::

   WriteContribution = \frac{W_{avg}}{R_{avg} + W_{avg}}

Therefore:

.. math::

   ReadContribution + WriteContribution = 1

These are contribution metrics, not efficiencies. A high Read Contribution
does not mean reads are inefficient; it means reads account for most of the
measured Data Access time and should receive priority in the next diagnostic
step.

Mean Duration per Operation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

For each operation :math:`op` (read, write, open, close, lseek):

.. math::

   MeanDuration_{op} = \frac{\sum_i T_{op,i}}{N_{op}}

where :math:`T_{op,i}` is the time of execution unit :math:`i` in calls of
:math:`op` and :math:`N_{op}` the total number of calls. It costs nothing
(time divided by count) and distinguishes the two explanations of a high
operation time: **many operations** (same mean duration, higher count) or
**more expensive operations** (same count, higher mean duration). The latter
points to the interaction with the I/O system rather than to the application
I/O pattern.

In the VTKHDF validation (see `Validation with the VTKHDF Case (POP3 Ticket
668)`_), the execution with 1M chunks performs the same number of opens as
the others (347 per rank), but each open takes 1,416 µs instead of about
500 µs, which lowers File Management Efficiency to 74.6%. The mean duration
identifies this immediately; time and count alone do not.

The mean duration should be presented as a characteristic, not as an
efficiency.

Data Access Load Balance
~~~~~~~~~~~~~~~~~~~~~~~~

The primary balance diagnostics are **per operation**:

.. math::

   ReadLB = \frac{R_{avg}}{\max_i R_i}, \quad
   WriteLB = \frac{W_{avg}}{\max_i W_i}

Applications often read and write in different phases separated by
synchronization. An imbalance in the write phase then costs time on its
own, and summing :math:`R_i + W_i` per execution unit dilutes it (or can even
cancel it, when the slowest writer is a fast reader). In the VTKHDF
validation, the execution with 2M chunks has Read LB = 0.89 and
Write LB = 0.21, but the combined DALB is 0.49; the write imbalance is the
cause of the longer MPI waiting time of that execution.

The combined Data Access Load Balance remains useful as a summary. A
candidate time-based definition is:

.. math::

   DALB = \frac{DA_{avg,IO}}{DA_{max,IO}}

The intention is to answer: among the execution units performing data access,
how evenly is data-access time distributed?

Not all application ranks necessarily perform I/O. Including deliberately
non-I/O ranks as zero-time participants could make a valid I/O delegation
strategy appear severely imbalanced.

Define the set of Data Access participants:

.. math::

   P_{DA} = \{i : DA_i > 0\}

and conceptually:

.. math::

   DA_{avg,IO} = \frac{1}{|P_{DA}|}\sum_{i \in P_{DA}} DA_i

.. math::

   DA_{max,IO} = \max_{i \in P_{DA}} DA_i

This participant-aware definition remains a design item to validate against the
available Paraver raw data before implementation.

The raw data is already available: the Paraver analysis of the I/O call
time (``io_calls_time.stats.csv``) contains one row per execution unit and
one column per operation, so :math:`DA_i` and :math:`FM_i` can be computed
exactly per row. The current parser keeps only the Total, Average, and
Maximum rows. Using :math:`\max_i R_i + \max_i W_i` instead of
:math:`\max_i (R_i + W_i)` overestimates the maximum: by 8% in the VTKHDF
execution with 4M chunks (649 ms instead of 600 ms).

Two details of the definition remain open:

* **Participant criterion.** With :math:`DA_i > 0`, an execution unit that
  only reads a small configuration file becomes a participant and lowers
  the average. Options: report the balance over all execution units and
  over participants, or use a minimum activity threshold (itself a policy
  choice).
* **Execution unit.** Threads or MPI ranks in MPI+OpenMP executions (the
  current I/O metrics use Host threads).

A low Data Access Load Balance identifies uneven read/write time; it does not
establish its cause. The next analysis should compare bytes transferred,
operation counts, request sizes, read/write composition, and files accessed.

Data Volume
~~~~~~~~~~~

Report:

.. math::

   B_R = \text{total bytes read}

.. math::

   B_W = \text{total bytes written}

and:

.. math::

   B_{DA} = B_R + B_W

Volume is essential when interpreting low Data Access Efficiency. A long Data
Access time may simply reflect the movement of a very large amount of data
required by the application.

Request Count
~~~~~~~~~~~~~

Report the number of POSIX read and write operations:

.. math::

   N_R, \quad N_W

For the same data volume, a workload issuing a very large number of requests
can interact differently with the I/O stack from one issuing fewer, larger
requests.

Mean Request Size
~~~~~~~~~~~~~~~~~

.. math::

   MeanReadSize = \frac{B_R}{N_R}

.. math::

   MeanWriteSize = \frac{B_W}{N_W}

The mean should not be used alone because different request-size distributions
can produce the same mean.

Request-Size Distribution
~~~~~~~~~~~~~~~~~~~~~~~~~

BasicAnalysis already obtains request-size histograms from Paraver. The
histogram intervals are determined from the request-size values present in the
trace. This gives an adaptive characterization instead of imposing a universal
rule such as ``request < 1 MB = small``.

Represent the distribution as:

.. math::

   H = \{(I_1,N_1), (I_2,N_2), \ldots, (I_k,N_k)\}

where ``I_j`` is a request-size interval and ``N_j`` is the number of
operations in it.

For each interval:

.. math::

   RequestShare_j = \frac{N_j}{\sum_k N_k}

This supports factual observations such as: a large fraction of the POSIX read
requests is concentrated in the lowest request-size intervals observed in this
execution. It should not automatically imply that those requests are
inefficiently small.

Time per request-size interval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The count does not show which requests cost the time. The time share of
each interval should be reported next to the count share:

.. math::

   TimeShare_j = \frac{T_j}{\sum_k T_k}

where :math:`T_j` is the time of the operations in interval :math:`j`. This
is the "I/O operation time per size" view used in the VTKHDF analysis.

Interval boundaries
^^^^^^^^^^^^^^^^^^^

The current Paraver histograms use **linear** intervals whose width is
determined by the largest request. When a few requests are large, all the
small requests fall in the first interval. In the VTKHDF execution with 4M
chunks, the first read interval is [8 B, 47 KB) and contains **99.8%** of
all the reads, so the distinction made in the analysis slides (8 B--42 KB
versus 62--65 KB) is not visible.

Recommended alternative: **power-of-two intervals** (for example < 4 KB,
4--64 KB, 64 KB--1 MB, 1--16 MB, ...):

* they are not "small/large" thresholds: each interval is only a scale;
* they resolve small requests even when large ones exist;
* they are identical in every trace, which makes cross-execution comparison
  direct (see `Cross-execution comparison`_);
* they relate directly to file-system sizes (in the VTKHDF case, GPFS data
  blocks of 16 MB and sub-blocks of 16 KB).

Histogram Coverage
^^^^^^^^^^^^^^^^^^

.. math::

   Coverage = \frac{\sum_j N_j}{N_{read/write}}

Coverage is a quality/representativeness indicator.

Cross-execution comparison
^^^^^^^^^^^^^^^^^^^^^^^^^^

Because Paraver histogram intervals depend on each trace, bin boundaries can
differ between executions. The histogram is therefore immediately useful for
single-execution characterization, while cross-execution comparison should
initially use exact quantities such as volume, operation count, and mean
request size. Common re-binning could be considered later; power-of-two
intervals (see `Interval boundaries`_) provide it directly.

Access Pattern
~~~~~~~~~~~~~~

*Decided (2026-10-29) and implemented.* The access pattern describes
where each request falls in the file with respect to the previous request
of the same process: one after the other, with regular jumps, or anywhere.
The same volume and request sizes can cost very different times depending
on this pattern, because file systems and their caches favor sequential
access.

Information in the trace
^^^^^^^^^^^^^^^^^^^^^^^^

Extrae does not record the offset of the reads and writes. It records the
descriptor and the requested size of each call, and the offset argument of
the seek calls (Extrae 5.1.3 source, ``wrappers/IO/io_probe.c``):

+------------------------------------+--------------------+------------------+
| Calls                              | Recorded           | Offset           |
+====================================+====================+==================+
| ``read``, ``write``, ``fread``,    | descriptor,        | reconstructed    |
| ``fwrite``, ``readv``, ``writev``  | requested size     | (current         |
|                                    |                    | position)        |
+------------------------------------+--------------------+------------------+
| ``lseek``, ``fseek``               | descriptor, offset | seek argument;   |
|                                    | argument (no       | ``SEEK_SET``     |
|                                    | ``whence``)        | assumed          |
+------------------------------------+--------------------+------------------+
| ``pread``, ``pwrite``, ``preadv``, | descriptor,        | not available    |
| ``pwritev``                        | requested size     | (argument not    |
|                                    |                    | recorded)        |
+------------------------------------+--------------------+------------------+
| ``open``, ``fopen``                | returned           | position 0       |
|                                    | descriptor, file   |                  |
|                                    | name               |                  |
+------------------------------------+--------------------+------------------+
| MPI-IO                             | requested size     | not available    |
|                                    | (no handle, no     |                  |
|                                    | offset)            |                  |
+------------------------------------+--------------------+------------------+

The position of each descriptor can therefore be rebuilt per process: an
``open``/``fopen`` sets it to 0, a seek sets it to the recorded offset, and
each read or write starts at the current position and advances it by its
size. The offset of each request is the position at its start.

Offset event only in recent traces
""""""""""""""""""""""""""""""""""

The ``I/O offset`` event (``40000075``) is recent: Extrae added it at our
request and delivered it first in a special installation; the first public
Extrae version that includes it is still to be confirmed with the Extrae
team. Only recent traces have it.
Of the traces used in this design, the VTKHDF traces (July 2026) have it
in all of their 417,596 seeks; the cfdem trace (April 2025) does not
define it. Without the offset, the position is lost at the first seek of
a stream. Rule:

* the position stays known from an ``open`` while the stream only reads
  and writes (cfdem makes no seeks, so all its requests to regular files
  are classified);
* a seek without an offset (or any seek in a trace whose ``.pcf`` does not
  define ``40000075``) makes the position unknown until the next ``open``
  of the descriptor;
* the share of requests with an unknown offset is always reported, so a
  trace from an older Extrae shows a low coverage instead of a wrong
  pattern.

Association with the files
""""""""""""""""""""""""""

Every read, write, and seek carries the descriptor (``40000010``), and
every ``open``/``fopen`` records the descriptor it returns together with
the file name (``40000059``). Each call is therefore attributed to a file
through its descriptor, from the ``open`` until the ``close``, after which
the descriptor number can be reused for another file. This is the
mechanism already used for the files and processes per file (`File Sharing
and Overlap`_), so the access pattern can also be given per file.

Descriptors are shared by the threads of a process, and so is the file
position: the position and the file are kept per process and descriptor,
not per thread.

Coverage in VTKHDF 100k (reads and writes): 99.6% of the calls and 94.9%
of the bytes have both the file and the offset; 0.4% of the calls and
5.1% of the bytes have a known offset (after a seek) but no file name.
These are the writes of 12 processes through a descriptor without a
traced ``open`` (descriptors 69, 70, 72): they are classified, and they
are attributed to the unnamed group of the files diagnostics. All 38,954
``open`` calls of this trace record a file name.

Definitions
^^^^^^^^^^^

A *stream* is a descriptor of a process between its ``open`` and its
``close`` (the threads of the process share it). Each read is compared with the previous read
of the same stream, and each write with the previous write, through the
gap between the start of the request and the end of the previous one:

.. math::

   gap_i = offset_i - (offset_{i-1} + size_{i-1})

* **First**: no previous request of the same kind on the stream.
* **Consecutive**: :math:`gap_i = 0`; the request starts where the
  previous one ended.
* **Strided**: :math:`gap_i \ne 0` and :math:`gap_i = gap_{i-1}`; a
  regular jump, repeated.
* **Forward**: :math:`gap_i > 0` and not strided; a jump ahead.
* **Backward**: :math:`gap_i < 0` and not strided; a jump back, including
  rereading or rewriting a region.
* **Unknown offset**: ``pread``/``pwrite`` family, MPI-IO, streams
  without a traced ``open`` until their first seek with an offset
  (descriptors opened before tracing starts, standard output,
  ``openat``/``dup`` not instrumented), and streams after a seek without
  an offset (traces from Extrae versions without the offset event).

*Sequential* (consecutive, positive strided, and forward requests) is the
term used by Darshan, and *consecutive* is the subset without gaps; using
the same meanings allows comparing with Darshan reports. ``Random`` is not
used as a class, because jumps can be regular at a scale the per-request
comparison does not see (for example HDF5 metadata lookups); the
backward and forward shares describe the pattern without that judgment.

Each class is reported as a share of the **requests**, the **bytes**, and
the **time** of the reads and of the writes, since a pattern that covers
most requests may move few bytes, as in the VTKHDF reads below.

Two related quantities come out of the same reconstruction:

* **Seeks to the current position**: seeks whose offset is the position
  the stream already has. The call moves nothing, so its time is a File
  Management cost that the application or the library can avoid.
* **Re-accessed volume**: bytes read (written) by a process more than
  once in the same file, as a share of its read (write) volume: the
  bytes moved minus the distinct bytes (union of the accessed regions per
  process and file).

Assumptions and limitations
^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Seek origin not recorded.** The ``whence`` of the seeks is not
  recorded: a seek with ``SEEK_CUR`` or ``SEEK_END`` is read as an
  absolute position, and the following requests of the stream are
  misplaced until the next ``SEEK_SET``. In the VTKHDF traces
  the seeks to 0 after an access (38,636, about one per ``open``) are
  HDF5 rereading the superblock: an
  8-byte read of the signature, a seek to 0, and a 48-byte read of the
  superblock, consistent with ``SEEK_SET``. The assumption holds for HDF5
  (``sec2`` driver) but has to be stated, and the Extrae developers could
  be asked to record ``whence``.
* **Requested size.** The size is the request, not the bytes returned: a
  short read (end of file) advances the reconstructed position too far.
* **Library buffering.** ``fread``/``fwrite``/``fseek`` describe the
  pattern presented to the C library, not what reaches the file system
  after the stream buffering.
* **Offsets not recorded.** ``pread``/``pwrite`` and MPI-IO (including the
  MPI-IO explicit-offset calls) cannot be classified; their share is
  reported as *unknown offset* so that the coverage is visible. Recording
  the offset argument of ``pread``/``pwrite`` would need a change in
  Extrae.
* **Regular files only.** Terminals, sockets, and pipes (descriptor type,
  event ``40000013``) have no position and are excluded from the
  classification; the coverage is computed over the requests to regular
  files.
* **Open flags not recorded.** A file opened with ``O_APPEND`` writes at
  its end whatever the position, so its writes would be misplaced; the
  open flags are not in the trace.
* **Descriptors not followed.** ``dup``/``dup2``, ``openat``, ``creat``,
  and descriptors inherited through ``fork`` are not instrumented: their
  calls have no traced ``open``, so they get neither a position (until a
  seek) nor a file name.
* **Per process.** The classification compares the requests of one
  process. How the regions of several processes fit together in a shared
  file (partitioned blocks, interleaved records) is a separate analysis
  (`File Sharing and Overlap`_).

Prototype results
^^^^^^^^^^^^^^^^^

Prototype script over the original traces (one pass, about 7 s per
VTKHDF trace; in BasicAnalysis it would be one more pass over the
filtered trace, which would also keep the offset event ``40000075``).
The prototype kept the positions per thread; the VTKHDF and cfdem traces
have one I/O thread per process, so the results are the same per process.

VTKHDF uGrid, 112 processes, 100k and 2M chunks (shares in %):

.. table::
   :widths: 22 10 7 13 9 9 10

   +------------------------+------------+---------+---------------+-----------+-----------+------------+
   | Calls                  | Share of   | First   | Consecutive   | Strided   | Forward   | Backward   |
   +========================+============+=========+===============+===========+===========+============+
   | Reads 100k             | requests   | 8.0     | 14.2          | 0.0       | 40.2      | 37.7       |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   | (482,706 calls)        | bytes      | 0.0     | **93.3**      | 0.0       | 4.3       | 2.3        |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   |                        | time       | 8.6     | 17.6          | 0.0       | 38.9      | 34.9       |
   +------------------------+------------+---------+---------------+-----------+-----------+------------+
   | Writes 100k            | requests   | 0.6     | **83.2**      | 0.0       | 12.7      | 3.5        |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   | (19,320 calls)         | bytes      | 0.0     | 94.3          | 0.0       | 5.7       | 0.0        |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   |                        | time       | 1.6     | 62.7          | 0.0       | 35.4      | 0.3        |
   +------------------------+------------+---------+---------------+-----------+-----------+------------+
   | Reads 2M               | requests   | 8.2     | 11.4          | 0.0       | 41.5      | 38.9       |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   | (466,866 calls)        | bytes      | 0.0     | **94.7**      | 0.0       | 3.9       | 1.4        |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   |                        | time       | 5.6     | 11.3          | 0.0       | 61.5      | 21.7       |
   +------------------------+------------+---------+---------------+-----------+-----------+------------+
   | Writes 2M              | requests   | 3.2     | 19.0          | 3.1       | 58.8      | 15.9       |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   | (3,556 calls)          | bytes      | 0.0     | 28.8          | 8.3       | **62.9**  | 0.0        |
   |                        +------------+---------+---------------+-----------+-----------+------------+
   |                        | time       | 10.8    | 2.6           | 0.7       | **85.9**  | 0.0        |
   +------------------------+------------+---------+---------------+-----------+-----------+------------+

No request has an unknown offset (the traces have only ``read``,
``write``, ``open``, ``close``, and ``lseek``). Observations:

* **Reads**: most read requests jump forward or backward (78%), but they
  move little data: 93--95% of the bytes are read consecutively. In the
  call sequence of one process the jumps are small reads after a seek
  (mostly 512 bytes), consistent with HDF5 metadata lookups, while the
  bulk data is read sequentially. The jumps take 74% (100k) and 83% (2M)
  of the read time, so the read time is dominated by small scattered
  requests, not by the data.
* **Writes**: with 100k chunks the data is written consecutively (83% of
  the requests, 94% of the bytes); with 2M chunks most writes jump ahead
  (63% of the bytes, 86% of the write time): the regions written by
  successive requests are separated by gaps. The cause (chunk allocation
  in the file) has not been checked.
* **Seeks to the current position**: 38,511 of 417,596 seeks (9.2%) in
  100k, 38,476 of 416,440 in 2M.
* **Re-accessed volume**: 2.5% of the read bytes (metadata reread after
  each of the 3--11 opens of the same file by a process), 0.0% of the
  written bytes.

cfdem 4 processes (Ticket 570, ANSI C and POSIX):

* Reads: 1,150 requests, 96.6% consecutive (97.5% of the bytes).
* Writes: 63,047 requests, but 94.9% have an unknown offset: 40,086
  ``fwrite`` to the terminal (descriptor 1) and 19,738 ``write`` to
  descriptor 3, opened before tracing starts (descriptor type unknown).
  They are 6.4% of the bytes and 2.9% of the write time. The writes to
  regular files are consecutive (96.5% of the write time). This trace
  motivates excluding non-file descriptors and reporting the coverage.

SPH-EXA (64 ranks) uses only ``MPI_File_read_at``: all its requests have
an unknown offset, and the access pattern is not available.

Presentation
^^^^^^^^^^^^

Proposed for the *What requests are made?* card of the I/O Analysis view
and for ``io_metrics.csv``: for reads and writes, the consecutive,
strided, forward, and backward shares of the requests, bytes, and time
(one stacked bar per execution and quantity), the share of seeks to the
current position, the re-accessed volume, and the offset coverage
(requests with a known offset over the requests to regular files). These
are diagnostics, not efficiency factors: a backward or forward pattern can
be what the data layout requires, and its cost is already in Data Access
Efficiency.

Alignment
~~~~~~~~~

Request alignment is separate from request granularity. A request can be large
but interact poorly with the filesystem because its offset or size does not
align with relevant storage boundaries.

Declaring an access misaligned may require system-specific information such as
filesystem block or stripe configuration. Alignment should initially be a
diagnostic characteristic rather than a universal efficiency metric.

Intermediate I/O Libraries
~~~~~~~~~~~~~~~~~~~~~~~~~~

The POSIX trace describes the access pattern ultimately presented to the POSIX
layer. A higher-level library such as HDF5, NetCDF, MPI-IO, or ADIOS may
transform the application's intended pattern.

BasicAnalysis can report the resulting POSIX behavior but should not attribute
the transformation to a particular library without higher-level evidence.

I/O Participation
~~~~~~~~~~~~~~~~~

.. math::

   Participation_{DA} = \frac{|P_{DA}|}{P}

This is a useful characteristic, not an efficiency. A low participation ratio
may represent an intentional and effective I/O delegation strategy.

File Sharing and Overlap
~~~~~~~~~~~~~~~~~~~~~~~~

Future analysis could characterize private versus shared files, ranks per file,
and overlapping versus non-overlapping file regions. A shared file is not
automatically a performance problem; impact depends on the actual access
pattern, overlap, filesystem striping, locking, and system characteristics.

Ranks per file and files per rank can already be obtained in the first
version: the Paraver analysis of the opens per filename
(``io_filename_count.stats.csv``) contains the execution unit × file matrix.
The number of non-zero cells per file column gives the ranks that open the
file, and per row the files opened by each rank. This allows the
classification used in the VTKHDF analysis: opens of the rank's own file,
of other ranks' files, and of a common file. In the execution with 4M
chunks, rank 0 opens its own part file 10 times, the common file 5 times,
and each other part file 4 times. Overlapping regions still require
offsets.

*Implemented (2026-10-20)* from the filtered trace instead of the open
matrix, because the opens alone do not show who moves the data: each call
is attributed to a file through its descriptor (``40000010``) and the file
name (``40000059``) of the ``open``/``fopen`` that returned it. Diagnostics:
files accessed, maximum processes per file, volume moved by the main
process of each file, and file-name coverage; per-file table in the report
and ``io_files.csv``. A count of shared files (more than one process) was
tried and discarded: in VTKHDF all 113 files are opened and read (metadata)
by the 112 processes, so all were shared, while each part file is written
and read about 97% by one process. The opens per file
(``hist-filename-burst.cfg``, ``hist-filename-time.cfg``) are no longer
computed.

Data Access Diagnostic Questions
--------------------------------

When Data Access Efficiency is low, guide the analyst through questions such as:

#. Is Data Access time dominated by reads or writes?
#. Are read time and write time each balanced among ranks that actually
   perform I/O?
#. Is the I/O concentrated in a few execution units (maximum versus average
   I/O time fraction, participation)?
#. How much data is being transferred?
#. How many read/write operations are issued?
#. Has the mean duration per operation changed, or only the number of
   operations?
#. How is the transferred volume divided into requests?
#. What does the adaptive request-size distribution look like?
#. Are many requests concentrated in the smaller observed request-size ranges?
#. Is the access pattern contiguous, strided, or irregular?
#. Are accesses aligned appropriately for the underlying I/O system?
#. Are files private or shared?
#. Do multiple ranks access overlapping file regions?
#. Could a higher-level I/O library be transforming the application's intended
   pattern before it reaches POSIX?
#. If workload characteristics are similar across ranks but access times differ,
   should storage-system interaction be investigated further?

File Management Diagnostic Model
--------------------------------

A low File Management Efficiency raises the question:

    Why are file-management operations adding significant time to data access?

File-Management Time Contributions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

   OpenContribution = \frac{O_{avg}}{FM_{avg}}

.. math::

   CloseContribution = \frac{C_{avg}}{FM_{avg}}

.. math::

   SeekContribution = \frac{S_{avg}}{FM_{avg}}

where:

.. math::

   FM_{avg} = O_{avg} + C_{avg} + S_{avg}

Therefore:

.. math::

   OpenContribution + CloseContribution + SeekContribution = 1

These are time-contribution metrics rather than efficiencies.

File Management Load Balance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A candidate time-based metric is:

.. math::

   FMLB = \frac{FM_{avg,IO}}{FM_{max,IO}}

As with Data Access Load Balance, the participating population must be defined
carefully. A low value identifies uneven file-management time but does not
determine its cause. The per-operation balance (in particular Open LB) is
more informative than the combined value, for the same reason as for Data
Access, and the exact :math:`FM_i` is available from the per-row raw data.

File-Management Operation Counts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Report the number of ``open``, ``close``, and ``lseek`` operations. Counts help
distinguish high total time accompanied by many operations from high total time
despite relatively few operations. The mean duration per operation (see
`Mean Duration per Operation`_) makes this distinction explicit.

File-Level Open Characteristics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The current raw data supports:

* distinct filenames observed;
* per-file open count;
* per-file open time;
* total open count represented by filename data;
* total open time represented by filename data;
* filename count coverage;
* filename time coverage.

Useful report views include total distinct files, total opens, average opens per
file, top files by open count, top files by open time, and percentage of open
time associated with high-cost files.

Filename Coverage
~~~~~~~~~~~~~~~~~

.. math::

   FilenameCountCoverage =
   \frac{\sum_f OpenCount_f}{OpenCount_{total}}

.. math::

   FilenameTimeCoverage =
   \frac{\sum_f OpenTime_f}{OpenTime_{total}}

These are data-quality/representativeness measures rather than performance
efficiencies.

File Management Diagnostic Questions
------------------------------------

#. Which operation dominates File Management time: open, close, or lseek?
#. Is File Management time balanced among relevant I/O participants?
#. Is the dominant time associated with a large number of operations, or
   with a higher mean duration per operation?
#. Are files being opened repeatedly?
#. Does each rank open only its own files, files of other ranks, or a
   common file?
#. Is the cost concentrated in a small subset of files?
#. How many distinct files are involved?
#. Is filename-level information sufficiently complete according to coverage?
#. Does the observed time appear explainable by application file-management
   activity, or is deeper filesystem/system analysis required?

Suggested I/O Report
--------------------

::

    I/O PERFORMANCE
    |
    +-- I/O Efficiency
    |   +-- Data Access Efficiency
    |   `-- File Management Efficiency
    |
    +-- I/O TIME
    |   +-- API contribution (MPI-IO / POSIX and ANSI C)
    |   +-- I/O time fraction (average)
    |   +-- I/O time fraction (maximum)
    |   `-- I/O participation
    |
    +-- DATA ACCESS
    |   +-- Read / Write Time Contribution
    |   +-- Data Access Load Balance (summary)
    |   |
    |   +-- Read
    |   |   +-- Time
    |   |   +-- Load Balance
    |   |   +-- Volume
    |   |   +-- Operations
    |   |   +-- Mean Duration
    |   |   +-- Mean Request Size
    |   |   `-- Request-Size Distribution (count and time)
    |   |
    |   `-- Write
    |       +-- Time
    |       +-- Load Balance
    |       +-- Volume
    |       +-- Operations
    |       +-- Mean Duration
    |       +-- Mean Request Size
    |       `-- Request-Size Distribution (count and time)
    |
    `-- FILE MANAGEMENT
        +-- File Management Load Balance (summary)
        +-- Open
        |   +-- Time contribution
        |   +-- Load Balance
        |   +-- Operations
        |   `-- Mean Duration
        +-- Close
        |   +-- Time contribution
        |   +-- Operations
        |   `-- Mean Duration
        +-- Lseek
        |   +-- Time contribution
        |   +-- Operations
        |   `-- Mean Duration
        |
        `-- File Access
            +-- Distinct files
            +-- Opens per file
            +-- Ranks per file / files per rank
            +-- Top files by open count
            `-- Top files by open time

Suggested Data-Access Summary Table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+----------------------+----------------------+----------------------+
| Data Access          | Read                 | Write                |
+======================+======================+======================+
| Time                 | measured value       | measured value       |
+----------------------+----------------------+----------------------+
| Time contribution    | percentage           | percentage           |
+----------------------+----------------------+----------------------+
| Load balance         | percentage           | percentage           |
+----------------------+----------------------+----------------------+
| Volume               | bytes                | bytes                |
+----------------------+----------------------+----------------------+
| Operations           | count                | count                |
+----------------------+----------------------+----------------------+
| Mean duration        | time / operation     | time / operation     |
+----------------------+----------------------+----------------------+
| Mean request size    | bytes / operation    | bytes / operation    |
+----------------------+----------------------+----------------------+
| Histogram coverage   | percentage           | percentage           |
+----------------------+----------------------+----------------------+

Suggested File-Management Summary Table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+-----------------+-------------------+------------+------------------+
| File Management | Time contribution | Operations | Mean duration    |
+=================+===================+============+==================+
| Open            | percentage        | count      | time / operation |
+-----------------+-------------------+------------+------------------+
| Close           | percentage        | count      | time / operation |
+-----------------+-------------------+------------+------------------+
| Lseek           | percentage        | count      | time / operation |
+-----------------+-------------------+------------+------------------+

Report Interpretation Policy
----------------------------

Efficiency Coloring
~~~~~~~~~~~~~~~~~~~

Efficiency-style threshold coloring should initially be reserved for:

* I/O Efficiency;
* Data Access Efficiency;
* File Management Efficiency.

Load-balance metrics can use a high-is-good percentage interpretation once
their participant-aware definitions are finalized.

Time contribution, I/O time fractions, bytes, operation counts, mean
duration, mean request size, request-size histogram bins, number of files,
and opens per file should **not** receive generic green/red efficiency
coloring because they require context.

Conditional Diagnostic Emphasis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The performance factors should determine which diagnostic information the
report emphasizes::

    Low I/O Efficiency
        |
        +-- Low Data Access Efficiency
        |      -> emphasize Data Access diagnostics
        |
        `-- Low File Management Efficiency
               -> emphasize File Management diagnostics

Interpretation Examples
-----------------------

Low Data Access Efficiency with Small-Request Pattern
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If BasicAnalysis observes low I/O Efficiency, File Management Efficiency close
to 100%, low Data Access Efficiency, balanced Data Access time, and a very
large number of read operations concentrated in the lower observed request-size
intervals, a suitable interpretation is:

    The I/O efficiency loss is primarily associated with Data Access rather
    than File Management. Data Access time is relatively balanced across I/O
    participants, while the observed POSIX read pattern contains a high number
    of requests concentrated in the lower request-size ranges. The read request
    granularity and access pattern should be investigated further.

The report should not automatically conclude that the requests are inefficient
or that the filesystem is the root cause.

Low Data Access Efficiency with Large Data Volume
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If Data Access Efficiency is low but Data Access Load Balance is good, the
transferred volume is very large, requests are relatively large, and no obvious
granularity problem appears, a suitable interpretation is:

    The execution spends significant time performing Data Access, but the
    available characteristics do not identify an obvious imbalance or
    small-request pattern. The observed cost may be associated with the amount
    of data that the application needs to transfer. Achieved I/O performance
    and interaction with the underlying storage system should be examined
    before classifying the behavior as inefficient.

Low Data Access Load Balance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When Data Access Load Balance is low, compare workload characteristics across
I/O participants. If ranks with greater Data Access time also perform more I/O
work, workload distribution may contribute to the imbalance. If ranks perform
similar amounts and types of I/O work but access times differ significantly,
recommend deeper investigation of storage-system interaction rather than
attributing the imbalance to application work distribution.

Low File Management Efficiency
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If File Management Efficiency is low and ``open`` accounts for most of File
Management time, inspect the number of opens and file-level information. Many
opens plus high open time may indicate significant repeated file-management
activity. Few opens plus high total open time motivates investigation of the
cost of those operations and underlying filesystem behavior.

Current Raw-Data Coverage
-------------------------

+------------------------------------+------------------------------+
| Diagnostic information             | Current status               |
+====================================+==============================+
| Read/write time                    | Available (five POSIX calls  |
|                                    | only; ANSI C and vector      |
|                                    | variants are dropped)        |
+------------------------------------+------------------------------+
| Open/close/lseek time              | Available (same limitation)  |
+------------------------------------+------------------------------+
| Operation counts                   | Available                    |
+------------------------------------+------------------------------+
| Mean duration per operation        | Derivable from time/count    |
+------------------------------------+------------------------------+
| Per-unit time per operation        | In the CSV (one row per      |
| (exact DA_i, FM_i, per-op LB)      | unit); not parsed yet        |
+------------------------------------+------------------------------+
| Maximum I/O time per unit          | Available (``io_max``)       |
+------------------------------------+------------------------------+
| Read/write total bytes             | Available                    |
+------------------------------------+------------------------------+
| Read/write average/max bytes       | Available                    |
+------------------------------------+------------------------------+
| Mean request size                  | Derivable from bytes/count   |
+------------------------------------+------------------------------+
| Request-size distribution          | Implemented (power-of-two    |
|                                    | intervals; count, time,      |
|                                    | bytes; POSIX, ANSI C, MPI-IO)|
+------------------------------------+------------------------------+
| Request-size histogram coverage    | Implemented                  |
+------------------------------------+------------------------------+
| Per-file open count/time           | Available                    |
+------------------------------------+------------------------------+
| Ranks per file / files per rank    | Implemented (filtered trace: |
|                                    | descriptor and file name;    |
|                                    | POSIX and ANSI C only)       |
+------------------------------------+------------------------------+
| Bytes, requests, and time per file | Implemented (same source)    |
| and per process                    |                              |
+------------------------------------+------------------------------+
| Filename count/time coverage       | Available                    |
+------------------------------------+------------------------------+
| I/O participant information        | In the CSV (non-zero rows);  |
|                                    | criterion to be decided      |
+------------------------------------+------------------------------+
| Per-rank detailed workload         | Counts per unit in the CSV;  |
|                                    | bytes per unit to be checked |
+------------------------------------+------------------------------+
| Offset-based access pattern        | Implemented for              |
|                                    | read/write/fread/fwrite from |
|                                    | open and seek (event         |
|                                    | 40000075, recent Extrae      |
|                                    | only); not for pread/pwrite  |
|                                    | or MPI-IO (see `Access       |
|                                    | Pattern`_)                   |
+------------------------------------+------------------------------+
| Alignment analysis                 | Offsets in the trace;        |
|                                    | needs file-system context    |
+------------------------------------+------------------------------+
| Descriptor type (file, socket,     | In the trace (event          |
| pipe, terminal)                    | 40000013); not used          |
+------------------------------------+------------------------------+
| Shared/overlapping region analysis | Not yet available            |
+------------------------------------+------------------------------+

Measurement Scope and Limitations
---------------------------------

The following aspects limit what the model can measure and should be stated
in the documentation of the metrics:

* **I/O library computation is useful time.** The CPU work of the I/O
  libraries (for example HDF5 compression, chunk management, or metadata
  handling) is not distinguished from the application computation and is
  counted in :math:`U`. A library that spends more CPU time therefore
  *increases* I/O Efficiency. In the VTKHDF validation with compression level
  1, the useful time grows from 1.16 s to 1.45 s per rank with 4M chunks,
  while I/O Efficiency stays around 70% and the execution time increases.
  Separating library computation requires call-stack information; comparing
  executions with and without compression measures the effect.

* **Phases are aggregated.** The metrics describe the whole execution.
  When an application has distinct I/O phases (for example a write phase and
  a read phase separated by barriers), the file-management time of the
  phases is added together, and a balance computed over the whole execution
  can dilute the imbalance of one phase. Per-phase metrics, with phases
  delimited by synchronization or user events, are a later extension. In
  the meantime, per-operation balance (read and write separately) captures
  part of the phase structure.

* **I/O not visible in the trace.** Memory-mapped I/O (``mmap``),
  asynchronous I/O (``aio_*``), and I/O performed by threads that are not
  instrumented are not measured. An I/O Efficiency close to 100% means that
  little *traced* I/O time was observed.

* **Descriptor types.** Calls on non-file descriptors (standard output,
  sockets, pipes) are currently counted as File I/O (see `Descriptor
  type`_).

* **Nested MPI-IO calls.** See the open question on MPI-IO and nested POSIX
  calls.


Relation with the Existing BasicAnalysis I/O Metrics
----------------------------------------------------

BasicAnalysis already reports the following I/O metrics:

+----------------------------+--------------------------------------------+
| Metric                     | Current formula                            |
+============================+============================================+
| I/O Efficiency             | U / (U + MPIIO + POSIXIO)                  |
+----------------------------+--------------------------------------------+
| MPI I/O Efficiency         | 1 - MPIIO / (P T)                          |
+----------------------------+--------------------------------------------+
| MPI I/O Load Balance       | avg / max over all execution units         |
+----------------------------+--------------------------------------------+
| POSIX I/O Efficiency       | 1 - POSIXIO / (P T)                        |
+----------------------------+--------------------------------------------+
| POSIX I/O Load Balance     | avg / max over all execution units         |
+----------------------------+--------------------------------------------+

*Decision (2026-10-18):* **I/O Efficiency is preserved** (it already
includes MPI-IO), and the other current I/O metrics (MPI I/O Efficiency, MPI
I/O Load Balance, POSIX I/O Efficiency, and POSIX I/O Load Balance) are
**replaced** by the new model:

* I/O Efficiency is decomposed into Data Access and File Management
  Efficiency, both including the POSIX, ANSI C, and MPI-IO calls.
* The API split is reported as a contribution (MPI-IO versus POSIX and
  ANSI C).
* The current API-specific efficiencies (:math:`1 - X/(P T)`) are
  replaced by the I/O time fractions (average and maximum).
* The current API-specific load balances are replaced by the per-operation
  load balances and the Data Access and File Management summaries.

Any change of definition or name of an existing metric changes the
BasicAnalysis outputs of existing traces and must be listed in the release
notes.


Validation with the VTKHDF Case (POP3 Ticket 668)
-------------------------------------------------

The proposed metrics were computed on 2026-10-18 with the current
BasicAnalysis raw data (branch ``feature/io-metrics``) for the eight
UnstructuredGrid traces of the chunk-size study:

* Application: ``vtkhdf_benchmark_parallel`` (VTKHDF, HDF5 1.14), 112 MPI
  ranks on one MareNostrum 5 GPP node, GPFS scratch, compression level 1.
* Traces: ``Ticket-668/analysis-chunking-exp/extrae_traces/
  res8k_edge500_diff_chunk_comp1-gpfs-scratch/*.uGrid.prv``.
* Reference analysis: ``Ticket-668/slide/POP3_VTKHDF-SAM_v4/v5``.

These traces contain only ``read``, ``write``, ``open``, ``close``, and
``lseek``; the sum of the per-operation times equals the total POSIX I/O
time for all eight traces.

Performance factors and time diagnostics (percentages):

+-------+------+-------+-------+-------+------+--------+-------+-------+
| Chunk | T(s) | IOEff | DAEff | FMEff | IO/T | IOmx/T | Read  | Open  |
|       |      |       |       |       |      |        | share | share |
+=======+======+=======+=======+=======+======+========+=======+=======+
| 50k   | 2.18 | 67.3  | 76.3  | 88.2  | 25.8 | 31.4   | 60.4  | 89.4  |
+-------+------+-------+-------+-------+------+--------+-------+-------+
| 100k  | 2.06 | 68.3  | 78.1  | 87.4  | 25.6 | 31.6   | 61.6  | 90.6  |
+-------+------+-------+-------+-------+------+--------+-------+-------+
| 150k  | 2.07 | 68.7  | 79.0  | 87.1  | 25.9 | 31.4   | 62.6  | 88.2  |
+-------+------+-------+-------+-------+------+--------+-------+-------+
| 250k  | 2.10 | 69.5  | 79.4  | 87.5  | 24.0 | 28.9   | 66.6  | 89.5  |
+-------+------+-------+-------+-------+------+--------+-------+-------+
| 500k  | 2.11 | 70.6  | 79.9  | 88.4  | 23.3 | 30.3   | 69.9  | 89.8  |
+-------+------+-------+-------+-------+------+--------+-------+-------+
| 1M    | 2.53 | 60.2  | 80.7  | 74.6  | 31.2 | 34.4   | 74.1  | 97.8  |
+-------+------+-------+-------+-------+------+--------+-------+-------+
| 2M    | 2.75 | 65.2  | 73.1  | 89.2  | 23.4 | 39.7   | 72.7  | 94.8  |
+-------+------+-------+-------+-------+------+--------+-------+-------+
| 4M    | 2.67 | 69.9  | 76.3  | 91.6  | 23.3 | 29.1   | 73.6  | 94.1  |
+-------+------+-------+-------+-------+------+--------+-------+-------+

*Read share* is the Read Time Contribution and *Open share* the Open
Contribution to File Management time.

Characteristics:

+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| Chunk | Reads | Opens | Mean  | Mean  | Open   | Read   | Write  | U avg  |
|       | /rank | /rank | read  | write | µs per | LB     | LB     | (s)    |
|       |       |       | size  | size  | call   |        |        |        |
+=======+=======+=======+=======+=======+========+========+========+========+
| 50k   | 4457  | 347   | 6.9KB | 0.09MB| 522    | 0.84   | 0.57   | 1.16   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| 100k  | 4310  | 348   | 7.2KB | 0.17MB| 546    | 0.86   | 0.61   | 1.13   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| 150k  | 4258  | 348   | 7.3KB | 0.24MB| 564    | 0.85   | 0.70   | 1.18   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| 250k  | 4219  | 347   | 7.4KB | 0.35MB| 530    | 0.82   | 0.63   | 1.15   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| 500k  | 4191  | 347   | 8.0KB | 0.57MB| 502    | 0.87   | 0.46   | 1.18   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| 1M    | 4177  | 347   | 9.0KB | 0.87MB| 1416   | 0.88   | 0.56   | 1.19   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| 2M    | 4168  | 347   | 7.3KB | 1.12MB| 545    | 0.89   | 0.21   | 1.21   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+
| 4M    | 4166  | 347   | 7.4KB | 1.73MB| 469    | 0.88   | 0.44   | 1.45   |
+-------+-------+-------+-------+-------+--------+--------+--------+--------+

Observations:

#. **The model reaches the conclusions of the manual analysis.** I/O
   Efficiency (60--71%) triggers the investigation in all executions, and
   the decomposition points to Data Access (DAEff 73--81%). The diagnostics
   then show the findings of the slides: about 4,200 reads per rank with a
   mean size of 7--9 KB for every chunk size (small requests, likely HDF5
   metadata), and 347 opens per rank, with open accounting for about 90% of
   File Management time.

#. **Mean duration per operation explains the 1M execution.** The number
   of opens is the same as in the other executions, but each open takes
   1,416 µs instead of about 500 µs. File Management Efficiency drops to
   74.6% and I/O Efficiency to 60.2%. This points to the interaction with
   the file system during that run rather than to a change in the
   application pattern.

#. **Per-operation balance explains the 2M execution.** Its execution time
   increases mainly because of MPI waiting (0.72 s per rank, against
   0.30--0.47 s in the others), while I/O Efficiency (65.2%) is similar to
   the other executions. Write LB is 0.21, Read LB 0.89, and the combined
   DALB 0.49. :math:`IOFraction_{max}` (39.7%) is also clearly higher than
   :math:`IOFraction_{avg}` (23.4%). The slowest writer is not rank 0 (the
   writer of the common file), which suggests a run-to-run file-system
   effect rather than the application decomposition.

#. **The mean write size follows the chunk size, but the reads do not.**
   The write size grows from 0.09 MB to 1.73 MB with the chunk size, while
   the number and size of the reads hardly change. Chunk tuning therefore
   affects the writes, but not the small-read pattern that dominates Data
   Access time.

#. **Useful time includes library computation.** With 4M chunks, the useful
   time per rank grows to 1.45 s (about 1.15 s for the other chunk sizes),
   possibly because of the compression of larger chunks, and the execution
   time increases while I/O Efficiency remains at 69.9%.

#. **The linear histogram does not resolve the small reads.** With 4M
   chunks, 99.8% of the reads fall in the first interval [8 B, 47 KB).

#. **The exact maximum needs the per-unit data.** With 4M chunks,
   :math:`\max_i R_i + \max_i W_i` = 649 ms while
   :math:`\max_i (R_i + W_i)` = 600 ms.


Open Formal and Design Questions
--------------------------------

#. **I/O participant definition**

   Which execution units should participate in Data Access and File Management
   Load Balance calculations? The model should distinguish intentional non-I/O
   ranks from actual imbalance among I/O participants.

#. **Data Access Load Balance raw data**

   Do the current Paraver analyses provide the per-rank combined ``read +
   write`` time required to compute ``DA_max`` correctly?

   In general:

   .. math::

      \max_i(R_i + W_i) \ne \max_i(R_i) + \max_i(W_i)

   *Answer:* yes. ``io_calls_time.stats.csv`` has one row per execution unit;
   only the parser has to change (see `Data Access Load Balance`_).

#. **File Management Load Balance raw data**

   The same issue applies to ``FM_i = O_i + C_i + S_i``. A correct ``FM_max``
   requires the combined per-rank quantity or an equivalent Paraver analysis.

   *Answer:* same as above; the per-row data gives the exact ``FM_i``.

#. **Request-size comparison across traces**

   Paraver adaptive histograms are appropriate for single-execution
   characterization, but cross-trace comparison may require common re-binning
   or higher-level scalar statistics.

   *Proposal:* power-of-two intervals, identical in every trace (see
   `Interval boundaries`_). They also solve the lack of resolution of the
   linear intervals for small requests.

#. **Request granularity scalar**

   Should BasicAnalysis define an additional scalar metric describing how
   fragmented transferred volume is into requests, or are operation count,
   mean request size, and the adaptive histogram sufficient? Any such metric
   should avoid arbitrary universal request-size thresholds.

#. **Access-pattern extraction**

   Can BasicAnalysis efficiently obtain ``rank, file, offset, size,
   operation`` information from Paraver without making trace processing
   prohibitively expensive?

#. **Alignment context**

   Which filesystem parameters are required before BasicAnalysis can move from
   reporting alignment-relevant characteristics to diagnosing misalignment?

#. **Higher-level I/O libraries**

   How much can BasicAnalysis infer from POSIX behavior alone, and when should
   it explicitly recommend inspection of MPI-IO, HDF5, NetCDF, ADIOS, or other
   intermediate layers?

#. **Bandwidth / transfer rate**

   What denominator should be used for a meaningful data-transfer performance
   metric? ``bytes / sum(POSIX call durations)`` should not automatically be
   called application or filesystem bandwidth. A phase-based elapsed-time
   definition may be preferable when phase boundaries can be established.

   In addition, the calls of concurrent execution units overlap in time, so
   the sum of call durations is not an elapsed time. The per-call transfer
   rate (size / duration of each call), used as a histogram in the VTKHDF
   analysis, is a well-defined characteristic of individual requests and
   could be offered later under that name rather than as "bandwidth".

#. **Efficiency thresholds**

   The threshold used to trigger deeper I/O analysis should be treated
   separately from workload-specific diagnostic thresholds. Fixed rules such
   as ``request < 1 MB = small`` should be avoided unless justified by the
   particular I/O system and workload.

#. **Classification of additional calls**

   Should ``fsync``/``fdatasync`` be Data Access or Other I/O? Which calls,
   if any, should be excluded (for example ``ioctl``)?

   *Decided:* see `Classification of the traced calls`_.

#. **Descriptor type**

   Should the model cover regular files only? How much time do non-file
   descriptors (standard output, sockets, pipes) take in typical traces?

   *Partial answer (2026-10-28):* in cfdem the non-file and untraced
   descriptors take 94.9% of the write calls and 2.9% of the write time.
   The access-pattern proposal excludes them; the efficiencies still
   include them.

#. **Relation with the existing I/O metrics**

   How should the new factors relate to the current I/O Efficiency (which
   includes MPI-IO) and to POSIX I/O Efficiency and Load Balance?

   *Decided:* see `Relation with the Existing BasicAnalysis I/O Metrics`_.

#. **MPI-IO and nested POSIX calls**

   MPI-IO implementations perform POSIX calls internally. If Extrae records
   both levels, the current I/O Efficiency counts the same time twice. This
   must be checked with an MPI-IO trace before defining a parent metric that
   combines MPI-IO and POSIX.

   *Answered:* Extrae does not trace the internal POSIX calls of MPI-IO by
   default (overhead). The model assumes this default.

#. **Phases**

   Should the I/O metrics be computed per phase (delimited by
   synchronization or user events)? See `Measurement Scope and
   Limitations`_.

#. **Access pattern** (proposal of 2026-10-28, see `Access Pattern`_)

   *Decided (2026-10-29):* the classes and the Darshan meaning of
   *sequential* as proposed, strided when the gap equals the previous gap;
   ``SEEK_SET`` assumed and documented, without detection of relative
   seeks; redundant seeks reported in the *Which calls take the time?*
   card and the re-accessed volume in the *What requests are made?* card;
   the Extrae team is asked to record the ``pread``/``pwrite`` offset and
   the seek ``whence``, and which public version includes the offset
   event; shared files (partitioned versus interleaved regions) left for
   later.

   * Are the classes (consecutive, strided, forward, backward) and the
     Darshan meaning of *sequential* the right ones? Should a strided
     pattern need more than two equal gaps?
   * Is the ``SEEK_SET`` assumption acceptable, or should seeks that
     look like ``SEEK_CUR``/``SEEK_END`` be detected and their stream
     marked as unknown until the next seek?
   * Should seeks to the current position and the re-accessed volume be
     reported, and where (requests card, File Management)?
   * Should the Extrae developers be asked to record the offset of
     ``pread``/``pwrite`` and the ``whence`` of the seeks?
   * Which Extrae version introduced the offset event ``40000075``? The
     User Guide should state the minimum version for the access pattern.
   * Shared files: is the per-process classification enough for a first
     version, leaving partitioned versus interleaved regions for later?

Design Principles to Preserve
-----------------------------

#. **Start from time.** The model detects performance loss from the time
   actually paid by the application on the measured system.

#. **Use other units to explain time.** Bytes, requests, sizes, files, offsets,
   and similar characteristics explain observed I/O time; they are not
   automatically efficiency factors.

#. **Separate detection from causality.** BasicAnalysis should identify
   suspicious behavior and guide deeper analysis, but should not claim a
   filesystem, library, or application root cause without sufficient evidence.

#. **Avoid universal I/O-pattern thresholds.** Request size and similar
   properties must be interpreted in the context of the access pattern and I/O
   system.

#. **Combine diagnostic evidence.** Small requests, shared files, or a low
   balance value should not be interpreted in isolation.

#. **Respect the I/O software stack.** The POSIX pattern is the behavior
   presented to the POSIX layer and may have been transformed by higher-level
   libraries.

#. **Do not confuse necessary I/O with inefficient I/O.** A data-intensive
   application may have low Data Access Efficiency because it must move a large
   volume of data.

#. **Keep BasicAnalysis and Paraver complementary.** BasicAnalysis should
   screen, quantify, characterize, and recommend where to investigate. Paraver
   remains the tool for detailed temporal and causal inspection.

#. **Keep extraction isolated and presentation integrated.** I/O raw data can
   remain hierarchically isolated in extraction/storage while the resulting
   performance factors and diagnostics are integrated into the standard and
   interactive BasicAnalysis reports.

Proposed First-Version Scope
----------------------------

*Decision (2026-10-18): approved.*

#. Classification of the traced calls (POSIX, ANSI C, and MPI-IO) into Data
   Access and File Management.
#. I/O Efficiency (preserved).
#. Data Access Efficiency.
#. File Management Efficiency.
#. API contribution (MPI-IO versus POSIX and ANSI C).
#. I/O time fractions (average and maximum) and I/O participation.
#. Read and Write time contributions.
#. Read and Write Load Balance, and Data Access Load Balance as a summary,
   computed from the per-unit rows.
#. Read/write time, volume, operation count, mean duration, and mean request
   size.
#. Read/write request-size distributions (count and time per interval,
   power-of-two intervals) and coverage.
#. File Management operation-time contributions, counts, and mean
   durations.
#. File Management Load Balance (in particular Open LB), computed from the
   per-unit rows.
#. Distinct files, per-file open count/time views, and ranks per file /
   files per rank.
#. Filename coverage.

Offset-based access pattern, alignment, overlapping access analysis,
per-call transfer rate, per-phase metrics, and the separation of I/O library
computation should be treated as later extensions rather than prerequisites
for the first I/O report.


Review Log
----------

*2026-10-29* -- Access pattern per file (user: the totals add all the
files): the classes are also counted per file (and for the descriptors
without a file name); the files table of the report and of the standard
output shows the share of the bytes read and written in consecutive
requests, and ``io_files.csv`` the shares of the requests and bytes of every
class. VTKHDF 100k: part files 93% (read) and 94% (write) of the bytes in
consecutive requests, common file 84% and 55%, hidden in the totals (the
part files hold 99% of the requests).

*2026-10-29* -- Access pattern decided and implemented (recommendations
accepted; see the open question). ``rawdata.parse_io_access_pattern_trace``
reads the filtered trace, which also keeps the descriptor type
(``40000013``) and the seek offset (``40000075``); positions per process
and descriptor; requests counted when the call ends, as the requests and
files. Diagnostics: volume in consecutive requests, volume re-accessed,
and offset coverage of the reads and writes, and redundant seeks;
``io_access_pattern.csv``; access-pattern plots in the requests card and
the redundant seeks in the calls card. Validated: VTKHDF 100k and 2M
identical to the prototype through the filtered trace (9.22% and 9.24%
redundant seeks, 0.032 s of 0.296 s of seek time in 100k); cfdem: 40,084
terminal writes excluded, the 19,738 writes to descriptor 3 (no traced
open) with an unknown offset.

*2026-10-29* -- Access-pattern proposal completed: the offset event is
recent (added to Extrae at our request; the cfdem trace of April 2025 does
not have it), so a seek without an offset makes the position unknown until
the next ``open`` and the coverage is always reported; calls are attributed
to files through the descriptor of the traced ``open`` (VTKHDF 100k: 99.6%
of the calls with file and offset, 0.4% with offset but no file name);
positions kept per process, not per thread; ``O_APPEND`` and descriptors
not followed (``dup``, ``openat``, ``fork``) added to the limitations.

*2026-10-28* -- Proposal (access pattern): offsets of ``read``/``write``/
``fread``/``fwrite`` rebuilt per process and descriptor from ``open``
(position 0), seeks (recorded offset, ``SEEK_SET`` assumed), and request
sizes; ``pread``/``pwrite`` and MPI-IO have no recorded offset (Extrae
5.1.3 source). Classes consecutive, strided, forward, backward, and
unknown offset, as shares of requests, bytes, and time; seeks to the
current position and re-accessed volume. Prototype on VTKHDF uGrid
100k/2M (reads: 78% of the requests jump, but 93--95% of the bytes are
consecutive; writes 2M: 63% of the bytes after a forward gap; 9.2% of the
seeks to the current position), cfdem (95% of the writes on terminal or
untraced descriptors, 2.9% of the write time), and SPH-EXA (MPI-IO only,
no offsets). Not implemented; open questions added.

*2026-10-20* -- Report plots (user: plots instead of tables): each card
shows its diagnostics as bar plots, one bar per execution, with the table of
values collapsed below. Share of the I/O time as one stacked bar per
execution (by call, and by API when MPI-IO is used); mean duration and mean
request size on logarithmic scales; per-file I/O time split into read,
write, and other calls, labelled with the main-process share. The
request-size coverage (near 100%) and the four file diagnostics stay as
tables.

*2026-10-20* -- Report organization: the I/O Analysis view had a single
diagnostics table of about 45 rows and a long reading guide. The
diagnostics are now in four cards, in reading order after the efficiency
table and its trends: *Where is the I/O time spent?* (time fractions,
participation, contributions, load balance), *Which calls take the time?*
(one row per call: time, operations, mean duration), *What requests are
made?* (one row per read and write: volume, mean size, size coverage, and
the request-size histograms), and *Which files are accessed?* (file
diagnostics and the top files). Each card explains its values; the guide
keeps only the reading order. The standard output and ``io_metrics.csv``
do not change.

*2026-10-20* -- Implementation (files and processes per file, POSIX and
ANSI C): the filtered trace also keeps the descriptor (``40000010``) and
file name (``40000059``) events. Extrae 5.1.3 records the descriptor
returned by ``open`` (``fileno`` for ``fopen``) in the same record as the
file name, and the descriptor in every call (ANSI C: ``fileno`` of the
stream); MPI-IO records neither the file nor the handle. Calls are
attributed per process (descriptors are shared by the threads) until the
descriptor is closed; descriptors without a traced open (stdout, files
opened before the tracing starts in a process, ``openat``/``creat``/``dup``
not instrumented, ``fopen`` records without a file name) go to one unnamed
group. Calls are counted at their end, as the requests. Decision: the
sharing indicator is the volume moved by the main process of each file
(threshold-free; 100% one process per file, 100/N % shared evenly), not a
count of shared files. Validation: bytes, requests, and time of the reads
and writes identical to the request-size distribution (cfdem, VTKHDF);
call time of all the files 3.264 s versus 3.271 s of POSIX I/O in cfdem
(44 nested calls not counted, as in the requests). VTKHDF 100k: 113 files,
112 processes per file, main processes 96.4%, coverage 94.9% (12 processes
write their part file through a descriptor opened before their first
traced call); cfdem: 320 files, main processes 100%, one probe file with
80% of the POSIX I/O time (223 writes of about 280 bytes). Also fixed: the
``.pcf`` value labels keep their spaces (file names), and the open calls of
a thread are no longer keyed by CPU.

*2026-10-20* -- Implementation (MPI-IO request sizes): the filtered trace
also keeps the MPI-IO call (``50000005``) and size (``50000110``) events.
Extrae records count x datatype size (requested bytes) at the entry and the
exit of every MPI-IO call; split collectives carry the size in ``*_begin``
(``*_end`` has none): one request with the time of both calls; nonblocking
calls are not instrumented (Extrae 5.1.3). Read/write identified by the
``.pcf`` labels. One distribution per operation for all the APIs (as the
classification by meaning); ``io_request_sizes.csv`` by API. Coverage counts
the calls of every API except the MPI-IO ``*_end`` calls. Validated on
SPH-EXA (64 ranks, ``MPI_File_read_at``): 836 requests and 192,308,840
bytes, identical to a direct count in the trace; VTKHDF and cfdem (POSIX
only) unchanged.

*2026-10-20* -- Implementation (request sizes, POSIX and ANSI C): read and
write families (Extrae values 1, 3, 5, 7, 9 and 2, 4, 6, 8, 10), volume,
mean request size, request-size coverage, and distribution in power-of-two
intervals (count, time, bytes and shares). Decision: Paraver filters the
trace to the I/O call and size events (``io-requests-filter.xml``) and
Python bins the requests (``rawdata.parse_io_requests_trace``). The
equivalent Paraver histograms (32 step windows, ``Is In Range [2^k, inf)``,
since Paraver has no logarithm) are generated by
``cfgs/generate_io_request_size_cfgs.py`` for inspection, but take 6 min on
the full cfdem trace and 3 min per VTKHDF trace on the filtered trace
(about one million calls), against 4 s in Python. MPI-IO request sizes
(event 50000110) are the next step.

*2026-10-19* -- Decision (useful time of the I/O units): the I/O factors
always use the useful time of the Host execution units, the units that
perform File I/O (``useful_io_tot``: the THREAD rows of the timings table;
``useful_tot`` as a fallback). In GPU traces the kernel time of the GPU
streams is excluded. SPH-EXA 64 ranks: Host useful 308.6 s versus 3611.7 s
with the streams; I/O Efficiency 99.51% -> 94.58%, Critical-Path 99.46% ->
94.04%. CPU traces unchanged (cfdem identical).

*2026-10-19* -- Decision (multiplicative structure): I/O Critical-Path
Efficiency = I/O Efficiency x I/O Load Balance, with the critical-path I/O
time as the sum of the per-operation maxima (units synchronized after each
kind of call) and a single load-balance factor (not split into Data Access
and File Management). Validated with VTKHDF 100k/2M (I/O Load Balance 88.49
/ 76.19%; predicted extra waiting 0.38 s per rank, measured MPI time +0.44 s)
and cfdem 4p (95.71%).

*2026-10-19* -- Implementation: I/O diagnostics table in the I/O Analysis
view and in the printable report (groups I/O time, Data Access, File
Management, Operations; no efficiency colors; unused rows omitted).

*2026-10-19* -- Stricter thresholds for the I/O efficiencies (Critical
< 90%, Attention 90--95%, Good >= 95%), defined per metric in
``metrics/definitions.yaml``; the report colors follow per-metric thresholds.

*2026-10-19* -- Implementation step 1 (branch ``feature/io-metrics``):
call classification, Data Access and File Management Efficiency, I/O time
fractions, participation, API, read/write and File Management
contributions, participant load balances, and per-operation time, count,
and mean duration (``iometrics.py``, ``io_metrics.csv``, standard output,
report tree, User Guide). The four API-specific metrics are replaced.
Verified on the VTKHDF uGrid traces, a cfdem trace with ANSI C calls
(Ticket 570), and an SPH-EXA trace with MPI-IO: the factors multiply to I/O
Efficiency, and all other outputs are unchanged. Remaining steps: request
sizes and volume (power-of-two intervals, families), report diagnostics
view, files (ranks per file).

*2026-10-18* -- Decisions: call classification by meaning across the APIs
(no Other I/O category), structure by type of operation including MPI-IO
(option A), I/O Efficiency preserved and the other current I/O metrics
replaced, first-version scope approved. Corrected: the I/O offset is only
recorded for seek calls.

*2026-10-18* -- Review of the design against the current implementation
(branch ``feature/io-metrics``) and the VTKHDF case (POP3 Ticket 668).
Added: classification of the traced calls and Other I/O; descriptor type;
note on the threshold versus the execution-time fraction; I/O time fractions
(average and maximum) and the delegated-I/O example; order dependence of
File Management Efficiency; mean duration per operation; per-operation load
balance and availability of the per-unit raw data; time per request-size
interval and power-of-two intervals; availability of offsets in the trace;
ranks per file from the existing raw data; measurement scope and
limitations; relation with the existing BasicAnalysis I/O metrics;
validation with the VTKHDF traces; answers to open questions 2--4 and new
open questions; updated report tree, summary tables, raw-data coverage, and
first-version scope.
