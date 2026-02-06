# Release Notes

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


