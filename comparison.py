#!/usr/bin/env python3

"""Comparison of traces that use different programming models.

When the analyzed traces do not share the same programming model
(e.g. MPI+CUDA vs MPI, or MPI+CUDA vs MPI+HIP), BasicAnalysis runs in
"comparison mode":

    - Each trace keeps the efficiency metrics of its own programming model.
    - Metrics that do not apply to a programming model are left empty.
    - Metrics computed against a reference trace (scalability, global
      efficiency, scaling detection) are not computed, because the
      executions use different kinds of resources.
    - Execution time and Speedup (runtime ratio against the first trace)
      remain available.
"""

from __future__ import print_function, division

import sys

from scaling import ScalingInfo


GPU_RUNTIMES = ("CUDA", "HIP")

# Cell content for metrics that do not apply to a programming model.
NOT_APPLICABLE = ''

# Metrics computed against the reference trace. They are not meaningful
# across programming models and are therefore not computed in
# comparison mode.
REFERENCE_METRIC_KEYS = {
    'mod_factors': (
        'global_eff',
        'comp_scale',
        'ipc_scale',
        'inst_scale',
        'freq_scale',
    ),
    'mod_factors_scale_plus_io': (
        'comp_scale',
        'ipc_scale',
        'inst_scale',
        'freq_scale',
    ),
    'host_factors': (
        'host_global_eff',
        'host_comp_scale',
        'host_ipc_scale',
        'host_inst_scale',
        'host_freq_scale',
    ),
    'device_factors': (
        'dev_global_eff',
        'dev_comp_scale',
    ),
    'other_metrics': (
        'efficiency',
    ),
}


def get_programming_model(mode):
    """Return the programming model of a trace mode.

    Examples:
        Detailed+MPI+CUDA -> MPI+CUDA
        Burst+MPI         -> MPI
        Sampling          -> Sampling
    """
    mode = str(mode)

    for prefix in ("Detailed+", "Burst+"):
        if mode.startswith(prefix):
            return mode[len(prefix):]

    return mode


def is_gpu_model(mode):
    """Return True for MPI+GPU trace modes (MPI+CUDA, MPI+HIP)."""
    return get_programming_model(mode) in (
        "MPI+" + runtime for runtime in GPU_RUNTIMES
    )


def get_second_level_runtime(mode):
    """Return the CPU runtime combined with MPI, or None.

    Examples:
        Detailed+MPI+OpenMP -> OpenMP
        Detailed+MPI        -> None
        Detailed+MPI+CUDA   -> None (GPU runtime)
    """
    model = get_programming_model(mode)

    if not model.startswith("MPI+") or is_gpu_model(mode):
        return None

    return model[len("MPI+"):]


def get_programming_models(trace_list, trace_mode):
    """Return the programming models of the traces, in trace order."""
    models = []

    for trace in trace_list:
        model = get_programming_model(trace_mode[trace])
        if model not in models:
            models.append(model)

    return models


def is_comparison_mode(trace_list, trace_mode):
    """Return True when the traces use different programming models."""
    return (
        len(trace_list) > 1
        and len(get_programming_models(trace_list, trace_mode)) > 1
    )


def _is_supported_mode(mode):
    """Comparison mode supports Detailed traces of MPI-based models."""
    mode = str(mode)
    return mode == "Detailed+MPI" or mode.startswith("Detailed+MPI+")


def check_comparison_support(trace_list, trace_mode):
    """Stop the analysis when a comparison includes unsupported traces.

    Comparison mode supports Detailed traces of MPI-based programming
    models. Burst traces, and traces without MPI, cannot be compared
    with other programming models.
    """
    if not is_comparison_mode(trace_list, trace_mode):
        return

    unsupported = [
        trace
        for trace in trace_list
        if not _is_supported_mode(trace_mode[trace])
    ]

    if not unsupported:
        return

    print("==ERROR== The traces use different programming models, but "
          "some of them cannot be compared.")
    print("          Comparison of programming models supports Detailed "
          "traces of MPI-based models")
    print("          (MPI, MPI+OpenMP, MPI+CUDA, MPI+HIP, ...).")
    print("")
    print("          Unsupported traces:")
    for trace in unsupported:
        print("            {} ({})".format(trace, trace_mode[trace]))
    print("")
    print("          Please analyze these traces separately.")
    sys.exit(1)


def get_comparison_scaling_info():
    """Return the scaling information used in comparison mode.

    No scaling analysis is performed across programming models. The
    selected value remains "strong" internally so that Speedup is the
    plain runtime ratio against the first trace.
    """
    return ScalingInfo(
        has_scaling_analysis=False,
        detected=None,
        selected="strong",
        selection_mode="implicit",
        overridden=False,
        status_message="Comparison of different programming models",
    )


def clear_reference_metrics(trace_list, factor_groups):
    """Mark reference-based metrics as not applicable ('N/A').

    factor_groups maps a group name of REFERENCE_METRIC_KEYS to the
    corresponding factor dictionary ([metric key][trace]).
    """
    for group, keys in REFERENCE_METRIC_KEYS.items():
        factors = factor_groups.get(group)
        if factors is None:
            continue

        for key in keys:
            if key not in factors:
                continue
            for trace in trace_list:
                factors[key][trace] = 'N/A'


def print_comparison_info(trace_list, trace_mode):
    """Print the comparison-mode notice."""
    models = get_programming_models(trace_list, trace_mode)

    print("Comparison of programming models:")
    print("  Programming models : {}".format(", ".join(models)))
    print("  Scalability metrics are not computed across programming models.")
    print("  Speedup is relative to the first trace: {}".format(trace_list[0]))
    print("")


class ComparisonCell(object):
    """One cell of the comparison table.

    value       metric value of the trace
    metric_key  metric of the trace's programming model shown in the cell;
                used to resolve its definition (Metric Details)
    runtime     runtime used to resolve runtime-specific definitions
                (e.g. OpenMP for omp_parallel_eff), or None
    """

    __slots__ = ('value', 'metric_key', 'runtime')

    def __init__(self, value, metric_key, runtime=None):
        self.value = value
        self.metric_key = metric_key
        self.runtime = runtime


def _trace_kind(mode):
    """Classify a trace mode for the comparison table."""
    if is_gpu_model(mode):
        return 'gpu'
    if get_second_level_runtime(mode) is not None:
        return 'mpi_x'
    return 'mpi'


def build_comparison_cells(trace_list, trace_mode, mod_factors,
                           hybrid_factors, host_factors):
    """Build the application rows of the comparison table.

    Each trace contributes the metrics of its own programming model:

        MPI         -> classic MPI metrics (mod_factors)
        MPI+<CPU>   -> MPI and second-level runtime metrics (hybrid_factors)
        MPI+GPU     -> Host metrics (host_factors)

    Device metrics are built by build_comparison_device_cells().

    Rows are included when they apply to at least one trace. Cells of
    traces where the metric does not apply are None.

    Returns:
        list of (label, {trace: ComparisonCell or None})
    """
    has_gpu = any(is_gpu_model(trace_mode[trace]) for trace in trace_list)

    second_level_runtimes = []
    for trace in trace_list:
        runtime = get_second_level_runtime(trace_mode[trace])
        if runtime is not None and runtime not in second_level_runtimes:
            second_level_runtimes.append(runtime)

    def row(label, sources):
        """sources maps a trace kind to (factors, key[, knowledge key])."""
        cells = {}
        for trace in trace_list:
            source = sources.get(_trace_kind(trace_mode[trace]))
            if source is None:
                cells[trace] = None
                continue

            factors, key = source[0], source[1]
            metric_key = source[2] if len(source) > 2 else key
            cells[trace] = ComparisonCell(
                factors[key][trace],
                metric_key,
                get_second_level_runtime(trace_mode[trace]),
            )
        return (label, cells)

    def mpi_row(label, gpu_key, mpi_x_key, mpi_key):
        return row(label, {
            'gpu': (host_factors, gpu_key),
            'mpi_x': (hybrid_factors, mpi_x_key),
            'mpi': (mod_factors, mpi_key),
        })

    if has_gpu:
        top_label = 'Host Parallel efficiency'
    else:
        top_label = 'Parallel efficiency'

    rows = [
        # For MPI+<CPU>, Parallel efficiency equals the Hybrid Parallel
        # efficiency (MPI x second-level runtime).
        row(top_label, {
            'gpu': (host_factors, 'host_parallel_eff'),
            'mpi_x': (mod_factors, 'parallel_eff', 'hybrid_eff'),
            'mpi': (mod_factors, 'parallel_eff'),
        }),
        mpi_row('-- MPI Parallel efficiency',
                'mpi_parallel_eff', 'mpi_parallel_eff', 'parallel_eff'),
        mpi_row('   -- MPI Load balance',
                'mpi_load_balance', 'mpi_load_balance', 'load_balance'),
        mpi_row('   -- MPI Communication efficiency',
                'mpi_comm_eff', 'mpi_comm_eff', 'comm_eff'),
        mpi_row('      -- Serialization efficiency',
                'serial_eff', 'serial_eff', 'serial_eff'),
        mpi_row('      -- Transfer efficiency',
                'transfer_eff', 'transfer_eff', 'transfer_eff'),
    ]

    # Second-level CPU runtimes (OpenMP, Pthreads, ...): one block per
    # runtime, filled only for the traces that use it.
    for runtime in second_level_runtimes:
        for label, key in (
                ('-- {} Parallel efficiency', 'omp_parallel_eff'),
                ('   -- {} Load balance', 'omp_load_balance'),
                ('   -- {} Communication efficiency', 'omp_comm_eff')):
            cells = {}
            for trace in trace_list:
                if get_second_level_runtime(trace_mode[trace]) == runtime:
                    cells[trace] = ComparisonCell(
                        hybrid_factors[key][trace], key, runtime
                    )
                else:
                    cells[trace] = None
            rows.append((label.format(runtime), cells))

    if has_gpu:
        rows.append(row('-- Device Offload efficiency', {
            'gpu': (host_factors, 'dev_offload_eff'),
        }))

    return rows


def build_comparison_device_cells(trace_list, trace_mode, device_factors):
    """Build the Device rows of the comparison table (MPI+GPU only).

    Returns an empty list when no trace uses a GPU programming model.
    """
    if not any(is_gpu_model(trace_mode[trace]) for trace in trace_list):
        return []

    rows = []
    for label, key in (
            ('DEVICE Parallel efficiency', 'dev_parallel_eff'),
            ('   -- Device Load balance', 'dev_load_balance'),
            ('   -- Device Communication efficiency', 'dev_comm_eff'),
            ('   -- Device Orchestration efficiency', 'dev_orches_eff')):
        cells = {}
        for trace in trace_list:
            if is_gpu_model(trace_mode[trace]):
                cells[trace] = ComparisonCell(
                    device_factors[key][trace], key
                )
            else:
                cells[trace] = None
        rows.append((label, cells))

    return rows


def _cells_to_values(rows):
    """Convert cell rows into value rows (None -> NOT_APPLICABLE)."""
    return [
        (label, {
            trace: NOT_APPLICABLE if cell is None else cell.value
            for trace, cell in cells.items()
        })
        for label, cells in rows
    ]


def build_comparison_rows(trace_list, trace_mode, mod_factors,
                          hybrid_factors, host_factors):
    """Application rows of the comparison table as values.

    Returns:
        list of (label, {trace: value}); not-applicable cells contain
        NOT_APPLICABLE.
    """
    return _cells_to_values(build_comparison_cells(
        trace_list, trace_mode, mod_factors, hybrid_factors, host_factors,
    ))


def build_comparison_device_rows(trace_list, trace_mode, device_factors):
    """Device rows of the comparison table as values (MPI+GPU only)."""
    return _cells_to_values(build_comparison_device_cells(
        trace_list, trace_mode, device_factors,
    ))
