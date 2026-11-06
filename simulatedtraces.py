#!/usr/bin/env python3

"""Dimemas simulated traces given as input.

A trace simulated by Dimemas is recognized by its content, not by its name:
the .row file written by Dimemas starts with "LEVEL SYSTEM SIZE 1" followed
by "unnamed_1 ()", while Extrae writes "LEVEL CPU SIZE <n>" with the node
names and nsys2prv writes "LEVEL NODE SIZE <n>". When the trace has no .row
file, the name *.sim.prv (the name used by BasicAnalysis for its own
simulations) is used instead.

What Dimemas simulates, and therefore what BasicAnalysis can compute:

  - Dimemas replays the MPI level: the main thread of each process, its
    computation bursts and its MPI calls and messages. The MPI-level metrics
    describe the simulated execution.
  - OpenMP (or Pthreads) worker threads and GPU streams are not simulated:
    they have no states in the simulated trace and the GPU stream labels lose
    the device. For these traces only the MPI-level metrics are reported.
  - Dimemas is not run again on a simulated trace, so Serialization and
    Transfer efficiencies are not available.
  - Hardware counters are copied from the original trace. They are consistent
    with the simulated time only when the simulation keeps the CPU speed
    (CPU ratio 1), which the trace does not record: they are reported with a
    warning.
  - Some Dimemas outputs (seen with MPI+CUDA simulations) have state records
    that end long after the end time in their own header. No metric is
    reported for those traces.
"""

from __future__ import print_function, division

import gzip
import html
import os
import re


DIMEMAS_ROW_SIGNATURE = ("LEVEL SYSTEM SIZE 1", "unnamed_1 ()")

SIMULATED_NAME_SUFFIXES = (".sim.prv", ".sim.prv.gz")

# Value of the metrics that a simulated trace cannot give.
NOT_AVAILABLE = 'Non-Avail'

# Metrics that need the ideal (Dimemas) simulation of the input trace.
SIMULATION_METRIC_KEYS = {
    'mod_factors': ('serial_eff', 'transfer_eff'),
    'hybrid_factors': ('serial_eff', 'transfer_eff'),
    'host_factors': ('serial_eff', 'transfer_eff'),
    'hyb_comm_omp_factors': ('omp_serial_eff', 'omp_transfer_eff'),
}

# Metrics kept for simulated traces with a second programming model
# (MPI+OpenMP, MPI+Pthreads, MPI+CUDA, ...): the MPI level, computed from the
# main thread of each process. The other metrics of these groups depend on
# the worker threads or GPU streams that Dimemas does not simulate.
MPI_LEVEL_KEYS = {
    'hybrid_factors': ('mpi_parallel_eff', 'mpi_load_balance', 'mpi_comm_eff'),
    'host_factors': ('mpi_parallel_eff', 'mpi_load_balance', 'mpi_comm_eff'),
}

# Groups cleared for those traces, except the keys in MPI_LEVEL_KEYS.
# other_metrics (elapsed time, speedup, IPC, frequency, I/O) is kept.
NON_MPI_LEVEL_GROUPS = (
    'mod_factors',
    'mod_factors_scale_plus_io',
    'hybrid_factors',
    'hyb_comm_omp_factors',
    'device_factors',
    'host_factors',
    'omp_talp_factors',
    'device_hwc_factors',
)

PURE_MPI_MODES = ('Detailed+MPI', 'Burst+MPI')

# A simulated trace is inconsistent when its measured runtime exceeds the end
# time of its header by more than this fraction.
END_TIME_TOLERANCE = 0.01

_HEADER_TIME_RE = re.compile(r"^#Paraver \([^)]*\):(?P<time>\d+)(?:_(?P<unit>[a-z]+))?:")
_UNIT_TO_US = {'ns': 1e-3, 'us': 1.0, 'ms': 1e3, 's': 1e6}


def _row_path(prv_file):
    if prv_file.endswith('.prv.gz'):
        return prv_file[:-7] + '.row'
    if prv_file.endswith('.prv'):
        return prv_file[:-4] + '.row'
    return prv_file + '.row'


def _first_lines(path, count):
    lines = []
    with open(path, errors='replace') as row_file:
        for line in row_file:
            line = line.strip()
            if line:
                lines.append(line)
            if len(lines) == count:
                break
    return tuple(lines)


def is_simulated_trace(prv_file):
    """True when the trace was written by Dimemas (see the module doc)."""
    row_path = _row_path(prv_file)
    if os.path.exists(row_path):
        try:
            return _first_lines(row_path, 2) == DIMEMAS_ROW_SIGNATURE
        except OSError:
            pass
    return prv_file.endswith(SIMULATED_NAME_SUFFIXES)


def header_end_time_us(prv_file):
    """End time of the trace from its '#Paraver' header, in microseconds.

    Returns None when the header cannot be read.
    """
    opener = gzip.open if prv_file.endswith('.prv.gz') else open
    try:
        with opener(prv_file, 'rt', errors='replace') as trace_file:
            line = trace_file.readline()
    except OSError:
        return None
    match = _HEADER_TIME_RE.match(line)
    if not match:
        return None
    factor = _UNIT_TO_US.get(match.group('unit') or 'us')
    if factor is None:
        return None
    return int(match.group('time')) * factor


def find_inconsistent_simulations(trace_list, simulated, raw_data):
    """Simulated traces whose measured runtime exceeds their header end time.

    Returns {trace: (header end time in us, measured runtime in us)}.
    """
    runtimes = raw_data.get('runtime', {})
    inconsistent = {}
    for trace in trace_list:
        if trace not in simulated:
            continue
        end_us = header_end_time_us(trace)
        try:
            runtime_us = float(runtimes.get(trace))
        except (TypeError, ValueError):
            continue
        if end_us and runtime_us > end_us * (1.0 + END_TIME_TOLERANCE):
            inconsistent[trace] = (end_us, runtime_us)
    return inconsistent


def inconsistent_simulation_warnings(inconsistent):
    """Lines of the warning printed for inconsistent simulated traces."""
    lines = []
    for trace, (end_us, runtime_us) in inconsistent.items():
        lines += [
            '==WARNING== {}: the simulated trace has records up to {:.3f} s but its'
            .format(trace, runtime_us * 1e-6),
            '  header ends at {:.6f} s. The Dimemas output is inconsistent: no'
            .format(end_us * 1e-6),
            '  metrics are reported for this trace.',
        ]
    return lines


def is_simulated_input(trace, cmdl_args):
    """True when the trace was detected as simulated for this analysis."""
    return trace in getattr(cmdl_args, 'simulated_traces', ())


def has_second_model(trace_mode):
    """True for MPI traces with a second programming model or a device."""
    return trace_mode not in PURE_MPI_MODES


def ideal_trace_bases(trace, processes):
    """Base names (without .prv) of the ideal simulations of a trace."""
    if trace.endswith('.prv.gz'):
        name = trace[:-7]
    elif trace.endswith('.prv'):
        name = trace[:-4]
    else:
        return ()
    base = name + '_' + str(processes) + 'P'
    return (base + '.sim', base + '_hybrid.sim')


def find_overwritten_inputs(trace_list, trace_processes, simulated):
    """Inputs that the ideal simulation of another input would overwrite.

    BasicAnalysis writes the ideal simulation of x.prv as x_<N>P.sim.prv next
    to x.prv, together with x_<N>P.sim.* statistics, and then moves them to
    scratch_out_basicanalysis. A simulated input with that name would be
    overwritten and moved away. Returns [(input, trace that overwrites it)].
    """
    inputs = {}
    for trace in trace_list:
        if trace.endswith('.prv.gz'):
            inputs[os.path.abspath(trace[:-7])] = trace
        elif trace.endswith('.prv'):
            inputs[os.path.abspath(trace[:-4])] = trace

    clashes = []
    for trace in trace_list:
        if trace in simulated:
            continue
        for base in ideal_trace_bases(trace, trace_processes[trace]):
            other = inputs.get(os.path.abspath(base))
            if other is not None and other != trace:
                clashes.append((other, trace))
    return clashes


def _not_available(group, key):
    """'Non-Avail', or NaN for the other metrics that the report printers
    compare as numbers (flushing and the I/O percentages)."""
    if group == 'other_metrics' and (key == 'flushing'
                                     or (key.startswith('io_') and key != 'io_eff')):
        return float('nan')
    return NOT_AVAILABLE


def clear_simulated_metrics(metrics_result, trace_list, trace_mode, simulated,
                            inconsistent=()):
    """Mark the metrics that a simulated trace cannot give as not available.

    metrics_result maps a group name (mod_factors, hybrid_factors, ...) to its
    factor dictionary ([metric key][trace]), as returned by compute_metrics.
    Every metric of the inconsistent traces is marked as not available.
    """
    for trace in trace_list:
        if trace not in simulated:
            continue

        if trace in inconsistent:
            for group, factors in metrics_result.items():
                if not isinstance(factors, dict):
                    continue
                for key, values in factors.items():
                    if not isinstance(values, dict) or trace not in values:
                        continue
                    # Structured I/O data (request sizes, files) comes from
                    # the I/O events, not from the runtime: it is kept.
                    if group == 'other_metrics' and not isinstance(
                            values[trace], (int, float)):
                        continue
                    values[trace] = _not_available(group, key)
            continue

        for group, keys in SIMULATION_METRIC_KEYS.items():
            factors = metrics_result.get(group)
            if not factors:
                continue
            for key in keys:
                if key in factors and trace in factors[key]:
                    factors[key][trace] = NOT_AVAILABLE

        if not has_second_model(trace_mode[trace]):
            continue

        for group in NON_MPI_LEVEL_GROUPS:
            factors = metrics_result.get(group)
            if not factors:
                continue
            kept = MPI_LEVEL_KEYS.get(group, ())
            for key, values in factors.items():
                if key in kept or not isinstance(values, dict):
                    continue
                if trace in values:
                    values[trace] = NOT_AVAILABLE


def simulated_trace_warnings(trace_list, trace_mode, simulated):
    """Lines of the warning printed when simulated traces are analyzed."""
    traces = [trace for trace in trace_list if trace in simulated]
    if not traces:
        return []

    lines = ['==WARNING== Dimemas simulated traces:']
    lines += ['  ' + trace for trace in traces]
    lines += [
        '  The metrics describe the simulated execution, not the measured one.',
        '  Dimemas is not run again on these traces: Serialization and Transfer',
        '  efficiencies are not available.',
        '  Hardware counters are copied from the original trace by Dimemas. IPC,',
        '  frequency and the computation scalability factors are only valid if the',
        '  simulation kept the CPU speed (CPU ratio 1).',
    ]

    second_model = [trace for trace in traces if has_second_model(trace_mode[trace])]
    if second_model:
        lines += [
            '  Dimemas simulates the MPI level only: the main thread of each process,',
            '  its computation and its MPI calls. OpenMP/Pthreads worker threads and GPU',
            '  streams have no states in the simulated trace, so only the MPI-level',
            '  metrics (MPI Parallel, Load balance, Communication efficiency) are',
            '  reported, and the average IPC and frequency only cover the main',
            '  threads, for:',
        ]
        lines += ['    {} ({})'.format(trace, trace_mode[trace]) for trace in second_model]
    return lines


def simulated_trace_note_html(report_traces):
    """Warning shown in the HTML report when simulated traces are analyzed."""
    traces = [trace for trace in report_traces if trace.get('simulated')]
    if not traces:
        return ''

    names = ', '.join('<code>{}</code>'.format(html.escape(trace['name'])) for trace in traces)
    broken = [trace['name'] for trace in traces if trace.get('inconsistent')]
    inconsistent = ''
    if broken:
        inconsistent = (
            ' The Dimemas output of {} has records after the end time of its '
            'header: no metrics are reported for it.'
        ).format(', '.join('<code>{}</code>'.format(html.escape(name))
                           for name in broken))
    second_model = [trace['name'] for trace in traces
                    if has_second_model(trace.get('mode', ''))]
    mpi_level = ''
    if second_model:
        mpi_level = (
            ' Dimemas simulates the MPI level only (the main thread of each '
            'process): OpenMP/Pthreads worker threads and GPU streams have no '
            'states in the simulated trace, so only the MPI-level metrics are '
            'reported, and the average IPC and frequency only cover the main '
            'threads, for {}.'
        ).format(', '.join('<code>{}</code>'.format(html.escape(name))
                           for name in second_model))

    return (
        "<div class='scaling-model-warning'>"
        "<b>Dimemas simulated traces:</b> {names}. The metrics describe the "
        "simulated execution. Dimemas is not run again on them, so "
        "Serialization and Transfer efficiencies are not available. Hardware "
        "counters are copied from the original trace: IPC, frequency and the "
        "computation scalability factors are only valid if the simulation kept "
        "the CPU speed.{mpi_level}{inconsistent}"
        "</div>"
    ).format(names=names, mpi_level=mpi_level, inconsistent=inconsistent)
