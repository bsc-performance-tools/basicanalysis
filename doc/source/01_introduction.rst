.. _cha:introduction:

Introduction
############

**BasicAnalysis** automates the extraction of POP performance metrics from 
Paraver traces. POP metrics help diagnose how efficiently a parallel application 
is running with respect to basic performance factors such as load balance and
communication, as well as identify which factors may limit application scalability.

The tool automatically extracts from the traces the performance data required 
to compute the efficiency metrics and organizes the results into complementary 
views. These views expose the relationships between the metrics and provide
different perspectives on the performance factors represented by the model.

The main analytical views provided by BasicAnalysis are:

* **Execution Overview**, which summarizes the analyzed traces, execution
  configurations, parallel resources, and general performance characteristics.

* **Parallel Runtime Model**, which presents the main application-level
  efficiency factors and their hierarchical relationships and, for hybrid
  applications, shows the contribution of the active parallel runtimes to
  Parallel Efficiency.

* **Runtime-Specific Analysis**, which provides additional metrics for the
  active parallel runtimes when runtime-specific information is available.

* **Execution Domains**, which provides complementary Host and Device views for
  accelerator applications and helps identify where accelerator-related
  inefficiencies manifest.

* **Scaling**, which shows how efficiency metrics and other performance
  indicators evolve across the analyzed execution configurations.

The generated interactive and printable reports preserve the relationships
between the efficiency metrics and provide metric definitions, interpretation
guidance, possible causes of efficiency losses, and possible next steps for
further performance analysis.


Parallel execution environments
===============================

The efficiency metrics implemented by BasicAnalysis are based on general
performance factors of parallel executions and are therefore not restricted
to a specific parallel programming model. Since most of the metrics are
derived from useful computation and execution time, BasicAnalysis can be
applied to different parallel execution environments represented in Paraver
traces.

Examples of parallel programming models and combinations currently handled
by BasicAnalysis include:

* MPI
* OpenMP
* MPI+OpenMP
* MPI+CUDA
* MPI+HIP

Depending on the parallel execution environment, BasicAnalysis may provide
additional runtime-specific metrics and decompositions. The exact set of
metrics available also depends on the information contained in the trace and
the selected analysis model.


Analysis workflow
=================

BasicAnalysis can be executed directly for a set of Paraver traces or through
a staged workflow in which trace analysis, raw-data merging, and metric
computation are performed independently.

The standard execution workflow is introduced in :doc:`02_getting_started`, while
the staged workflow is described in detail in :doc:`04_staged_workflow`.