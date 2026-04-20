# Release Notes


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


