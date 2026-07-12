# BasicAnalysis

The tool extracts raw performance data from Paraver traces, computes
hierarchical performance efficiency metrics, and generates CSV files,
plots, interactive HTML reports, and printable PDF performance reports.

It supports several parallel programming models such as:

* MPI
* OpenMP and other shared-memory programming models
* GPU programming models
* Hybrid models such as MPI+OpenMP and MPI+CUDA

The tool extracts raw performance data from Paraver traces, computes performance metrics, and generates tables, CSV files, plots and a performance report (HTML and PDF).

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


## Optional Dependencies

When a supported Chromium-compatible browser is available, BasicAnalysis
automatically generates a PDF performance report.

If no supported browser is found, PDF generation is skipped and a warning
is reported. The HTML reports and the rest of the BasicAnalysis analysis
are still generated normally.

The following browser executables are supported:

- `chromium`
- `chromium-browser`
- `google-chrome`
- `google-chrome-stable`

For example, on Ubuntu:

```bash
sudo apt install chromium
```

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
* efficiency and model-factor tables
* additional metrics tables
* speedup and scalability plots
* gnuplot scripts
* matplotlib figures
* an interactive HTML performance report
* a printable HTML performance report
* a PDF performance report

The main report files are:

```
basicanalysis_interactive_report.html
basicanalysis_printable_report.html
basicanalysis_performance_report.pdf
```

## Notes

* Dimemas is required to obtain the Transfer and Serialization metrics for MPI and hybrid analyses.
* The generated plots depend on the availability of the required Python modules.


## Performance analysis model

BasicAnalysis uses a hierarchical efficiency model to help identify the
main sources of performance degradation.

Parent metrics summarize overall performance efficiency, while child
metrics provide a more detailed characterization of the factors affecting
their parent metric.

When several traces are analyzed, BasicAnalysis also evaluates scaling
trends relative to the reference trace.

The generated reports preserve this metric hierarchy and provide automatic
performance interpretations to guide further detailed analysis.



## Step-by-step workflow

BasicAnalysis from version 0.5.0 can be executed in three independent stages:

- Trace analysis: analyze each trace and generate rawdata JSON files.
- Merge: merge several rawdata JSON files into a single merged file.
- Metrics computation: compute metrics, reports, and plots from the merged rawdata JSON.

This workflow is useful when processing many traces, especially if some analyses fail. In that case, users can rerun only the failed traces, then merge the results and compute the final metrics.

### 1. Trace analysis step
Command:

``` analyze_traces.py [options] [trace_list ...] ```

Analyze traces and generate per-trace rawdata JSON files.

This step parses each input trace, detects its programming model,
extracts raw performance data, and optionally runs Dimemas simulations
when required by the selected metric model.

The generated rawdata JSON files can later be merged and reused for
metrics computation without repeating the analysis step.

#### Help Contents

##### Positional arguments:

```
  trace_list
      List of traces to process. Wildcards are accepted and only valid
      traces are analyzed.
```

##### Main options:

``` 
  -h, --help
      Show this help message and exit.

  -v, --version
      Show program version and exit.

  -d, --debug
      Increase output verbosity to debug level.

  -m {simple,hybrid}, --metrics {simple,hybrid}
      Select the kind of efficiency metrics to prepare rawdata for
      (single parallelism or hybrid, default: hybrid).

  -s {weak,strong,auto}, --scaling {weak,strong,auto}
      Define whether the measurements correspond to weak scaling,
      strong scaling, or let the tool detect it automatically
      (default: auto).

  -tmd {pcf,prv}, --trace_mode_detection {pcf,prv}
      Select whether the trace mode is detected from the .pcf file
      or from the .prv file. For customized traces such as cut or
      filtered traces, use the .prv file (default: pcf).

  -ord {yes,not}, --order_traces {yes,not}
      Order the trace list based on the number of processes.
```

##### Simulation options (it is needed for communications sub-metrics):

```
  -skip-simul, --skip-simulation
      Skip running Dimemas simulation.

  -somp, --simulation_openmp
      Enable OpenMP event simulation.

  -scuda, --simulation_cuda
      Enable CUDA event simulation.

  --ideal-omp
      In simulation of MPI+OpenMP codes, ignore the duration of OpenMP
      runtime events. Any remaining duration is due to implicit
      synchronization.

  --hyb-mpiomp
      Compute Serialization and Transfer submetrics at the OpenMP level
      for MPI+OpenMP codes.
```

##### Resource options:

```
  --jobs JOBS
      Number of parallel trace analyses, or "auto" (default: 1).

  --mem-per-worker-gb MEM_PER_WORKER_GB
      Estimated memory required per worker in GiB; overrides the
      automatic heuristic.

  -ms MAX_TRACE_SIZE, --max_trace_size MAX_TRACE_SIZE
      Maximum allowed trace size in MiB (default: 1024 MiB).
```
##### Output:

- This step generates one rawdata JSON file per analyzed trace.
- These files can be merged later with merge_rawdata.py.

### 2. Merge step

Command:

```
merge_rawdata.py --output merged_rawdata.json rawdata_list.json
```
#### Help contents

Merge per-trace rawdata JSON files into a single merged rawdata JSON file.

This step combines the results produced by the analysis step into one
merged file that can later be used for metrics computation, reporting,
and plot generation.

This is useful when traces are analyzed in separate runs, or when only
failed traces need to be reanalyzed and merged again afterward.

##### Positional arguments:

```
  rawdata_files
      List of per-trace rawdata JSON files to merge.
```

##### Options:

```
  -h, --help
      Show this help message and exit.

  -v, --version
      Show program version and exit.

  -d, --debug
      Increase output verbosity to debug level.

  --output OUTPUT
      Output merged rawdata JSON file.
```

##### Notes:

The merged file preserves:

  - trace list
  - trace metadata
  - raw performance data
  - MPI process count information

The merged output can be passed directly to compute_metrics_from_merged.py.

### 3. Metrics computation step

Command

```
compute_metrics_from_merged.py --merged-input merged_rawdata.json [options]

```

#### Help Contents

Compute metrics, reports, and plots from merged rawdata JSON.

This step reads a merged rawdata JSON file produced by the merge step
and computes the final efficiency metrics without reanalyzing the
original traces.

This is useful when trace analysis has already been completed and only
the final metrics, tables, CSV files, and plots need to be generated.


##### Options:

```
  -h, --help
      Show this help message and exit.

  -v, --version
      Show program version and exit.

  -d, --debug
      Increase output verbosity to debug level.

  --merged-input MERGED_INPUT
      Merged rawdata JSON file.

  -m {simple,hybrid}, --metrics {simple,hybrid}
      Select the kind of efficiency metrics to compute
      (single parallelism or hybrid, default: hybrid).

  -s {weak,strong,auto}, --scaling {weak,strong,auto}
      Define whether the measurements correspond to weak scaling,
      strong scaling, or let the tool detect it automatically
      (default: auto).

  --limit LIMIT
      Limit number of cores for the plots
      (default: maximum process count in the merged input).

  -ord {yes,not}, --order_traces {yes,not}
      Order traces based on the number of processes.

  -pop-model {classic,talp}, --pop_model_to_apply {classic,talp}
      Select the metric model for MPI+GPU codes (default: talp).
      classic shows the multiplicative hybrid metrics proposed by
      BSC Tools in POP2, while talp shows the metrics proposed
      by the TALP team in POP3.

```

##### Notes:
  - This step does not analyze traces directly. It only consumes the merged rawdata JSON file.
  - Use the analysis step first if rawdata has not been generated yet.



### Short Workflow example

##### 1. Analyze traces

```
analyze_traces.py trace1.prv trace2.prv trace3.prv
```

##### 2. Merge rawdata

```
merge_rawdata.py --output merged_rawdata.json *.rawdata.json
```


##### 3. Compute metrics from merged data

```
compute_metrics_from_merged.py --merged-input merged_rawdata.json
```

