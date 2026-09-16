# BasicAnalysis

BasicAnalysis is a tool that automates the application of the hierarchical
POP performance model to Paraver traces. The model characterizes
parallel executions through efficiency metrics based on key performance
factors, helping performance analysts identify which factors contribute to
performance and scalability losses.

The tool automatically extracts the performance data required to compute
the model's efficiency metrics and organizes the results into an interactive
Performance Report. The report provides complementary views of the efficiency
metrics and related performance information, helping analysts interpret the
metrics, relate the different factors represented by the model, and identify
possible next steps for further performance analysis.


## Key Features

* Automatic extraction of performance data and computation of efficiency
  metrics from Paraver traces.
* Hierarchical organization of efficiency metrics around key performance
  factors based on the POP performance model.
* Parallel Runtime Model for showing the contribution of different parallel
  runtimes to Parallel Efficiency.
* Runtime-specific efficiency metrics for MPI, OpenMP, and accelerator
  runtimes.
* Host and Device execution-domain efficiency metrics for accelerator
  applications.
* File I/O analysis with complementary efficiency and load-balance metrics for
  MPI-I/O and POSIX/ANSI C File I/O activity.
* Strong and weak scaling evaluation across multiple execution configurations.
* Metric Details with metric definitions, possible causes of performance
  losses, and guidance for further analysis.
* Interactive Performance Report with complementary analysis views and
  export capabilities.
* Support for both direct analysis of Paraver traces and a staged workflow
  for analyzing, merging, and reusing previously extracted performance data.

## Parallel Execution Environments

The efficiency metrics implemented by BasicAnalysis are based on general
performance factors of parallel executions and can be applied to different
parallel execution environments represented in Paraver traces.

Examples of programming models and combinations handled by BasicAnalysis
include:

* MPI
* OpenMP
* MPI+OpenMP
* MPI+CUDA
* MPI+HIP

Additional runtime-specific metrics and decompositions are available depending
on the parallel execution environment and the information contained in the
trace.

For MPI+HIP applications, simulation-derived MPI Serialization and Transfer
Efficiency are currently unavailable. See the BasicAnalysis User Guide for
the corresponding methodological limitations.


## Prerequisites

BasicAnalysis requires:

* Python 3
* Paraver / paramedir
* Dimemas, when simulation-derived communication metrics are required

`paramedir` is available as part of the Paraver distribution:

https://tools.bsc.es/paraver

Dimemas is available from:

https://tools.bsc.es/dimemas

The corresponding executables must be available through the `PATH`
environment variable. A typical configuration is:

```bash
export PATH=<paraver-install-dir>/bin:$PATH
export PARAVER_HOME=<paraver-install-dir>

export PATH=<dimemas-install-dir>/bin:$PATH
export DIMEMAS_HOME=<dimemas-install-dir>
```

Dimemas is used to compute simulation-derived communication metrics such as
Serialization Efficiency and Transfer Efficiency when supported by the
analyzed programming model. BasicAnalysis can also be executed without
Dimemas or with simulation explicitly disabled, in which case these metrics
are reported as unavailable.

## Installation

BasicAnalysis does not require a separate installation step. Clone or copy
the repository to the desired location and install the recommended Python
packages.

The recommended Python environment can be installed using the
`requirements.txt` file provided with BasicAnalysis:

```bash
pip install -r requirements.txt
```

The requirements file installs the Python packages used for data processing,
analysis, and visualization.

BasicAnalysis can still compute the performance metrics when optional
plotting dependencies are not available, but the corresponding plotting
functionality will be skipped.

The BasicAnalysis scripts can be executed directly from the repository.
Alternatively, the repository directory can be added to the `PATH`
environment variable:

```bash
export PATH=<basicanalysis-dir>:$PATH
```

Verify that BasicAnalysis is available with:

```bash
modelfactors.py --version
```

## Quick Start

BasicAnalysis is executed through `modelfactors.py`:

```bash
modelfactors.py [options] <list-of-traces>
```

The input can contain one or more Paraver traces (`.prv` or `.prv.gz`).
For example, to analyze all Paraver traces in the current directory:

```bash
modelfactors.py *.prv
```

Multiple traces can also be provided explicitly:

```bash
modelfactors.py trace_1.prv trace_2.prv trace_3.prv
```

When several traces are analyzed, BasicAnalysis evaluates how the performance
metrics evolve across the execution configurations and includes scaling
information in the generated report.

By default, BasicAnalysis automatically detects the programming model and
scaling type and computes the corresponding efficiency metrics.

After the analysis completes, open the generated interactive Performance
Report:

```text
basicanalysis_interactive_report.html
```

The report provides complementary views for identifying and interpreting
the factors contributing to performance and scalability losses.

To see all available command-line options, use:

```bash
modelfactors.py --help
```

For detailed information about the analysis options, performance analysis
methodology, metrics, report views, and output files, see the BasicAnalysis User Guide.


## Performance Report

BasicAnalysis generates an interactive Performance Report that organizes the
computed efficiency metrics and related performance information into
complementary views. Rather than presenting the results only as metric tables,
the report provides different perspectives that help users navigate the
efficiency hierarchy, interpret the observed losses, and identify aspects that
may require further investigation.

The report includes:

* **Execution Overview** – summarizes the analyzed trace configurations,
  including their programming models and parallel resources, together with
  general performance information such as execution time, speedup, efficiency,
  average IPC, and average frequency.
* **Parallel Runtime Model** – presents the main application-level efficiency
  factors and their hierarchical relationships and, for hybrid applications,
  shows the contribution of the active parallel runtimes to the observed
  Parallel Efficiency.
* **Runtime-Specific Analysis** – presents efficiency metrics that characterize
  the behavior of individual parallel runtimes.
* **Execution Domains** – presents Host and Device efficiency metrics for
  accelerator applications.
* **I/O Analysis** – characterizes the weight and distribution of File I/O
  activity through complementary MPI-I/O and POSIX/ANSI C File I/O metrics.
* **Scaling** – shows the detected scaling model and how performance indicators,
  efficiency metrics, runtime contributions, and execution-domain metrics
  evolve across execution configurations.
* **Metric Details** – provides definitions and interpretation guidance for
  individual metrics, including possible causes of low efficiency and possible
  next steps for further analysis.

The report also allows complementary views to be displayed together, helping
users relate different perspectives of the efficiency results, and supports
export of report content. Some views, such as Execution Domains and I/O
Analysis, provide complementary diagnostic perspectives and are not additional
multiplicative components of the application-level performance model.


## Staged Analysis Workflow

For analyses involving multiple traces, BasicAnalysis can also be executed
as a three-stage workflow:

1. Analyze the traces and generate reusable raw-data files:

   ```bash
   analyze_trace.py [options] <list-of-traces>
   ```

2. Merge the generated raw data:

   ```bash
   merge_trace_results.py --output merged_rawdata.json <rawdata-files>
   ```

3. Compute the metrics and generate the reports and plots:

   ```bash
   compute_metrics_from_merged.py --merged-input merged_rawdata.json
   ```

The staged workflow separates trace processing from metric computation.
Individual traces can be analyzed independently, allowing their processing
to be distributed across different jobs or compute nodes when required. This
is particularly useful for large or computationally expensive traces whose
processing or simulation may require significant memory or execution time.

The generated raw-data files can also be reused, allowing metrics and reports
to be regenerated without processing the original traces again.

See the BasicAnalysis User Guide for the complete staged workflow and
available options.


## Documentation

The BasicAnalysis User Guide provides detailed documentation about
installation, command-line options, analysis workflows, performance
methodology, metric definitions, the interactive Performance Report,
generated output, and current limitations.

See the BasicAnalysis User Guide in the `doc/` directory.

## Versioning

BasicAnalysis uses Calendar Versioning (CalVer) with the `YYYY.MM.DD` format.