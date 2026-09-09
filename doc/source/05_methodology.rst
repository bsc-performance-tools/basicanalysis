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

.. graphviz::
   :align: center

   digraph BaseEfficiencyHierarchy {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.35,
           ranksep=0.45
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#6B7C8F",
           penwidth=1.0
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

       global [
           label="Global Efficiency",
           fillcolor="#EAF2F8"
       ];

        parallel [
            label="Parallel Efficiency",
            fillcolor="#C8E6C9"
        ];

        comp [
            label="Computation Scalability",
            fillcolor="#BBDEFB"
        ];

        lb [
            label="Load Balance",
            fillcolor="#E8F5E9"
        ];

        comm [
            label="Communication Efficiency",
            fillcolor="#E8F5E9"
        ];

       global -> parallel;
       global -> comp;

       parallel -> lb;
       parallel -> comm;
   }

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

.. graphviz::
   :align: center

   digraph CommunicationHierarchy {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.35,
           ranksep=0.45
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#6B7C8F",
           penwidth=1.0
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

        comm [
            label="Communication Efficiency",
            fillcolor="#E8F5E9"
        ];

        serialization [
            label="Serialization Efficiency",
            fillcolor="#F1F8E9"
        ];

        transfer [
            label="Transfer Efficiency",
            fillcolor="#F1F8E9"
        ];

       comm -> serialization;
       comm -> transfer;
   }

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

.. graphviz::
   :align: center

   digraph CompleteEfficiencyHierarchy {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.35,
           ranksep=0.45
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#6B7C8F",
           penwidth=1.0
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

       global [
           label="Global Efficiency",
           fillcolor="#F4F6F7"
       ];

       parallel [
           label="Parallel Efficiency",
           fillcolor="#C8E6C9"
       ];

       loadbalance [
           label="Load Balance",
           fillcolor="#E8F5E9"
       ];

       communication [
           label="Communication Efficiency",
           fillcolor="#E8F5E9"
       ];

       serialization [
           label="Serialization Efficiency",
           fillcolor="#F1F8E9"
       ];

       transfer [
           label="Transfer Efficiency",
           fillcolor="#F1F8E9"
       ];

       computation [
           label="Computation Scalability",
           fillcolor="#BBDEFB"
       ];

       ipc [
           label="IPC Scalability",
           fillcolor="#E3F2FD"
       ];

       instructions [
           label="Instruction Scalability",
           fillcolor="#E3F2FD"
       ];

       frequency [
           label="Frequency Scalability",
           fillcolor="#E3F2FD"
       ];

       global -> parallel;
       global -> computation;

       parallel -> loadbalance;
       parallel -> communication;

       communication -> serialization;
       communication -> transfer;

       computation -> ipc;
       computation -> instructions;
       computation -> frequency;
   }


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

.. graphviz::
   :align: center

   digraph HybridParallelEfficiency {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.45,
           ranksep=0.45
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#6B7C8F",
           penwidth=1.0
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

       hybrid_pe [
           label="Hybrid Parallel Efficiency",
           fillcolor="#C8E6C9"
       ];

       hybrid_lb [
           label="Hybrid Load Balance",
           fillcolor="#E8F5E9"
       ];

       hybrid_ce [
           label="Hybrid Communication Efficiency",
           fillcolor="#E8F5E9"
       ];

       hybrid_pe -> hybrid_lb;
       hybrid_pe -> hybrid_ce;
   }

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

.. graphviz::
   :align: center

   digraph HybridOuterParallelEfficiency {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.45,
           ranksep=0.65
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#6B7C8F",
           penwidth=1.0
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

       outer_pe [
           label="Outer-runtime Parallel Efficiency",
           fillcolor="#C8E6C9"
       ];

       outer_lb [
           label="Outer-runtime Load Balance",
           fillcolor="#E8F5E9"
       ];

       outer_ce [
           label="Outer-runtime Communication Efficiency",
           fillcolor="#E8F5E9"
       ];

       outer_pe -> outer_lb;
       outer_pe -> outer_ce;
   }

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


.. graphviz::
   :align: center

   digraph HybridInnerParallelEfficiency {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.45,
           ranksep=0.65
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#6B7C8F",
           penwidth=1.0
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

       inner_pe [
           label="Inner-runtime Parallel Efficiency",
           fillcolor="#C8E6C9"
       ];

       inner_lb [
           label="Inner-runtime Load Balance",
           fillcolor="#E8F5E9"
       ];

       inner_ce [
           label="Inner-runtime Communication Efficiency",
           fillcolor="#E8F5E9"
       ];

       inner_pe -> inner_lb;
       inner_pe -> inner_ce;
   }


The resulting generic metric hierarchy for a hybrid parallel application 
can be represented as follows:


.. graphviz::
   :align: center

   digraph GenericParallelRuntimeModel {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.40,
           ranksep=0.50
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#2E7D32",
           penwidth=1.0
       ];

       edge [
           penwidth=1.0,
           arrowsize=0.7
       ];

       /*
        * Hybrid level
        */

       hybrid_pe [
           label="Hybrid Parallel\nEfficiency",
           fillcolor="#C8E6C9"
       ];

       hybrid_lb [
           label="Hybrid Load\nBalance",
           fillcolor="#E8F5E9"
       ];

       hybrid_ce [
           label="Hybrid Communication\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       /*
        * Outer-runtime level
        */

       outer_pe [
           label="Outer-runtime Parallel\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       outer_lb [
           label="Outer-runtime Load\nBalance",
           fillcolor="#F4F6F7"
       ];

       outer_ce [
           label="Outer-runtime Communication\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       /*
        * Inner-runtime level
        */

       inner_pe [
           label="Inner-runtime Parallel\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       inner_lb [
           label="Inner-runtime Load\nBalance",
           fillcolor="#F4F6F7"
       ];

       inner_ce [
           label="Inner-runtime Communication\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       /*
        * Hybrid performance-factor decomposition
        */

       hybrid_pe -> hybrid_lb [
           color="#4A90C2"
       ];

       hybrid_pe -> hybrid_ce [
           color="#4A90C2"
       ];

       /*
        * Runtime decomposition of Hybrid PE
        */

       hybrid_pe -> outer_pe [
           color="#2E7D32"
       ];

       hybrid_pe -> inner_pe [
           color="#2E7D32"
       ];

       /*
        * Outer-runtime performance factors
        */

       outer_pe -> outer_lb [
           color="#2E7D32"
       ];

       outer_pe -> outer_ce [
           color="#2E7D32"
       ];

       /*
        * Inner-runtime performance factors
        */

       inner_pe -> inner_lb [
           color="#2E7D32"
       ];

       inner_pe -> inner_ce [
           color="#2E7D32"
       ];

       /*
        * Runtime contributions to hybrid factors
        */

       hybrid_lb -> outer_lb [
           color="#4A90C2"
       ];

       hybrid_lb -> inner_lb [
           color="#4A90C2"
       ];

       hybrid_ce -> outer_ce [
           color="#4A90C2"
       ];

       hybrid_ce -> inner_ce [
           color="#4A90C2"
       ];

       /*
        * Layout constraints.
        *
        * Hybrid factors stay on the left.
        * Outer and inner runtime branches extend to the right.
        */

       { rank=same;
           hybrid_lb;
           hybrid_ce;
           outer_pe;
           inner_pe;
       }

       { rank=same;
           outer_lb;
           outer_ce;
           inner_lb;
           inner_ce;
       }

       /*
        * Invisible edges control left-to-right ordering.
        */

       hybrid_lb -> hybrid_ce [
           style=invis,
           weight=20
       ];

       hybrid_ce -> outer_pe [
           style=invis,
           weight=20
       ];

       outer_pe -> inner_pe [
           style=invis,
           weight=20
       ];

       outer_lb -> outer_ce [
           style=invis,
           weight=20
       ];

       outer_ce -> inner_lb [
           style=invis,
           weight=20
       ];

       inner_lb -> inner_ce [
           style=invis,
           weight=20
       ];
   }


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

.. graphviz::
   :align: center

   digraph MPIOMPParallelRuntimeModel {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.40,
           ranksep=0.50
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#2E7D32",
           penwidth=1.0
       ];

       edge [
           penwidth=1.0,
           arrowsize=0.7
       ];

       /*
        * Hybrid level
        */

       hybrid_pe [
           label="Hybrid Parallel\nEfficiency",
           fillcolor="#C8E6C9"
       ];

       hybrid_lb [
           label="Hybrid Load\nBalance",
           fillcolor="#E8F5E9"
       ];

       hybrid_ce [
           label="Hybrid Communication\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       /*
        * MPI level
        */

       mpi_pe [
           label="MPI Parallel\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       mpi_lb [
           label="MPI Load\nBalance",
           fillcolor="#F4F6F7"
       ];

       mpi_ce [
           label="MPI Communication\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       mpi_serial [
           label="MPI Serialization\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       mpi_transfer [
           label="MPI Transfer\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       /*
        * OpenMP level
        */

       omp_pe [
           label="OpenMP Parallel\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       omp_lb [
           label="OpenMP Load\nBalance",
           fillcolor="#F4F6F7"
       ];

       omp_ce [
           label="OpenMP Communication\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       /*
        * Hybrid performance-factor decomposition
        */

       hybrid_pe -> hybrid_lb [
           color="#4A90C2"
       ];

       hybrid_pe -> hybrid_ce [
           color="#4A90C2"
       ];

       /*
        * Runtime decomposition of Hybrid PE
        */

       hybrid_pe -> mpi_pe [
           color="#2E7D32"
       ];

       hybrid_pe -> omp_pe [
           color="#2E7D32"
       ];

       /*
        * MPI performance factors
        */

       mpi_pe -> mpi_lb [
           color="#2E7D32"
       ];

       mpi_pe -> mpi_ce [
           color="#2E7D32"
       ];

       /*
        * OpenMP performance factors
        */

       omp_pe -> omp_lb [
           color="#2E7D32"
       ];

       omp_pe -> omp_ce [
           color="#2E7D32"
       ];

       /*
        * Runtime contributions to Hybrid Load Balance
        */

       hybrid_lb -> mpi_lb [
           color="#4A90C2"
       ];

       hybrid_lb -> omp_lb [
           color="#4A90C2"
       ];

       /*
        * Runtime contributions to Hybrid Communication Efficiency
        */

       hybrid_ce -> mpi_ce [
           color="#4A90C2"
       ];

       hybrid_ce -> omp_ce [
           color="#4A90C2"
       ];

       /*
        * MPI Communication Efficiency decomposition
        */

       mpi_ce -> mpi_serial [
           color="#2E7D32"
       ];

       mpi_ce -> mpi_transfer [
           color="#2E7D32"
       ];

       /*
        * Layout constraints:
        * Hybrid factors on the left,
        * MPI and OpenMP runtime branches on the right.
        */

       { rank=same;
           hybrid_lb;
           hybrid_ce;
           mpi_pe;
           omp_pe;
       }

       { rank=same;
           mpi_lb;
           mpi_ce;
           omp_lb;
           omp_ce;
       }

       { rank=same;
           mpi_serial;
           mpi_transfer;
       }

       /*
        * Invisible edges control left-to-right ordering.
        */

       hybrid_lb -> hybrid_ce [
           style=invis,
           weight=20
       ];

       hybrid_ce -> mpi_pe [
           style=invis,
           weight=20
       ];

       mpi_pe -> omp_pe [
           style=invis,
           weight=20
       ];

       mpi_lb -> mpi_ce [
           style=invis,
           weight=20
       ];

       mpi_ce -> omp_lb [
           style=invis,
           weight=20
       ];

       omp_lb -> omp_ce [
           style=invis,
           weight=20
       ];

       mpi_serial -> mpi_transfer [
           style=invis,
           weight=20
       ];
   }

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


.. graphviz::
   :align: center

   digraph HybridCommunicationDecomposition {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.45,
           ranksep=0.50
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#2E7D32",
           penwidth=1.0
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

       hybrid_ce [
           label="Hybrid Communication\nEfficiency",
           fillcolor="#C8E6C9"
       ];

       hybrid_serial [
           label="Hybrid Serialization\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       hybrid_transfer [
           label="Hybrid Transfer\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       mpi_serial [
           label="MPI Serialization\nEfficiency",
           fillcolor="#F1F8E9"
       ];

       omp_serial [
           label="OpenMP Serialization\nEfficiency",
           fillcolor="#F1F8E9"
       ];

       mpi_transfer [
           label="MPI Transfer\nEfficiency",
           fillcolor="#F1F8E9"
       ];

       omp_transfer [
           label="OpenMP Transfer\nEfficiency",
           fillcolor="#F1F8E9"
       ];

       hybrid_ce -> hybrid_serial;
       hybrid_ce -> hybrid_transfer;

       hybrid_serial -> mpi_serial;
       hybrid_serial -> omp_serial;

       hybrid_transfer -> mpi_transfer;
       hybrid_transfer -> omp_transfer;

       { rank=same; hybrid_serial; hybrid_transfer; }
       { rank=same; mpi_serial; omp_serial; mpi_transfer; omp_transfer; }
   }


The OpenMP factors derived through this extension describe the contribution
of OpenMP to the communication-related factors observed in the hybrid
execution. They remain relative contributions within the Parallel Runtime
Model. The MPI+OpenMP metric hierarchy is therefore extended as follows:

.. graphviz::
   :align: center

   digraph MPIOMPParallelRuntimeModel {

       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.40,
           ranksep=0.50
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#2E7D32",
           penwidth=1.0
       ];

       edge [
           penwidth=1.0,
           arrowsize=0.7
       ];

       /*
        * Hybrid level
        */

       hybrid_pe [
           label="Hybrid Parallel\nEfficiency",
           fillcolor="#C8E6C9"
       ];

       hybrid_lb [
           label="Hybrid Load\nBalance",
           fillcolor="#E8F5E9"
       ];

       hybrid_ce [
           label="Hybrid Communication\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       hybrid_serial [
           label="Hybrid Serialization\nEfficiency",
           fillcolor="#D9EAF7"
       ];

       hybrid_transfer [
           label="Hybrid Transfer\nEfficiency",
           fillcolor="#D9EAF7"
       ];

       /*
        * MPI level
        */

       mpi_pe [
           label="MPI Parallel\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       mpi_lb [
           label="MPI Load\nBalance",
           fillcolor="#F4F6F7"
       ];

       mpi_ce [
           label="MPI Communication\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       mpi_serial [
           label="MPI Serialization\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       mpi_transfer [
           label="MPI Transfer\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       /*
        * OpenMP level
        */

       omp_pe [
           label="OpenMP Parallel\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       omp_lb [
           label="OpenMP Load\nBalance",
           fillcolor="#F4F6F7"
       ];

       omp_ce [
           label="OpenMP Communication\nEfficiency",
           fillcolor="#F4F6F7"
       ];

       omp_serial [
           label="OpenMP Serialization\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       omp_transfer [
           label="OpenMP Transfer\nEfficiency",
           fillcolor="#E8F5E9"
       ];

       /*
        * Hybrid performance-factor decomposition
        */

       hybrid_pe -> hybrid_lb [
           color="#4A90C2"
       ];

       hybrid_pe -> hybrid_ce [
           color="#4A90C2"
       ];

       /*
        * Runtime decomposition of Hybrid PE
        */

       hybrid_pe -> mpi_pe [
           color="#2E7D32"
       ];

       hybrid_pe -> omp_pe [
           color="#2E7D32"
       ];

       /*
        * MPI performance factors
        */

       mpi_pe -> mpi_lb [
           color="#2E7D32"
       ];

       mpi_pe -> mpi_ce [
           color="#2E7D32"
       ];

       /*
        * OpenMP performance factors
        */

       omp_pe -> omp_lb [
           color="#2E7D32"
       ];

       omp_pe -> omp_ce [
           color="#2E7D32"
       ];

       /*
        * Runtime contributions to Hybrid Load Balance
        */

       hybrid_lb -> mpi_lb [
           color="#4A90C2"
       ];

       hybrid_lb -> omp_lb [
           color="#4A90C2"
       ];

       /*
        * Hybrid Communication Efficiency decomposition
        */

       hybrid_ce -> hybrid_serial [
           color="#4A90C2"
       ];

       hybrid_ce -> hybrid_transfer [
           color="#4A90C2"
       ];

       /*
        * Runtime contributions to Hybrid Communication Efficiency
        */

       hybrid_ce -> mpi_ce [
           color="#4A90C2"
       ];

       hybrid_ce -> omp_ce [
           color="#4A90C2"
       ];

       /*
        * MPI Communication Efficiency decomposition
        */

       mpi_ce -> mpi_serial [
           color="#2E7D32"
       ];

       mpi_ce -> mpi_transfer [
           color="#2E7D32"
       ];

       /*
        * OpenMP Communication Efficiency decomposition
        */

       omp_ce -> omp_serial [
           color="#2E7D32"
       ];

       omp_ce -> omp_transfer [
           color="#2E7D32"
       ];

       /*
        * Runtime decomposition of Hybrid Serialization Efficiency
        */

       hybrid_serial -> mpi_serial [
           color="#4A90C2"
       ];

       hybrid_serial -> omp_serial [
           color="#4A90C2"
       ];

       /*
        * Runtime decomposition of Hybrid Transfer Efficiency
        */

       hybrid_transfer -> mpi_transfer [
           color="#4A90C2"
       ];

       hybrid_transfer -> omp_transfer [
           color="#4A90C2"
       ];

       /*
        * Layout constraints:
        * Hybrid factors on the left,
        * MPI and OpenMP runtime branches on the right.
        */

       {
           rank=same;
           hybrid_lb;
           hybrid_ce;
           mpi_pe;
           omp_pe;
       }

       {
           rank=same;
           hybrid_serial;
           hybrid_transfer;
           mpi_lb;
           mpi_ce;
           omp_lb;
           omp_ce;
       }

       {
           rank=same;
           mpi_serial;
           mpi_transfer;
           omp_serial;
           omp_transfer;
       }

       /*
        * Invisible edges control left-to-right ordering.
        */

       hybrid_lb -> hybrid_ce [
           style=invis,
           weight=20
       ];

       hybrid_ce -> mpi_pe [
           style=invis,
           weight=20
       ];

       mpi_pe -> omp_pe [
           style=invis,
           weight=20
       ];

       hybrid_serial -> hybrid_transfer [
           style=invis,
           weight=20
       ];

       hybrid_transfer -> mpi_lb [
           style=invis,
           weight=20
       ];

       mpi_lb -> mpi_ce [
           style=invis,
           weight=20
       ];

       mpi_ce -> omp_lb [
           style=invis,
           weight=20
       ];

       omp_lb -> omp_ce [
           style=invis,
           weight=20
       ];

       mpi_serial -> mpi_transfer [
           style=invis,
           weight=20
       ];

       mpi_transfer -> omp_serial [
           style=invis,
           weight=20
       ];

       omp_serial -> omp_transfer [
           style=invis,
           weight=20
       ];
   }

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

.. graphviz::
   :align: center

   digraph OpenMPEfficiencyHierarchy {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.45,
           ranksep=0.50
       ];

       node [
           shape=box,
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#EF6C00",
           penwidth=1.0
       ];

       edge [
           color="#B26A00",
           penwidth=1.0,
           arrowsize=0.7
       ];

       omp_pe [
           label="OMP Parallel\nEfficiency",
           fillcolor="#FFE0B2"
       ];

       omp_serial [
           label="OMP Serial\nEfficiency",
           fillcolor="#FFF3E0"
       ];

       omp_lb [
           label="OMP Load\nBalance",
           fillcolor="#FFF3E0"
       ];

       omp_sched [
           label="OMP Scheduling\nEfficiency",
           fillcolor="#FFF3E0"
       ];

       omp_pe -> omp_serial;
       omp_pe -> omp_lb;
       omp_pe -> omp_sched;

       { rank=same; omp_serial; omp_lb; omp_sched; }
   }



Execution Domains
=================

For accelerator applications, BasicAnalysis also provides an
**Execution Domains** view.

This view separates the execution into two complementary domains:

* **Host**, representing the CPU-side execution and the mechanisms responsible
  for supplying work to the accelerator;
* **Device**, representing the execution of work on the accelerator.

The purpose of this view is to identify where accelerator-related
inefficiencies manifest. For example, a performance loss may originate from
host-side orchestration or offload behavior, or it may manifest as poor
utilization or imbalance on the device.


Host execution domain
---------------------

The Host hierarchy characterizes the efficiency of CPU-side execution and the
interaction between the host and accelerator.

.. TODO:
   Add Graphviz Host hierarchy:

   Host Global Efficiency
   +-- Host Parallel Efficiency
   |   +-- MPI Parallel Efficiency
   |   +-- Device Offload Efficiency
   +-- Host Computation Scalability


Device execution domain
-----------------------

The Device hierarchy characterizes how efficiently work is executed on the
accelerator.

.. TODO:
   Add Graphviz Device hierarchy:

   Device Global Efficiency
   +-- Device Parallel Efficiency
   |   +-- Device Load Balance
   |   +-- Device Communication Efficiency
   |   +-- Device Orchestration Efficiency
   +-- Device Computation Scalability


Independent Host and Device efficiencies
----------------------------------------

Host and Device metrics do not form a multiplicative decomposition of a
single application Global Efficiency.

Instead, BasicAnalysis computes independent:

* **Host Global Efficiency**, and
* **Device Global Efficiency**.

These metrics characterize different execution domains and must be interpreted
as complementary evidence.

In particular:

.. warning::

   Host Global Efficiency and Device Global Efficiency must not be multiplied
   to obtain application Global Efficiency.

The Execution Domains view can therefore be used to determine **where**
accelerator-related performance losses manifest, while the Parallel Runtime
Model describes how those losses contribute to the application's hierarchical
efficiency model.


Scaling analysis
================

When several execution configurations are analyzed together, BasicAnalysis
examines how performance and efficiency factors evolve as the amount of
parallel resources changes.

The **Scaling Analysis** complements the hierarchical analysis by adding the
configuration dimension. Rather than asking only which metric is low, it asks
how that metric changes across the analyzed executions.

BasicAnalysis supports strong- and weak-scaling analyses. The scaling model
can be selected explicitly or automatically detected from the execution data.
The detected model, the model used by the analysis, and whether the selection
was automatic or manual are reported with the scaling results.


Reference execution
-------------------

Relative scalability metrics are evaluated with respect to a reference
execution. The trace ordering therefore affects the interpretation of the
scaling analysis.

By default, BasicAnalysis orders the traces according to their parallel
configuration before computing the comparative metrics. Users can preserve the
input ordering when a different reference ordering is required.

The selected reference configuration should represent a meaningful baseline
for interpreting the evolution of performance across the analyzed executions.


Interpreting scaling trends
---------------------------

Scaling analysis preserves the relationships defined by the metric hierarchy.
The evolution of a parent metric can therefore be interpreted together with
the evolution of its child factors.

For example, when Global Efficiency decreases across configurations, its
Parallel Efficiency and Computation Scalability trends can be inspected to
determine which component contributes to the degradation. The same reasoning
can then be applied recursively to the corresponding child metrics.

.. TODO:
   Decide whether one compact parent/children Graphviz example adds value
   here. Avoid repeating the complete hierarchy already introduced earlier
   in this chapter.


Complementary analytical views
==============================

The BasicAnalysis analytical views address different performance questions and
provide complementary perspectives on the execution. The views required for a
particular assessment depend on the analysis objective.

A useful way to interpret them is:

**Parallel Runtime Model**
   Which performance factor or parallel runtime contributes to the efficiency
   loss?

**Runtime-Specific Analysis**
   Which behavior within that runtime helps explain the observed inefficiency?

**Execution Domains**
   Where does the accelerator-related inefficiency manifest: Host, offload
   path, or Device?

**Scaling Analysis**
   How does the behavior evolve as the execution configuration changes?

A comprehensive performance assessment may combine several of these
perspectives, while a targeted investigation may focus on the view relevant to
the performance aspect under study.

BasicAnalysis provides metric definitions and interpretation guidance to
support this process. Detailed trace analysis or specialized performance tools
may still be required to establish the underlying cause of an observed
efficiency loss.


From traces to efficiency metrics
=================================

BasicAnalysis derives its performance metrics from information extracted from
Paraver traces. Depending on the metric and programming model, the required
information can come directly from the measured execution or from an
idealized execution generated through simulation.

The internal analysis workflow combines Paraver/paramedir data extraction and,
when required, Dimemas simulation:


.. graphviz::
   :align: center

   digraph BasicAnalysisMetricWorkflow {
       rankdir=TB;

       graph [
           bgcolor="transparent",
           nodesep=0.65,
           ranksep=0.26,
           splines=ortho
       ];

       node [
           fontname="Helvetica",
           fontsize=10,
           style="filled",
           color="#6B7C8F",
           penwidth=1.0,
           margin="0.10,0.06"
       ];

       edge [
           color="#526477",
           penwidth=1.0,
           arrowsize=0.7
       ];

       traces [
           label="Paraver traces",
           shape=folder,
           fillcolor="#EAF2F8"
       ];

       analysis_cfg [
           label="Analysis\nconfiguration files",
           shape=folder,
           fillcolor="#EAF2F8"
       ];

       generate_ideal_cfg [
           label="Generate ideal\nconfiguration",
           shape=box,
           fillcolor="#E8F5E9"
       ];

       ideal_cfg [
           label="Ideal simulation\nconfiguration",
           shape=note,
           fillcolor="#F4F6F7"
       ];

       paramedir_measured [
           label="paramedir",
           shape=box,
           fillcolor="#E8F5E9"
       ];

       measured [
           label="Measured raw data",
           shape=note,
           fillcolor="#F4F6F7"
       ];

       prv2dim [
           label="prv2dim",
           shape=box,
           fillcolor="#F3E5F5"
       ];

       dimemas [
           label="Dimemas",
           shape=box,
           fillcolor="#F3E5F5"
       ];

       simulated [
           label="Simulated traces",
           shape=folder,
           fillcolor="#F3E5F5"
       ];

       paramedir_ideal [
           label="paramedir",
           shape=box,
           fillcolor="#E8F5E9"
       ];

       ideal [
           label="Ideal raw data",
           shape=note,
           fillcolor="#F3E5F5"
       ];

       compute [
           label="Compute metrics",
           shape=box,
           fillcolor="#E8F5E9"
       ];

       metrics [
           label="Efficiency metrics",
           shape=folder,
           fillcolor="#FFF3E0"
       ];

       /*
        * Main top-level elements
        */
       {
           rank=same;
           analysis_cfg;
           traces;
           generate_ideal_cfg;
       }

       /*
        * Measured-data path
        */
       traces -> paramedir_measured;
       analysis_cfg -> paramedir_measured;

       paramedir_measured -> measured;

       /*
        * Simulation path
        */
       traces -> prv2dim [
           label="when simulation\nis required",
           fontsize=9
       ];

      traces -> generate_ideal_cfg [
         label="trace information",
         fontsize=9,
         constraint=false
      ];

       generate_ideal_cfg -> ideal_cfg;

       prv2dim -> dimemas;
       ideal_cfg -> dimemas;

       dimemas -> simulated;

       simulated -> paramedir_ideal;

       /*
        * This configuration-file dependency should not
        * determine the vertical position of paramedir.
        */
       analysis_cfg -> paramedir_ideal [
           constraint=false
       ];

       paramedir_ideal -> ideal;

       /*
        * Metric computation
        */
       measured -> compute;
       ideal -> compute;

       compute -> metrics;

       /*
        * Keep the first processing level aligned.
        */
       {
           rank=same;
           paramedir_measured;
           prv2dim;
           ideal_cfg;
       }
   }


Measured execution
------------------

The original Paraver trace represents the measured application execution.
BasicAnalysis uses ``paramedir`` together with a set of Paraver configuration
files to extract the raw information required by the different metric models.

The extracted information depends on the programming model and may include
execution times, useful computation, communication behavior, runtime activity,
and accelerator activity.


Idealized execution
-------------------

Some communication-efficiency decompositions require a comparison with an
idealized execution.

When these metrics are required, BasicAnalysis converts the relevant trace
information for Dimemas and simulates an idealized execution. ``paramedir`` is
then used again to extract the corresponding simulated information.

Measured and simulated data are subsequently combined to compute the
efficiency factors that depend on this comparison.


The Dimemas ideal configuration
-------------------------------

The Dimemas simulation used by BasicAnalysis is controlled by an ideal
configuration that represents the assumptions of the idealized communication
model.

The purpose of this configuration is not to reproduce the measured machine
exactly, but to provide the reference execution required by the corresponding
efficiency decomposition.

The exact assumptions represented by the BasicAnalysis ideal configuration
and their relationship with Serialization Efficiency and Transfer Efficiency
are discussed in :doc:`06_metrics`.

When simulation is disabled with ``--skip-simulation``, metrics requiring
idealized execution information cannot be computed and are reported as
unavailable.