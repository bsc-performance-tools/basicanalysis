# BasicAnalysis

BasicAnalysis generates performance metrics based on the BSC Performance Model, originally developed at BSC in 2008 and later used and extended within the POP Centre of Excellence since 2015, from a set of Paraver traces.

It supports several parallel programming models such as:

* Pure MPI applications
* Pure OpenMP applications
* Hybrid applications such as MPI+OpenMP and MPI+CUDA

The tool extracts raw performance data from Paraver traces, computes performance metrics, and optionally generates tables, CSV files, and plots.

## Prerequisites

BasicAnalysis requires:

* Python 3
* Paraver / paramedir
* Dimemas

The following tools must be installed and available through the `PATH` environment variable:

* `paramedir` available from the Paraver distribution: [https://tools.bsc.es/paraver](https://tools.bsc.es/paraver)
* `Dimemas`: [https://tools.bsc.es/dimemas](https://tools.bsc.es/dimemas)

Set the environment variables as follows:

```bash
export PATH=<paraver-install-dir>/bin:$PATH
export PARAVER_HOME=<paraver-install-dir>

export PATH=<dimemas-install-dir>/bin:$PATH
export DIMEMAS_HOME=<dimemas-install-dir>
```

## Python dependencies

Some functionality depends on additional Python modules.

Core analysis requires only Python 3 and the standard library.

Optional plotting and advanced analysis require:

* NumPy
* pandas
* SciPy
* matplotlib >= 3.x
* seaborn

These modules can be installed with:

```bash
pip install numpy pandas scipy matplotlib seaborn
```

If these modules are not available, BasicAnalysis can still compute the metrics, but plotting functionality will be skipped.

For gnuplot-based output, gnuplot version 5.0 or higher is required.

## Installation

There is no installation step required.

Clone or copy the repository to any location and add the directory containing `modelfactors.py` to the `PATH` environment variable if desired.

Example:

```bash
export PATH=<basicanalysis-dir>:$PATH
```

## Usage

BasicAnalysis is executed through:

```bash
modelfactors.py [options] <list-of-traces>
```

The `<list-of-traces>` argument accepts:

* explicit trace filenames
* wildcard expressions
* multiple traces

Only valid Paraver traces are kept automatically.

Example:

```bash
modelfactors.py *.prv
```

or:

```bash
modelfactors.py trace_1.prv trace_2.prv trace_3.prv
```

## Main options

```text
-m, --metrics {simple,hybrid}
    Select the kind of efficiency metrics to compute.
    - simple: always use the simple metric workflow
    - hybrid: use the hybrid metric workflow only if at least one trace
      contains hybrid parallelism (For example: MPI+OpenMP, MPI+CUDA).
      If all traces are simple traces, BasicAnalysis automatically falls back
      to the simple metric workflow.
    Default: hybrid

-s, --scaling {weak,strong,auto}
    Define the scaling type.
    Default: auto

-ms, --max_trace_size
    Set the maximum trace size in MiB allowed.
    Default: 1024 MiB

--jobs
    Number of traces analyzed in parallel, or "auto".
    Default: 1

--mem-per-worker-gb
    Estimated memory required per worker in GiB.
    Overrides the automatic memory heuristic.

-skip-simul, --skip-simulation
    Skip running the Dimemas simulation.

-somp, --simulation_openmp
    Enable simulation of OpenMP events.

-scuda, --simulation_cuda
    Enable simulation of CUDA events.

-tmd, --trace_mode_detection {pcf,prv}
    Select whether the trace mode is detected from the .pcf or .prv file.
    For customized traces such as filtered or cut traces, use prv.
    Default: pcf

-ord, --order_traces {yes,not}
    Order the trace list by number of processes.
    Default: yes

-pop-model, --pop_model_to_apply {classic,talp}
    Select the POP metric model for MPI+GPU codes.
    - classic: multiplicative hybrid metrics proposed in POP2
    - talp: TALP metrics proposed in POP3
    Default: talp

-d, --debug
    Enable debug output.

-v, --version
    Print the BasicAnalysis version.
```

## Output

Depending on the trace type and execution mode, BasicAnalysis can generate:

* raw-data CSV files
* efficiency tables
* model-factor tables
* additional metrics tables
* speedup plots
* scalability plots
* gnuplot scripts
* matplotlib figures

## Notes

* Dimemas is required to obtain the Transfer and Serialization metrics for MPI and hybrid analyses.
* The generated plots depend on the availability of the required Python modules.






