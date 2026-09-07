Limitations
===========

Simulation-derived Metrics
--------------------------

Serialization Efficiency and Transfer Efficiency rely on an ideal execution
simulated with *Dimemas*. These metrics are therefore only available for
programming models and runtime events that can be represented by the current
*Dimemas* simulation model.

**BasicAnalysis** currently uses *Dimemas* simulation for MPI, MPI+OpenMP, and
MPI+CUDA applications. Serialization and Transfer Efficiency are not provided
for MPI+HIP applications because HIP events are not currently simulated by
*Dimemas*.

These metrics are also unavailable when *Dimemas* is not installed or when
simulation is explicitly disabled with the ``--skip-simulation`` option.


Number of Parallel Runtimes
---------------------------

The Parallel Runtime Model has been validated for applications with up to two
parallel runtime levels, such as MPI+OpenMP and MPI+GPU.

Applications containing more than two parallel runtimes may be detected in the
trace, but their decomposition into runtime-specific efficiency factors has not
been validated. In such cases, **BasicAnalysis** does not provide an independent
performance decomposition for every runtime level.


Hierarchical Execution Model
----------------------------

The Parallel Runtime Model assumes a hierarchical organization of the parallel
runtimes. For hybrid applications, MPI is considered the outer parallel level
and the second runtime, such as OpenMP or the accelerator runtime, the inner
level.

The model therefore assumes that execution attributed to the inner parallel
runtime does not overlap with MPI activity in a way that violates this
hierarchical decomposition. For example, in an MPI+OpenMP application, when
the master thread is executing MPI calls, the worker threads are assumed not to
be performing useful computation concurrently.
