# Release Notes

## Unreleased

### New Features

- New File I/O performance model. The traced POSIX, ANSI C, and MPI-IO calls
  are classified into **Data Access** (calls that move or commit data: read
  and write calls of every API) and **File Management** (open, close, seek,
  and control calls), and **I/O Efficiency** is decomposed as
  `I/O Efficiency = Data Access Efficiency x File Management Efficiency`.
  **I/O Critical-Path Efficiency** = I/O Efficiency x **I/O Load Balance**
  estimates the I/O cost when the units wait for the slowest one after each
  kind of I/O call (the critical-path I/O time adds, for each kind of call,
  the time of the unit that spends the most time in it).
  I/O diagnostics explain where the I/O time is spent: average and maximum
  I/O time fraction, I/O participation, MPI-IO and POSIX/ANSI C
  contributions, Read/Write and Open/Close/Seek/Control contributions, load
  balance among the units that perform I/O (Data Access, Read, Write, File
  Management, and Open), and the time, number of operations, and mean
  duration of each group of calls. The factors are shown in the standard
  output, `other_metrics.csv`, and the I/O Analysis view of the report; the
  diagnostics in a table of the I/O Analysis view (without efficiency
  colors), the standard output, and the new `io_metrics.csv`. The time
  and number of MPI-IO calls are obtained with two new Paraver
  configurations (`mpiio-calls-time.cfg`, `mpiio-calls-count.cfg`).
- Request sizes of the read and write calls (POSIX, ANSI C, and MPI-IO;
  an MPI-IO split collective is one request): volume, mean
  request size, request-size coverage, and the request-size distribution in
  power-of-two intervals (share of the requests, of the time, and of the
  bytes), identical for every execution. They are shown in the standard
  output, the I/O diagnostics and new *Request sizes* histograms (share of
  the requests and of the time per interval, one bar per execution) of the
  I/O Analysis view, `io_metrics.csv`, and the new `io_request_sizes.csv`
  (by API). The
  requests are read from a temporary trace with only the I/O events,
  written by Paraver (`cfgs/io-requests-filter.xml`); the histograms
  `cfgs/io-*-size-pow2-*.cfg` show the same intervals in Paraver for the
  POSIX and ANSI C calls.
- Files accessed by the POSIX and ANSI C calls (MPI-IO records no file):
  files accessed, maximum processes per file, volume moved by the main
  process of each file (100% when each file is read and written by one
  process), and file-name coverage of the volume. Each call is attributed
  to its file through its descriptor and the file name of the open that
  returned it. They are shown in the I/O diagnostics, a new *Files* table
  of the I/O Analysis view (the ten files with the most I/O time of each
  execution), the standard output, `io_metrics.csv`, and the new
  `io_files.csv` (every file). The temporary trace of the requests also
  keeps the descriptor and file name events.
- Access pattern of the POSIX and ANSI C reads and writes to regular files:
  each request is first, consecutive, strided, forward, backward, or with
  an unknown offset with respect to the previous request of the same kind
  on the same descriptor, as shares of the requests, bytes, and time. The
  offsets are rebuilt from the opens, the seek offsets (recorded only by
  recent Extrae versions; taken as absolute), and the request sizes. New
  diagnostics: volume in consecutive requests, volume re-accessed, and
  offset coverage of the reads and writes, and redundant seeks (seeks to
  the current position). Shown in the *What requests are made?* and *Which
  calls take the time?* cards, the standard output, `io_metrics.csv`, and
  the new `io_access_pattern.csv`. The report (above the plots) and the
  standard output (after the tables) explain the meaning of each class.
  The pattern is also given per file: the share of the bytes read and
  written in consecutive requests in the files table of the report and of
  the standard output, and every class in `io_files.csv`. The temporary trace of the requests also
  keeps the descriptor type and seek offset events.
- The I/O Analysis view shows, after the efficiency table and its trends,
  four cards in reading order, each with a short note on how to read it and
  the diagnostics as plots (the values in a collapsible table): *Where is
  the I/O time spent?* (share of the I/O time of each call and API, time
  fractions, participation, and load balance), *Which calls take the
  time?* (time, operations, and mean duration of each call), *What requests
  are made?* (volume, mean request size, and the request-size histograms),
  and *Which files are accessed?* (file diagnostics and the I/O time of the
  files with the most I/O time).
- Classification thresholds can be set per metric in
  `metrics/definitions.yaml` (`thresholds: critical, attention`); the cell
  colors and the efficiency scale of the report follow the thresholds of
  each metric. The I/O efficiencies use the same thresholds as the other
  efficiencies (Critical below 60%, Good from 85%); stricter thresholds for
  I/O can be set this way.
- Add Device metrics for traces generated with nsys2prv from NVIDIA Nsight
  Systems reports (CUDA). These traces are detected automatically and
  analyzed with their own configurations, without changing the analysis of
  Extrae traces. Following the TALP device model, useful Device time is
  taken from the kernel events, and Device communication from the memory
  operations (copies and `memset`) and NCCL kernel events.
  nsys2prv does not record the node of each process: in traces merged from
  several nodes, every process is on the same node and the device numbers
  repeat. When the trace has more GPU metrics threads than GPUs identified by
  node and device number, each process is assumed to use its own GPUs, so
  GPUs of different nodes are not merged (a multi-node trace of 32 GPUs was
  analyzed as 4 GPUs before). Without GPU metrics threads this cannot be
  checked, and a warning is printed.
  The execution time is the end declared in the trace header: nsys2prv can
  write GPU metric samples after it, and Paraver then extends the trace to
  the last event, which made the period without application activity count
  as idle Device time and as useful Host time.
- Add Host metrics for nsys2prv traces: Device Offload efficiency, Host
  Parallel efficiency and Host Computation scalability. Since these traces
  have no state records, the useful host time is the elapsed time minus the
  time in CUDA calls. Only the processes with GPU streams are analyzed.
- Show the configuration of nsys2prv traces with the same format as
  MPI+GPU traces, `units (processes x streams per process) [devices]`
  (e.g. `5 (1x4) [1D]`), and report the devices, GPU streams, streams per
  process and host threads in the standard output.
- Compute the Parallel Runtime Model of nsys2prv traces over host threads
  and GPU streams, as for GPU applications without MPI in Extrae traces, and
  show their processes, streams per process and execution mapping in the
  Execution Overview of the interactive report.
- Add GPU hardware counter metrics for nsys2prv traces whose Nsight Systems
  report includes GPU metrics: SM Utilization and its factors SM Coverage
  and SM Issue Efficiency, and the indicators GPU Active, Achieved Occupancy
  (run average over all kernels), Tensor Core Activity, DRAM Read and Write
  Bandwidth and GPC Clock. They are averages over the whole execution
  weighted by the GPU activity, are complementary to the Host/Device model
  (not part of it), and are shown in the standard output, in
  `device_hwc_metrics.csv`, in the `efficiency_table_device_hwc_matplot`
  heatmap, in the `table_device_hwc_indicators_matplot` table of
  indicators, and in the new *GPU Hardware Counters* view of the interactive
  report, whose PNG export includes the indicators below the efficiency
  table. The metrics of Extrae traces do not change.
  `rawdata.csv` contains the integrals of the counters, including the DRAM
  read and write bandwidth without the GR Active weighting, which are
  proportional to the amount of data read and written (for comparing
  executions on the same GPU model).
- User-defined workload scaling: `--workload W1,W2,...` (workload sizes, for
  example batch sizes) or `--ratios-workload R1,R2,...` (workload ratios
  relative to the reference trace), one value per trace in command-line
  order. The scalability metrics, Speedup, and Scaling Efficiency use the
  weak-scaling formulas with the workload ratio in place of the ratio of
  processes, Host threads, or devices. This covers experiments in which the
  workload changes but the resources do not, such as several batch sizes on
  the same GPU. In the Host/Device model, the Host and the device can have
  their own workload (`--host-workload`, `--device-workload`, and their
  ratio forms), which default to that of the application; the Application
  Computation Scalability uses the ideal useful time of both domains. The
  workload and ratio of each trace are printed in the scaling model summary
  and shown in the Scaling section of the report; the automatic detection
  of weak or strong scaling is not used.
- Device Computation Scalability is split into factors whose product is the
  Device Computation Scalability, so the Host/Device model stays
  multiplicative. For *nsys2prv* traces with GPU metrics, the factors have
  the names of the CPU ones: **Device IPC Scalability** (mean SM Issue
  during the kernels), **Device Instruction Scalability** (instructions
  issued, SM Issue x GPC clock, with the new configuration
  `cfgs/nsys2prv/hwc_sm_issue_clock.cfg`, relative to those expected by the
  scaling model) and **Device Frequency Scalability**. For the other GPU
  traces, the work is counted as the GPU threads launched (blocks per grid x
  threads per block): **Device Work Scalability** (the threads launched
  relative to those expected by the scaling model) and **Device Throughput
  Scalability** (the threads completed per second of kernel time).
  The kernels of the GPU streams are read from the trace; a new table gives
  the share of each kernel in the change of the device time from the ideal
  of the scaling model (library kernels such as cuBLAS `nvjet_*` grouped by
  family), in the standard output, the Scaling view of the report (one
  execution at a time, with a selector), and the new `device_kernels.csv`. `rawdata.csv` adds the kernels executed and the
  GPU threads launched.

### Changes

- **I/O metrics replaced.** MPI I/O Efficiency, MPI I/O Load Balance, POSIX
  I/O Efficiency, and POSIX I/O Load Balance are no longer reported; they
  are replaced by Data Access and File Management Efficiency and the I/O
  diagnostics (the API-specific efficiencies by the I/O time fractions and
  the MPI-IO and POSIX/ANSI C contributions, the API-specific load balances
  by the per-operation load balances). In
  `other_metrics.csv`, the four rows are replaced by Data Access and File
  Management Efficiency, I/O Load Balance, and I/O Critical-Path
  Efficiency. The
  other metrics do not change; in the standard output, the first column of
  the general-indicators table is narrower because its longest label was
  removed.
- **I/O Efficiency in GPU applications.** The I/O efficiencies compare the
  I/O time with the useful time of the Host execution units, the units that
  perform File I/O. Previously, I/O Efficiency in GPU traces also counted
  the kernel time of the GPU streams as useful time and was overestimated
  (SPH-EXA, 64 ranks: 99.51% before, 94.58% now). The I/O Efficiency of
  traces without GPUs does not change. `rawdata.csv` has a new row, *Useful
  duration of the Host units, which perform File I/O (total)*.
- The linear request-size histograms (`hist-read-size-count.cfg`,
  `hist-write-size-count.cfg`) and the byte histograms (`hist-read-bytes.cfg`,
  `hist-write-bytes.cfg`) are no longer computed: they counted only the
  `read` and `write` calls, and no metric used them. They are replaced by
  the request-size distribution.
- The histograms of the opens per file (`hist-filename-burst.cfg`,
  `hist-filename-time.cfg`) are no longer computed: no metric used them,
  and the files accessed are now obtained from all the POSIX and ANSI C
  calls.
- The I/O diagnostics include every traced I/O call, including the ANSI C
  (`fread`, `fwrite`, `fopen`, `fclose`, `fseek`) and the vector and
  positional POSIX calls, which the previous per-operation raw data ignored.

### Improvements

- Label the columns of the static plots (efficiency tables, Speedup and
  Efficiency) with the trace identifier of the interactive report (`[T1]`,
  `[T2]`, ...), so that each trace can be referenced in papers and slides,
  also when several traces have the same configuration. The PNG export of
  the interactive report also keeps the trace identifiers. The CSV files
  and the standard output do not change.
- Static efficiency tables no longer show the metrics that have no value
  for any trace (e.g. IPC, Instruction and Frequency scalability when the
  traces have no hardware counters).
- Add Host-only and Device-only efficiency tables of the Host/Device model
  (`efficiency_table_talp_host_matplot` and
  `efficiency_table_talp_device_matplot`), in addition to the combined
  `efficiency_table_talp_matplot`, e.g. for presentations that focus on one
  execution domain.
- Interactive report: rename the *Execution Domains* view to *Host/Device
  Model*, show the Device metrics before the Host metrics, and
  collapse the *How to read this view* notes and the *How to use this
  report* note by default (click to expand). The hint on how to open the
  Metric Details is now part of the *How to read this view* notes instead of
  a line above each table.
- Identify useful Device computation by the *Running* state on the GPU
  streams, which corresponds to kernel execution, for CUDA and HIP. A single
  configuration now serves both runtimes and does not depend on the kernel
  event code used by the Extrae version. In cut traces, kernels already
  running at the beginning of the trace are now also counted.

### Fixes

- Fixed the Parallel Runtime Model of the interactive report for GPU
  applications without MPI: it showed an empty *MPI + X* model instead of
  the CUDA (or HIP) Parallel Runtime Model. Serialization and Transfer
  efficiency are now reported as not applicable (`N/A`) for these
  applications instead of 0.
- Fixed the reading of trace headers without CPU information, such as those
  written by nsys2prv (0 nodes), which stopped the analysis.
- Fixed the automatic scaling detection when some indicators are not
  available (e.g. useful time or instructions), which stopped the analysis
  of several traces. Unavailable indicators no longer vote.
- Fixed the hardware-counter metrics of GPU traces, which also counted the
  rows of the GPU streams. Extrae writes a few counter values on the stream
  rows when it closes them (the counters of the host thread), and the
  counter configurations counted them again for every kernel of the stream,
  so the useful cycles and instructions were overestimated by about 10^6.
  The useful instructions and cycles, the flushing, I/O, and MPI-IO cycles
  and instructions, and the average frequency now use the host threads
  only (rows labelled `THREAD`). Affected metrics, only in GPU traces:
  Average IPC, Average frequency, and IPC, Instruction, and Frequency
  Scalability (CloverLeaf CUDA, 4 GPUs: IPC 3.88 before, 3.17 now;
  frequency 2.40 GHz before, 2.73 GHz now). CPU traces do not change.
- Fixed two Paraver configurations of the OpenMP Runtime-Specific metrics
  whose analyzer ranges had been saved for a specific trace, so that values
  outside the range were silently ignored: the MPI time of MPI+OpenMP
  executions ignored `MPI_Send`, `MPI_Recv` and MPI calls with identifiers
  above 33, and the useful time outside OpenMP parallel regions ignored bursts
  longer than 0.13 s. Only the OpenMP Runtime-Specific metrics are affected
  (OpenMP Parallel, Serial, Load Balance and Scheduling Efficiency), mainly
  the OpenMP Serial Efficiency, which was overestimated (e.g. 98.61% instead
  of 89.58% in a Laplace MPI+OpenMP execution). The application-level
  metrics, the Parallel Runtime Model, and the Host/Device metrics do not
  change.
- Fixed the analyzer range of the bytes read and written by I/O calls, which
  ignored calls larger than 420,000 bytes or smaller than 8 bytes. These
  values are not used by the current metrics or report views.
- Fixed the detection of GPU memory transfers for traces generated with
  Extrae versions that record transfers with a different event code. Device
  memory transfers are now identified by the *Memory transfer* state on the
  GPU streams, for CUDA and HIP. In affected traces, Device Communication
  Efficiency was reported as 100% and Device Orchestration Efficiency was
  slightly underestimated.


## 2026.10.05

### New Features

- Add the comparison of executions that use different programming models,
  for example a new MPI+CUDA implementation with its MPI or MPI+OpenMP
  version, or MPI+CUDA with MPI+HIP. Each trace is described with the
  efficiency metrics of its own programming model. The comparison is shown
  in the terminal, written to `comparison_metrics.csv`, and presented in a
  new *Programming Model Comparison* tab of the interactive report, together
  with the complete report of each programming model. See *Comparing
  programming models* in the User Guide.
- Add Host/Device metrics and the Execution Domains view for GPU
  applications without MPI (CUDA and HIP with a serial host).
  `--pop_model_to_apply classic` keeps the previous metrics.

### Improvements

- The message shown when the interactive report cannot be generated now
  includes the cause, such as a missing Python package (`plotly` or `yaml`).

### Fixes

- Fixed the number of GPU streams reported as 0 for traces with legacy CUDA
  and HIP thread labels (`CUDA-D<n>.S<m>-<node>`, `HIP-D<n>.S<m>-<node>`).
  For HIP traces, the number of devices and the Device metrics were also
  affected.


## 2026.09.17

This is a corrective release addressing issues identified in the staged
analysis workflow introduced in version 2026.09.15.

### Fixes

- Fixed staged trace analysis to support multiple input traces while generating
  an independent raw-data JSON file for each trace.
- Fixed the merge of per-trace raw-data JSON files.
- Fixed the preservation of execution-mapping information when generating
  reports through the staged workflow.
- Corrected staged-workflow commands, options, and usage examples in the
  User Guide and README.


## 2026.09.15

> **Versioning:** Starting with this release, BasicAnalysis adopts
> Calendar Versioning (CalVer) using the `YYYY.MM.DD` format.

### New Features

- Add the interactive **Performance Report**, organizing BasicAnalysis results
  into complementary analysis views:
  - Execution Overview
  - Parallel Runtime Model
  - Runtime-Specific Analysis
  - Execution Domains
  - I/O Analysis
  - Scaling
  - Metric Details

- Add the **Parallel Runtime Model** to identify the contribution of the active
  parallel runtimes to Parallel Efficiency in hybrid applications.

- Add interactive **Runtime-Specific Analysis** for investigating the
  efficiency metrics associated with individual parallel runtimes.

- Add **MPI+HIP support**, including HIP runtime analysis and Host/Device
  execution-domain metrics.

- Add the **I/O Analysis** view to the interactive Performance Report,
  providing complementary analysis of MPI-I/O and POSIX/ANSI C File I/O
  activity.

- Add **Metric Details** with metric definitions, interpretation guidance,
  typical causes of performance losses, and recommended next analysis steps.

- Add interactive **Scaling** analysis to the Performance Report, including the
  detected scaling model, Speedup and Efficiency, and metric trends across
  execution configurations.

- Add **complementary split-view analysis**, allowing two report views to be
  inspected simultaneously.

- Add report export capabilities, including efficiency-table export as PNG,
  multi-table export as ZIP, and printable report generation for saving as PDF.

### Improvements

- Extend Host Computation Scalability with Host-side IPC, Instruction, and
  Frequency scalability diagnostics.

- Refine weak-scaling normalization of Host and Device Computation Scalability
  so that each execution domain is normalized using its corresponding resource
  population: Host execution units for the Host domain and physical devices
  for the Device domain.

- Extend File I/O analysis with the new API-specific **MPI I/O Efficiency**,
  **MPI I/O Load Balance**, **POSIX I/O Efficiency**, and
  **POSIX I/O Load Balance** metrics.

- Add a `requirements.txt` file with the recommended Python dependencies to
  simplify the setup of the BasicAnalysis environment.

### Bug Fixes

- Fix GPU device identification and stream-to-device mapping for accelerator
  traces using different GPU label formats in Paraver `.row` files.
  BasicAnalysis now supports both current and legacy GPU labels, ensuring that
  GPU stream activity is correctly associated with the corresponding physical
  devices.

- Fix **Average Frequency** computation to correctly derive the average
  processor frequency from the available hardware-counter measurements.

- Fix **Frequency Scalability** computation for MPI+GPU applications so that
  frequency changes are evaluated using the corresponding host-side frequency
  measurements across execution configurations.

### Documentation

- Add a comprehensive **BasicAnalysis User Guide** covering:
  - installation and prerequisites;
  - command-line options;
  - direct and staged analysis workflows;
  - the performance-analysis methodology;
  - application-level and runtime-specific metrics;
  - Host/Device execution-domain metrics;
  - File I/O metrics;
  - the interactive Performance Report;
  - generated output; and
  - current methodological and implementation limitations.

- Rewrite and update the README to describe the current BasicAnalysis
  methodology, supported programming models, analysis workflow, and
  Performance Report.

- Update installation instructions and Python dependency information.


## 0.5.1

### Bug Fixes

- Fix GPU device mapping to support the new UUID-based identification in .row files, ensuring compatibility with MPI+GPU traces generated by version 5.0.6 and later.



## 0.5.0

### New Features

- Add `--hyb-mpiomp` support to compute serialization and transfer efficiencies at the OpenMP level for hybrid MPI+OpenMP codes. This allows reporting Serialization and Transfer separately at MPI and OpenMP levels.
- Add `--ideal-omp` option to generate simulated MPI+OpenMP traces with ideal OpenMP behavior. In this mode, Dimemas ignores the duration of OpenMP runtime events, so any remaining duration is due to implicit synchronization. This option impacts the Serialization and Transfer metrics.
- Add support to split workflow execution, allowing users to analyze traces, merge intermediate results, and compute metrics in separate steps. This is useful when analyzing many traces and only rerunning failed traces before merging and recomputing the final metrics.

### Bug Fixes

- Fix device metrics computation when memory transfer events are not present in the analyzed traces.
- Fix frequency computation.



## 0.4.1

### Bug Fixes
- Fixed computation of offloading metric.



## 0.4.0

### New Features
- Added POP model selection: classic or TALP (TALP only for MPI+CUDA trace mode)
- Enabled Serialization and Transfer Efficiency for hybrid MPI+CUDA applications
- Added --skip-simulation to bypass Dimemas simulation
- Added advanced OpenMP/CUDA simulation flags (expert use only; not recommended for general users)

### Bug Fixes and Improvements
- Fixed trace mode detection.
- Improved handling of incomplete simulations.
- Improved error detection and diagnostics. Error logs are now preserved to simplify debugging and interaction with tool developers.


