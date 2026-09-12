.. _cha:methodology:

Performance Analysis Methodology
################################

BasicAnalysis organizes performance analysis through a hierarchy of efficiency
metrics and a set of complementary analytical views. The objective is not only
to report individual efficiency values, but also to help users understand
which performance factors contribute to the observed efficiency losses and
which aspects of the execution should be investigated further.

The analysis can progress from application-level behavior toward more specific
performance factors, parallel runtimes, and execution components. Depending on
the analysis objective, users can combine several analytical views to
understand the overall performance behavior or focus on the view most relevant
to a particular performance aspect.

The methodology is organized around the following perspectives:

* **Hierarchical Efficiency Analysis**, which decomposes high-level efficiency
  metrics into progressively more specific contributing factors.
* **Parallel Runtime Model**, which attributes parallel-efficiency behavior to
  the active parallel runtimes.
* **Runtime-Specific Analysis**, which provides additional metrics describing
  the behavior of individual parallel runtimes.
* **Execution Domains**, which provides a complementary Host/Device analysis
  for accelerator applications.
* **I/O Analysis**, which provides complementary metrics characterizing the
  contribution and distribution of File I/O activity.
* **Scaling Analysis**, which examines how performance and efficiency factors
  evolve across execution configurations.

The following sections describe how these perspectives are related and how
they can be used according to the objective of the performance assessment.


Hierarchical efficiency analysis
================================

As BasicAnalysis automates the computation of POP performance metrics, it
follows the POP hierarchical metric model, in which high-level efficiencies
are decomposed into more specific contributing factors. This hierarchy allows
the analysis to progress from an overall efficiency loss toward increasingly
specific factors that can explain it.

At the application level, the hierarchy starts with Global Efficiency, which
is decomposed into Parallel Efficiency and Computation Scalability:

.. math::

   Global\ Efficiency =
   Parallel\ Efficiency \times Computation\ Scalability

These two factors represent the two main sources of inefficiency in parallel
applications. Parallel Efficiency captures the overheads introduced by
parallel execution, while Computation Scalability captures how the computation
scales as the computational resources increase.

Parallel Efficiency
-------------------

Parallelization requires dividing the application workload among the available
parallel units and defining the interactions required among those units to
complete the computation.

Parallel Efficiency characterizes the efficiency of this parallelization. Its
losses can arise from two fundamental aspects: an uneven distribution of the
computational workload among the parallel units and the overhead associated
with the communication and coordination required among them.

Therefore, Parallel Efficiency is decomposed as:

.. math::

   Parallel\ Efficiency =
   Load\ Balance \times Communication\ Efficiency


This results in the following application-level hierarchy:

.. graphviz:: graphs/05_base_efficiency_hierarchy.dot
   :align: center

Load Balance characterizes how evenly the computational workload is
distributed among the parallel units, while Communication Efficiency
characterizes the efficiency loss associated with the communication and
coordination required among them.

At this level of the hierarchy, communication is a general parallel-execution
concept and is not restricted to message passing or to a particular
programming model. Its specific interpretation depends on the parallel
execution model being analyzed.

Communication Efficiency can be further decomposed to distinguish losses
associated with serialization from those associated with data transfer:

.. math::

   Communication\ Efficiency =
   Serialization\ Efficiency \times Transfer\ Efficiency

Serialization Efficiency characterizes losses associated with dependencies
and synchronization among parallel units, while Transfer Efficiency
characterizes the additional cost associated with transferring the information
required for their interaction.

The Communication Efficiency branch can therefore be represented as:

.. graphviz:: graphs/05_communication_hierarchy.dot
   :align: center

The way these communication factors are obtained depends on the parallel
execution model. BasicAnalysis directly derives the MPI factors using
idealized communication information generated through Dimemas. For hybrid
executions, additional runtime contributions can be derived from the
relationships between the hybrid- and runtime-level metrics, as described in
the Runtime-Specific Analysis section.

Computation Scalability
-----------------------

The other main factor contributing to Global Efficiency is Computation
Scalability. While Parallel Efficiency captures the overheads introduced by
parallel execution, Computation Scalability characterizes how the computation
scales as the computational resources increase.

Unlike Parallel Efficiency, Computation Scalability is evaluated relative to
a reference execution. It captures changes in the computational behavior as
the application scales, independently of the overheads attributed to parallel
execution.

Computation Scalability is decomposed as:

.. math::

   Computation\ Scalability =
   IPC\ Scalability \times
   Instruction\ Scalability \times
   Frequency\ Scalability

The scaling of the computation can therefore be decomposed into three
components: Instructions, IPC, and Frequency. These represent the three main
factors that determine the duration of the computation: the amount of work
performed (Instructions), the rate at which that work is executed (IPC), and
the operating speed of the computational resource (Frequency).

Together with the Parallel Efficiency decomposition introduced above, these
metrics complete the application-level efficiency hierarchy:

.. graphviz:: graphs/05_complete_efficiency_hierarchy.dot
   :align: center

The hierarchy provides a systematic way to navigate an efficiency analysis.
When a parent metric shows a significant loss, its child metrics can be
inspected to determine which performance factor contributes to that loss.

For example, a low Parallel Efficiency can lead to the inspection of Load
Balance and Communication Efficiency. If Communication Efficiency shows the
larger loss, Serialization Efficiency and Transfer Efficiency can then be
examined to distinguish whether the degradation is primarily associated with
dependencies and synchronization or with data-transfer costs.

Similarly, Computation Scalability can be investigated through its IPC, 
Instruction, and Frequency Scalability components to determine which 
factor contributes to the observed degradation.

The analysis can continue through the hierarchy until the available metrics
provide the level of detail required for the performance assessment.

This application-level hierarchy provides the basis for the additional
analysis performed by BasicAnalysis. When multiple parallel runtimes
participate in the execution, the Parallel Efficiency branch can be extended
to distinguish the contribution of each runtime while preserving the same
underlying performance factors. This extension is introduced by the Parallel
Runtime Model in the following section.

The complete definitions and formulations of these metrics are provided in
:doc:`06_metrics`.


Parallel Runtime Model
======================

The application-level hierarchy introduced in the previous section can also
be applied to applications that combine multiple parallel runtimes. In this
case, however, Parallel Efficiency and its contributing factors characterize
the combined behavior of the parallel runtimes participating in the execution.

For a hybrid application, this application-level Parallel Efficiency 
is referred to as **Hybrid Parallel Efficiency**. Similarly, Hybrid Load Balance
and Hybrid Communication Efficiency characterize workload distribution and
communication and coordination for the hybrid execution as a whole.

This decomposition identifies which performance factor limits the hybrid
execution, but it does not reveal how the different parallel runtimes
contribute to that factor. To provide this additional level of analysis,
BasicAnalysis uses the **Parallel Runtime Model**.

The Parallel Runtime Model introduces a runtime dimension into the Parallel
Efficiency hierarchy. For a hierarchical hybrid execution, it distinguishes
an **outer parallel runtime** and an **inner parallel runtime**. For example,
MPI is the outer runtime and OpenMP the inner runtime in MPI+OpenMP, while MPI
is the outer runtime and the accelerator runtime the inner runtime in
MPI+CUDA and MPI+HIP.

Parallel-runtime performance factors
------------------------------------

The Parallel Runtime Model preserves the three performance factors introduced
for parallel execution---Parallel Efficiency, Load Balance, and Communication
Efficiency---and evaluates them at different runtime levels.

For compactness, the following notation is used in the equations in this 
section:

* **PE**: Parallel Efficiency
* **LB**: Load Balance
* **CommE**: Communication Efficiency

The model distinguishes three levels: the **hybrid level**, the
**outer-runtime level**, and the **inner-runtime level**.


At the hybrid level, the metrics characterize the complete hybrid
parallelization, considering all participating parallel runtimes. The
performance-factor decomposition remains:

.. math::

   Hybrid\_PE = Hybrid\_LB \times Hybrid\_CommE

Here, :math:`Hybrid\_LB` characterizes workload distribution across the
complete hybrid execution, while :math:`Hybrid\_CommE` characterizes the
communication and coordination overhead associated with all participating
parallel runtimes.

.. graphviz:: graphs/05_hybrid_parallel_efficiency.dot
   :align: center


To isolate the contribution of the outer runtime, the execution is analyzed
from its perspective. Activity associated with the outer runtime is treated
as parallel-runtime overhead, while execution outside that runtime is
considered computation at this level.

The same performance-factor decomposition is preserved:

.. math::

   Outer\_PE = Outer\_LB \times Outer\_CommE

For MPI+OpenMP, MPI is the outer runtime. From the MPI perspective, time
inside MPI represents MPI-runtime activity, while execution outside MPI,
including OpenMP activity, is considered computation. The resulting MPI 
metrics therefore characterize the performance factors associated with 
the outer parallelization.

.. graphviz:: graphs/05_hybrid_outer_parallel_efficiency.dot
   :align: center

Once the hybrid and outer-runtime factors are known, the contribution 
of the inner runtime can be derived using the multiplicative structure 
of the model. For Parallel Efficiency:

.. math::

   Hybrid\_PE = Outer\_PE \times Inner\_PE

The same relationship applies to Load Balance and Communication Efficiency:

.. math::

   Hybrid\_LB = Outer\_LB \times Inner\_LB

.. math::

   Hybrid\_CommE = Outer\_CommE \times Inner\_CommE

Therefore, the inner-runtime performance factors are obtained as:

.. math::

   Inner\_PE = \frac{Hybrid\_PE}{Outer\_PE}

.. math::

   Inner\_LB = \frac{Hybrid\_LB}{Outer\_LB}

.. math::

   Inner\_CommE = \frac{Hybrid\_CommE}{Outer\_CommE}

The inner-runtime metrics therefore represent the contribution required to
relate the outer-runtime factors to those observed for the complete hybrid
execution. 

.. graphviz:: graphs/05_hybrid_inner_parallel_efficiency.dot
   :align: center

The resulting generic metric hierarchy for a hybrid parallel application 
can be represented as follows:

.. graphviz:: graphs/05_generic_parallel_runtime_model.dot
   :align: center

The hierarchy can be followed either by performance factor, to examine 
Load Balance or Communication Efficiency across runtime levels, or by 
runtime, to examine the factors contributing to the parallel efficiency 
of the outer or inner runtime.

For an MPI+OpenMP execution, the outer and inner runtimes correspond to MPI
and OpenMP, respectively. The generic runtime decomposition described above
can therefore be expressed directly in terms of these two runtimes.

For Parallel Efficiency, the relationship becomes:

.. math::

   Hybrid\_PE = MPI\_PE \times OpenMP\_PE

and the OpenMP contribution is therefore obtained as:

.. math::

   OpenMP\_PE = \frac{Hybrid\_PE}{MPI\_PE}

The same decomposition applies to the other two performance factors. Hybrid
Load Balance is determined by the MPI and OpenMP Load Balance contributions,
while Hybrid Communication Efficiency is determined by the corresponding MPI
and OpenMP Communication Efficiency contributions:

.. math::

   Hybrid\_LB = MPI\_LB \times OpenMP\_LB

.. math::

   Hybrid\_CommE = MPI\_CommE \times OpenMP\_CommE

The resulting Parallel Runtime Model for an MPI+OpenMP application can
therefore be represented as:

.. graphviz:: graphs/05_mpiomp_parallel_runtime_model.dot
   :align: center

When MPI is the outer runtime, MPI Communication Efficiency can be further 
decomposed into MPI Serialization Efficiency and MPI Transfer Efficiency. 
These factors provide a deeper characterization of the communication losses 
associated with the MPI runtime.

Interpreting derived runtime contributions
------------------------------------------

Unlike the hybrid and outer-runtime factors, inner-runtime contributions are
not independent efficiency measurements. They are derived from the
multiplicative relationship between the hybrid and outer-runtime levels.

Because an inner-runtime contribution is obtained as the ratio between the
corresponding hybrid and outer-runtime factors, its value may exceed 100% when
the hybrid factor is greater than the outer-runtime factor. Such a value
should not be interpreted as an independently measured physical efficiency
above its ideal value, but as the relative contribution of the inner runtime
within the multiplicative model.

Inner-runtime factors should therefore be interpreted together with the
hybrid and outer-runtime factors from which they are derived.



Runtime-Specific Analysis
=========================

The Parallel Runtime Model identifies how the active parallel runtimes
contribute to the main parallel-performance factors. Once a runtime is
identified as contributing to an efficiency loss, however, additional
information may be required to understand the behavior behind that
contribution.

BasicAnalysis therefore complements the Parallel Runtime Model with
**Runtime-Specific Analysis**. Depending on the programming model, this
analysis can either extend the decomposition of the common performance
factors or introduce additional metrics that characterize behavior specific
to a particular runtime.

These two perspectives are complementary. The Parallel Runtime Model preserves
common performance factors across runtime levels, allowing their contributions
to the hybrid execution to be distinguished. Runtime-specific metrics provide
a more specialized view of the execution and can expose sources of
inefficiency that are meaningful for a particular programming model.

The runtime-specific information currently available depends on the parallel
programming model and on the information that can be obtained from the
analyzed traces.

Extending the Parallel Runtime Model
------------------------------------

The Parallel Runtime Model introduced in the previous section attributes
Parallel Efficiency, Load Balance, and Communication Efficiency to the
parallel runtimes participating in a hybrid execution. When additional
information is available, the same multiplicative principle can be extended
to the factors explaining Communication Efficiency.

Communication Efficiency can be decomposed into Serialization Efficiency and
Transfer Efficiency:

.. math::

   CommE = Serialization \times Transfer

Serialization Efficiency characterizes losses associated with dependencies
and synchronization among parallel units, while Transfer Efficiency
characterizes the additional overhead associated with the mechanisms required
to perform their interaction.

For an MPI+OpenMP execution, BasicAnalysis extends this decomposition to the
hybrid and runtime levels. This makes it possible not only to identify whether
Communication Efficiency is limiting the hybrid execution, but also to
distinguish how MPI and OpenMP contribute to its Serialization and Transfer
components.

Hybrid and MPI communication factors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The MPI and hybrid communication factors are characterized from different
execution perspectives.

At the MPI level, BasicAnalysis uses an idealized MPI execution to separate
the effects associated with serialization from those associated with data
transfer. OpenMP activity is not modeled as an independent source of
parallel-runtime overhead at this level.

At the hybrid level, both MPI and OpenMP participate in the execution model.
Idealized execution information is used to separate structural limitations
from the additional overheads introduced by the mechanisms used to coordinate
and communicate among the parallel units.

This provides Serialization and Transfer factors at both the hybrid and MPI
levels. The remaining contribution can then be attributed to the OpenMP
runtime using the same multiplicative principle introduced by the Parallel
Runtime Model.

Deriving the OpenMP contribution
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Following the same multiplicative approach used for the other
parallel-runtime factors, Hybrid Serialization Efficiency is expressed in
terms of the MPI and OpenMP contributions:

.. math::

   Hybrid\_Serialization =
   MPI\_Serialization \times OpenMP\_Serialization

Similarly, Hybrid Transfer Efficiency is expressed as:

.. math::

   Hybrid\_Transfer =
   MPI\_Transfer \times OpenMP\_Transfer

The OpenMP contributions can therefore be derived from the corresponding
hybrid and MPI factors:

.. math::

   OpenMP\_Serialization =
   \frac{Hybrid\_Serialization}
        {MPI\_Serialization}

.. math::

   OpenMP\_Transfer =
   \frac{Hybrid\_Transfer}
        {MPI\_Transfer}

These relationships extend the runtime attribution introduced for Load
Balance and Communication Efficiency to the two factors that explain
Communication Efficiency.

Interpreting the OpenMP communication factors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

At the OpenMP level, Serialization and Transfer Efficiency should be
interpreted according to the mechanisms through which threads interact rather
than in terms of message passing.

**OpenMP Serialization Efficiency** characterizes structural limitations that
restrict concurrent execution, such as dependencies or limited available
parallelism.

**OpenMP Transfer Efficiency** characterizes additional OpenMP runtime
overheads associated with coordinating the parallel execution, including
synchronization, scheduling, and thread-management activity.

The terminology therefore preserves the common Communication Efficiency
decomposition while its runtime-specific interpretation reflects the
interaction mechanisms of OpenMP.

The resulting hierarchy can be represented as:

.. graphviz:: graphs/05_hybrid_communication_decomposition.dot
   :align: center

The OpenMP factors derived through this extension describe the contribution
of OpenMP to the communication-related factors observed in the hybrid
execution. They remain relative contributions within the Parallel Runtime
Model. The MPI+OpenMP metric hierarchy is therefore extended as follows:

.. graphviz:: graphs/05_mpiomp_parallel_runtime_model_extended.dot
   :align: center

A different perspective is required to characterize the OpenMP execution
itself. For this purpose, BasicAnalysis provides an isolated OpenMP analysis
that evaluates serial execution, load imbalance within parallel regions, and
OpenMP scheduling and fork/join overhead.


Isolated OpenMP analysis
------------------------

The OpenMP contributions derived through the Parallel Runtime Model describe
how the inner runtime contributes to the performance factors observed for the
complete hybrid execution. BasicAnalysis also provides an isolated OpenMP
analysis that examines the efficiency of the OpenMP execution itself.

Efficient OpenMP execution requires more than distributing work among
threads. The application must expose sufficient parallel work, distribute
that work evenly among the threads participating in each parallel region,
and manage the parallel execution without excessive runtime overhead.

The isolated OpenMP model therefore considers three main sources of
inefficiency: serial execution outside OpenMP parallel regions, load
imbalance among threads inside parallel regions, and OpenMP runtime overhead
associated with scheduling and fork/join activity.

Serial execution
^^^^^^^^^^^^^^^^

Execution outside OpenMP parallel regions limits the amount of work that can
be performed concurrently by the available threads. During these regions,
only the master thread is active while the remaining OpenMP threads do not
participate in the computation.

**OpenMP Serial Efficiency** characterizes the efficiency loss associated
with this serial part of the OpenMP execution. A low value therefore indicates
that a significant fraction of the available thread execution capacity is
lost because execution remains outside OpenMP parallel regions.

Load imbalance in parallel regions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Entering an OpenMP parallel region does not by itself guarantee efficient use
of the participating threads. The useful computational work must also be
distributed evenly among them.

**OpenMP Load Balance** characterizes differences in useful computation among
threads within each OpenMP parallel region. When some threads perform less
useful work than others, they finish their assigned work earlier and remain
without useful computation while other threads are still active.

A low OpenMP Load Balance therefore indicates an uneven distribution of useful
work inside OpenMP parallel regions.

Scheduling and fork/join overhead
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Even when sufficient parallel work is available and that work is well
balanced, the OpenMP runtime introduces overhead to create, coordinate, and
schedule the parallel execution.

**OpenMP Scheduling Efficiency** characterizes runtime overhead associated
with OpenMP scheduling and fork/join activity that is not attributed to
serial execution or useful-work imbalance.

A low OpenMP Scheduling Efficiency therefore indicates that OpenMP runtime
management represents a significant source of efficiency loss.


These three factors determine the isolated OpenMP Parallel Efficiency:

.. math::

   OMP\_PE =
   OMP\_Serial \times
   OMP\_LB \times
   OMP\_Sched

The metric hierarchy for the isolated OpenMP analysis can therefore 
be represented as:

.. graphviz:: graphs/05_openmp_efficiency_hierarchy.dot
   :align: center

Execution Domains
=================

Accelerator applications involve execution across two distinct but interacting
domains: the **Host**, where the CPU-side execution takes place and work is
prepared and submitted to the accelerator, and the **Device**, where the
offloaded work is executed.

This distinction is independent of the particular parallel programming model.
The Host may itself use a distributed- or shared-memory parallel runtime, while
the Device execution is managed through an accelerator programming model. For
example, the same Host/Device perspective can conceptually be applied to
MPI+GPU, OpenMP+GPU, or OpenACC+GPU applications.

The performance behavior observed in these two domains is complementary but
different. Inefficiency may originate from the Host execution or from the
mechanisms used to supply work to the accelerator, while other losses may
manifest on the Device through insufficient available work, data movement,
workload imbalance, or computation scalability.

The **Execution Domains** analysis separates these two perspectives in order
to identify where accelerator-related inefficiencies manifest:

* **Host**, characterizing CPU-side execution and the interaction with the
  accelerator;
* **Device**, characterizing the execution of work on the accelerator.

BasicAnalysis currently implements this analysis for MPI+GPU applications,
where MPI represents the Host-side parallel runtime and CUDA or HIP manages
the accelerator execution.

The Host/Device efficiency model extends the POP methodology to heterogeneous
accelerated systems. BasicAnalysis applies this model through post-mortem
analysis of Paraver traces, deriving the Host- and Device-side execution
information required to compute the corresponding metrics.

For compactness, the following notation is used for the Host and 
Device metrics:

* **Host_PE**: Host Parallel Efficiency
* **MPI_PE**: MPI Parallel Efficiency
* **Device_Offload**: Device Offload Efficiency
* **Host_GE**: Host Global Efficiency
* **Host_CompScale**: Host Computation Scalability
* **Device_GE**: Device Global Efficiency
* **Device_PE**: Device Parallel Efficiency
* **Device_LB**: Device Load Balance
* **Device_CommE**: Device Communication Efficiency
* **Device_OrchE**: Device Orchestration Efficiency
* **Device_CompScale**: Device Computation Scalability

Host Global Efficiency
----------------------

The Host Global Efficiency characterizes the efficiency of the CPU-side
execution. Performance losses at this level can arise from the parallel
execution and the interaction with the accelerator, but also from changes
in the efficiency of the computation performed on the Host as the execution
configuration changes.

These two aspects are characterized by Host Parallel Efficiency and Host
Computation Scalability, respectively. Host Global Efficiency is therefore
defined as:

.. math::

   Host\_GE = Host\_PE \times Host\_CompScale


Host Parallel Efficiency
^^^^^^^^^^^^^^^^^^^^^^^^

From the Host perspective, parallel-efficiency losses can originate from two
different components of the execution. The Host parallel runtime can introduce
the usual load-distribution and communication overheads, while interaction
with the accelerator can introduce offload overhead associated with launching
work, transferring data, or waiting for the device.

In the current MPI+GPU implementation, the Host-side parallel runtime is MPI.
Therefore, Host Parallel Efficiency is decomposed into an MPI contribution
and an accelerator-offload contribution:

.. math::

   Host\_PE = MPI\_PE \times Device\_Offload

**MPI Parallel Efficiency** characterizes the contribution associated with the
MPI parallelization. When evaluating this contribution, time spent outside MPI,
including Host activity associated with managing the accelerator, is considered
computation from the MPI perspective.

**Device Offload Efficiency** characterizes the remaining Host-side loss
associated with using the accelerator. This includes activity such as
launching accelerator work, transferring data, and waiting for accelerator
operations to complete.

Host Computation Scalability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Host Computation Scalability** characterizes how the useful computation
performed on the Host evolves when the execution configuration changes.
It applies the computation-scalability branch of the performance model to
Host-side useful computation.

As in the application-level model, Host Computation Scalability can be
further decomposed into:

* **Host IPC Scalability**, characterizing changes in the number of instructions
  completed per processor cycle;

* **Host Instruction Scalability**, characterizing changes in the amount of
  instructions required to perform the useful Host computation;

* **Host Frequency Scalability**, characterizing changes in processor frequency.

These factors are evaluated considering only the Host-side execution and 
therefore characterize the scalability of the CPU-side computation 
independently of the Device execution.

The Host computation-scaling branch is therefore decomposed into:

.. math::

   Host\_CompScale =
   Host\_IPCScale \times
   Host\_InstructionScale \times
   Host\_FrequencyScale

Together, the Host Parallel Efficiency and Host Computation Scalability
branches provide the complete decomposition of Host Global Efficiency. The
resulting Host metric hierarchy for the current MPI+GPU implementation is:

.. graphviz:: graphs/05_host_execution_domain.dot
   :align: center

Device Global Efficiency
------------------------

Device Global Efficiency characterizes the efficiency of the accelerator-side
execution. Performance losses at this level can arise from how effectively the
available Device resources execute the work supplied by the Host, but also
from changes in the efficiency of the computation performed on the Device as
the execution configuration changes.

These two aspects are characterized by Device Parallel Efficiency and Device
Computation Scalability, respectively. Device Global Efficiency is therefore
defined as:

.. math::

   Device\_GE =
   Device\_PE \times Device\_CompScale

Device Parallel Efficiency
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A device may fail to perform useful computation for several different
reasons. It may not have work available to execute, it may be involved in data
movement, or the useful work may be distributed unevenly across the available
devices. The Device hierarchy separates these effects into three performance
factors: Orchestration Efficiency, Communication Efficiency, and Load Balance.

**Device Load Balance** 

When several accelerators participate in the execution, useful work must also
be distributed evenly among them.

Device Load Balance characterizes differences in useful computation across
devices. A low value indicates that some devices perform less useful
computation than others and therefore contribute less effectively to the
parallel execution.

**Device Communication Efficiency** 
Even when work is available, device execution can be delayed by data movement.
Transfers may occur between Host and Device or between accelerators, and may
also involve communication mechanisms such as accelerator-aware MPI or
device-communication libraries.

Device Communication Efficiency characterizes the loss associated with
data movement that is not hidden by computation. Data transfers that overlap
with useful computation do not contribute to this loss.

**Device Orchestration Efficiency**

A device can remain idle because executable work is not available when it is
ready to execute. This may reflect inefficiencies in coordinating computation,
communication, and Host offload, including delays in supplying work or
dependencies between accelerator operations.

Device Orchestration Efficiency characterizes the loss associated with periods
in which the accelerator remains inactive because neither useful computation
nor data movement is being performed. A low value therefore indicates that the
accelerator is not being supplied with executable work continuously.

Together, these factors determine Device Parallel Efficiency:

.. math::

   Device\_PE =
   Device\_LB \times Device\_CommE \times Device\_OrchE


Device Computation Scalability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Device Computation Scalability** characterizes how the useful computation
performed on the Device evolves when the execution configuration changes.
It complements Device Parallel Efficiency by separating changes in the
computation itself from losses associated with workload distribution, data
movement, and the availability of work on the accelerator.

At present, BasicAnalysis provides Device Computation Scalability as the
parent metric of the computation-scaling branch. A decomposition into
lower-level Device computation-scaling factors is not currently defined in
BasicAnalysis and is therefore not included in the metric hierarchy.

With the Device Parallel Efficiency factors described above and Device
Computation Scalability completing the second branch, the Device Global
Efficiency hierarchy for the current MPI+GPU implementation can be
represented as:

.. graphviz:: graphs/05_device_execution_domain.dot
   :align: center


Independent Host and Device efficiencies
----------------------------------------

The Host and Device hierarchies describe different execution domains. They are
not successive levels of a single multiplicative hierarchy.

BasicAnalysis therefore computes two independent domain-level efficiencies:

* **Host Global Efficiency**, which characterizes CPU-side execution and the
  interaction with the accelerator;
* **Device Global Efficiency**, which characterizes execution on the
  accelerator itself.

A low Host Global Efficiency may indicate limitations in the CPU-side execution 
or offload path, while a low Device Global Efficiency may indicate insufficient 
work, data-movement overhead, imbalance, or poor computation scalability on the 
accelerator.

.. warning::

   Host Global Efficiency and Device Global Efficiency must not be multiplied
   to obtain application Global Efficiency.

The Execution Domains analysis should therefore be interpreted as a
localization view: it helps determine **where** accelerator-related
inefficiency manifests. The Parallel Runtime Model provides a different,
complementary perspective by attributing efficiency losses to the participating
parallel runtimes and their common performance factors.


I/O analysis
============

File I/O can represent an important component of application execution, but
its contribution is not currently part of the hierarchical efficiency model
used by BasicAnalysis. BasicAnalysis therefore provides **I/O Analysis** as a
complementary analytical view.

The analysis characterizes two aspects of the observed File I/O activity:

* the relative contribution of File I/O to the measured execution activity;
* the distribution of File I/O activity across the execution units involved.

BasicAnalysis distinguishes File I/O performed through **MPI-I/O** from
**POSIX and ANSI C File I/O** when the corresponding activity is available in
the trace. The resulting metrics allow the user to determine whether File I/O
represents a significant component of the execution and whether the observed
I/O activity is evenly distributed across the participating execution units.

The I/O metrics are interpreted as efficiency-oriented metrics, so higher
values represent more favorable behavior. However, they should not be
multiplied with Global Efficiency, Parallel Efficiency, or other factors of
the hierarchical performance model.

When several execution configurations are analyzed, the evolution of the I/O
metrics can also be compared across configurations to identify changes in the
relative contribution or distribution of File I/O activity as the application
scales.

The definitions, formulations, and availability conditions of the I/O metrics
are provided in :doc:`06_metrics`.


Scaling analysis
================

When several execution configurations are analyzed together, BasicAnalysis
examines how application performance and the efficiency factors identified by
the hierarchical model evolve as the amount of parallel resources changes.

The **Scaling Analysis** adds the configuration dimension to the performance
assessment. While the hierarchical analysis identifies the factors that
contribute to an efficiency loss for a given execution, Scaling Analysis
examines how those factors evolve across the analyzed configurations.

Scaling Analysis should not be confused with the **Computation Scalability**
metric introduced earlier in this chapter. Computation Scalability is one
factor of the efficiency hierarchy, characterizing how the computation itself
scales relative to a reference execution. Scaling Analysis is the broader
comparative analysis in which Computation Scalability, Parallel Efficiency,
and their contributing factors can all be examined across configurations.

The interpretation of the scaling behavior depends on the scaling model.
BasicAnalysis supports both **strong scaling**, where the problem size remains
constant while the computational resources increase, and **weak scaling**,
where the amount of work increases together with the computational resources.

Determining the scaling model
-----------------------------

When automatic scaling detection is enabled, BasicAnalysis determines whether
the analyzed executions exhibit behavior consistent with strong or weak
scaling from the execution measurements.

The first execution in the ordered trace list is used as the reference.
BasicAnalysis evaluates three indicators across the remaining configurations:

* the growth in useful instructions relative to the growth in the number of
  processes;

* the evolution of execution time relative to the reference;

* the evolution of average useful computation relative to the reference.

For each indicator, BasicAnalysis computes its average relative behavior
across the non-reference executions. An indicator is considered consistent
with weak scaling when its average ratio is greater than 0.9.

Weak scaling is selected when at least two of the three indicators exhibit
weak-scaling behavior. Otherwise, the executions are classified as strong
scaling.

This detection provides an execution-based estimate of the scaling model
rather than determining the application problem size directly. The scaling
model can therefore be selected explicitly when the intended scaling
experiment is known. If the manually selected model differs from the
automatically detected one, BasicAnalysis reports the discrepancy.

The detected scaling model, the model finally used for the analysis, and
whether the selection was automatic or manual are included in the scaling
information reported by BasicAnalysis.

Reference execution
-------------------

The reference execution used during scaling detection also provides the
baseline for evaluating relative scalability metrics, such as Computation
Scalability and its contributing factors.

By default, BasicAnalysis orders the traces according to their parallel
configuration and uses the first execution in this ordering as the reference.
Users can preserve the input ordering when a different reference execution is
required.

The choice of reference affects the numerical values of the relative
scalability metrics and their interpretation. The selected configuration
should therefore provide a meaningful baseline for evaluating how performance
evolves as the application scales.

Interpreting scaling trends
---------------------------

Scaling Analysis preserves the relationships defined by the metric hierarchy,
but examines them across execution configurations. The evolution of a parent
metric can therefore be interpreted together with the evolution of its
contributing factors.

For example, if Global Efficiency decreases as the application scales,
Parallel Efficiency and Computation Scalability can be compared across the
same configurations to determine which branch is responsible for the observed
degradation. If Parallel Efficiency deteriorates, its Load Balance and
Communication Efficiency trends can then be inspected. Similarly, a
degradation in Computation Scalability can be investigated through the
evolution of its IPC, Instruction, and Frequency Scalability factors.

This comparative perspective is important because the scaling behavior of a
metric is not determined only by its value at a single configuration. A metric
may remain relatively high while progressively degrading as resources
increase, revealing an emerging scalability limitation. Conversely, a metric
that is low but remains stable may represent an existing performance
limitation without being the factor responsible for the observed scaling
degradation.


Complementary analytical views
==============================

The BasicAnalysis analytical views address different performance questions and
provide complementary perspectives on the execution. They are not intended to
be interpreted as independent analyses, but as different levels of evidence
that can be combined according to the objective of the performance assessment.

A useful way to interpret them is:

**Hierarchical Efficiency Analysis**

   Which performance factor contributes to the observed efficiency loss?

**Parallel Runtime Model**

   When multiple parallel runtimes participate in the execution, which runtime
   contributes to that performance factor?

**Runtime-Specific Analysis**

   Which behavior within the identified runtime helps explain the observed
   inefficiency?

**Execution Domains**

   For accelerator applications, where does the inefficiency manifest: Host,
   offload path, or Device?

**I/O Analysis**

   How significant is File I/O activity, and how is that activity distributed
   across the execution units involved?

**Scaling Analysis**

   How do the performance factors and their contributions evolve as the
   execution configuration changes?

These perspectives can be followed progressively during a comprehensive
performance assessment or selected individually when investigating a specific
performance question. Their combination allows the analysis to move from identifying an efficiency
loss, to attributing it to a performance factor or parallel runtime, and, when
supported by the available metrics, to further characterizing where and how
the inefficiency manifests. Complementary views can additionally expose
execution aspects, such as File I/O activity, that are relevant to the
performance assessment without forming part of the hierarchical efficiency
model.

BasicAnalysis provides the efficiency metrics and interpretation guidance
needed to support this assessment. The metrics identify and characterize
performance losses, but they do not necessarily establish their underlying
cause. Detailed trace inspection or specialized performance-analysis tools may
therefore be required to validate the observations and determine why the
identified behavior occurs.