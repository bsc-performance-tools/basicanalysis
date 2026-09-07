.. _cha:methodology:

Performance Analysis Methodology
################################

BasicAnalysis organizes performance analysis as a hierarchy of complementary
views. The objective is not only to report individual efficiency values, but
also to help users understand which performance factors contribute to the
observed efficiency losses and which aspects of the execution should be
investigated next.

The analysis progresses from application-level behavior toward more specific
performance factors and execution components. Depending on the programming
model and the available trace information, BasicAnalysis combines the
following views:

* **Parallel Runtime Model**, which identifies the main efficiency factors and
  attributes parallel-efficiency losses to the active parallel runtimes.
* **Runtime-Specific Analysis**, which provides additional metrics describing
  the behavior of individual parallel runtimes.
* **Execution Domains**, which provides a complementary Host/Device analysis
  for accelerator applications.
* **Scaling**, which examines how performance and efficiency factors
  evolve across execution configurations.

These views answer different performance-analysis questions and should be
interpreted together rather than as interchangeable representations of the
execution.


Hierarchical efficiency analysis
================================

The main BasicAnalysis efficiency model follows a hierarchical decomposition
in which a parent efficiency is explained through more specific child factors.

At the application level, Global Efficiency is decomposed as:

.. math::

   Global\ Efficiency =
   Parallel\ Efficiency \times Computation\ Scalability

Parallel Efficiency is further decomposed as:

.. math::

   Parallel\ Efficiency =
   Load\ Balance \times Communication\ Efficiency

For MPI executions, Communication Efficiency can be decomposed into:

.. math::

   Communication\ Efficiency =
   Serialization\ Efficiency \times Transfer\ Efficiency

This hierarchy provides a systematic way to navigate the analysis. When a
parent metric shows an efficiency loss, its child metrics can be inspected to
identify which factor contributes most strongly to that loss.

For example, a low Parallel Efficiency should lead to the inspection of Load
Balance and Communication Efficiency. If Communication Efficiency is the
dominant source of loss, Serialization Efficiency and Transfer Efficiency can
then help distinguish between losses associated with process dependencies and
those associated with the communication transfer itself.

The complete definitions and formulations of these metrics are provided in
:doc:`metrics`.


Parallel Runtime Model
======================

Applications can combine multiple parallel programming models, such as
MPI+OpenMP or MPI+GPU. In these cases, observing only application-level
efficiency is insufficient to understand which parallel runtime contributes
to the performance loss.

The **Parallel Runtime Model** extends the hierarchical analysis by exposing
the contribution of the active parallel runtimes.

At the highest level, the model retains the application-level relationship
between Global Efficiency, Parallel Efficiency, and Computation Scalability.
Parallel Efficiency is then analyzed according to the parallel runtimes
participating in the execution.

For a hybrid execution, this provides a hierarchy conceptually represented as:

.. graphviz::
   :align: center

   digraph EfficiencyHierarchy {
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
           fillcolor="#E8F5E9"
       ];

         mpi_runtime [
            label="MPI contribution",
            fillcolor="#FFF3E0"
         ];

         inner_runtime [
            label="Inner-runtime contribution",
            fillcolor="#FFF3E0"
         ];

       comp [
           label="Computation Scalability",
           fillcolor="#E8F5E9"
       ];

       global -> parallel;
       global -> comp;

       parallel -> mpi_runtime;
       parallel -> inner_runtime;
   }


The exact runtime decomposition depends on the programming model. For example,
an MPI+OpenMP execution exposes MPI and OpenMP contributions, while an
MPI+CUDA or MPI+HIP execution exposes MPI and accelerator-runtime
contributions.


Measured and derived runtime metrics
------------------------------------

An important property of the hybrid Parallel Runtime Model is that not every
level of the hierarchy represents an independently measured efficiency.

Application-level and MPI-level quantities can be obtained from measured
execution data, while some inner runtime contributions are derived so that
the multiplicative relationship of the model is preserved.

Consequently, a derived inner metric may exceed 100%. Such a value should not
be interpreted as an independent physical efficiency greater than its ideal
value. Instead, it represents the relative contribution required by the
multiplicative decomposition of the hybrid model.

For this reason, metrics within the Parallel Runtime Model should be
interpreted according to their position and role in the hierarchy rather than
as a collection of independent efficiency measurements.


Runtime-Specific Analysis
=========================

The Parallel Runtime Model identifies which runtime contributes to a
parallel-efficiency loss, but additional information may be required to
understand the behavior of that runtime.

The **Runtime-Specific Analysis** provides this complementary information when
runtime-specific metrics are available.

For example, an OpenMP runtime can be examined using metrics describing
parallel-region efficiency and its contributing factors. MPI communication can
be examined through its communication-efficiency decomposition when the
required information is available.

Runtime-specific metrics therefore answer a different question from the
Parallel Runtime Model:

* the Parallel Runtime Model helps identify **which runtime contributes to the
  loss**;
* Runtime-Specific Analysis helps explain **which behavior within that runtime
  is associated with the loss**.

Not every programming model currently provides the same level of
runtime-specific decomposition. BasicAnalysis reports the runtime-specific
information supported by the analyzed execution and available trace data.


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

The Execution Domains view should therefore be used to determine **where**
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

Scaling plots preserve the hierarchy between performance metrics. When a
parent metric is shown, its direct child metrics are presented together when
applicable.

For example:

.. graphviz::
   :align: center

   digraph EfficiencyHierarchy {
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
           fillcolor="#E8F5E9"
       ];

       comp [
           label="Computation Scalability",
           fillcolor="#E8F5E9"
       ];

       global -> parallel;
       global -> comp;
   }




and:

.. graphviz::
   :align: center

   digraph EfficiencyHierarchy {
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

       parallel [
           label="Parallel Efficiency",
           fillcolor="#E8F5E9"
       ];

       loadbalance [
           label="Load Balance Effiency",
           fillcolor="#FFF3E0"
       ];

       communication [
           label="Communication Efficiency",
           fillcolor="#FFF3E0"
       ];

       parallel -> loadbalance;
       parallel -> communication;
   }



This parent-and-children representation helps determine which factor explains
the evolution observed in the parent metric.

A decreasing Global Efficiency, for example, should not be interpreted in
isolation. Its Parallel Efficiency and Computation Scalability trends should
be inspected to determine which component is responsible for the degradation.
The same reasoning can then be applied recursively to the corresponding child
metrics.


Complementary analytical views
==============================

The BasicAnalysis views are intentionally complementary and may use different
scopes and metric relationships.

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

The analysis should progressively follow the available evidence toward the
factors showing the most significant efficiency losses. BasicAnalysis provides
metric definitions and interpretation guidance to support this process, while
detailed trace analysis or specialized performance tools may be required to
establish the underlying cause.


From traces to efficiency metrics
=================================

BasicAnalysis derives its performance metrics from information extracted from
Paraver traces. Depending on the metric and programming model, the required
information can come directly from the measured execution or from an
idealized execution generated through simulation.

The internal analysis workflow that combines Paraver/paramedir data extraction and,
when required, Dimemas simulation can be depicted as:

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
are discussed in :doc:`metrics`.

When simulation is disabled with ``--skip-simulation``, metrics requiring
idealized execution information cannot be computed and are reported as
unavailable.