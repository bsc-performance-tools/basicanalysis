# Release Notes

## Unreleased

### New Features

- Add Device metrics for traces generated with nsys2prv from NVIDIA Nsight
  Systems reports (CUDA). These traces are detected automatically and
  analyzed with their own configurations, without changing the analysis of
  Extrae traces. Following the TALP device model, useful Device time is
  taken from the kernel events, and Device communication from the memory
  operations (copies and `memset`) and NCCL kernel events.
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

### Improvements

- Interactive report: rename the *Execution Domains* view to *Host/Device
  Model (TALP)*, show the Device metrics before the Host metrics, and
  collapse the *How to read this view* notes by default (click to expand).
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


